"""Optional official Ark AIGC asset sync; mappings live outside editable projects."""
import copy,datetime,hashlib,hmac,json,re,threading,time,urllib.parse,urllib.request,urllib.error
import cloud_video
ENDPOINT='https://ark.cn-beijing.volcengineapi.com'
class AssetRejected(ValueError):pass
OP=urllib.request.build_opener(urllib.request.ProxyHandler({}));LOCK=threading.RLock();GROUP_LOCKS={}
def sign(action,body,ak,sk,stamp=None):
    stamp=stamp or datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');day=stamp[:8]
    raw=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode();digest=hashlib.sha256(raw).hexdigest();host=urllib.parse.urlsplit(ENDPOINT).netloc
    query=urllib.parse.urlencode(sorted({'Action':action,'Version':'2024-01-01'}.items()))
    headers={'Content-Type':'application/json','Host':host,'X-Date':stamp,'X-Content-Sha256':digest}
    canonical=''.join(k.lower()+':'+v.strip()+'\n' for k,v in sorted(headers.items(),key=lambda row:row[0].lower()))
    signed='content-type;host;x-content-sha256;x-date';scope=day+'/cn-beijing/ark/request'
    request='POST\n/\n'+query+'\n'+canonical+'\n'+signed+'\n'+digest
    message='HMAC-SHA256\n'+stamp+'\n'+scope+'\n'+hashlib.sha256(request.encode()).hexdigest()
    key=sk.encode()
    for item in (day,'cn-beijing','ark','request'):key=hmac.new(key,item.encode(),hashlib.sha256).digest()
    headers['Authorization']='HMAC-SHA256 Credential='+ak+'/'+scope+', SignedHeaders='+signed+', Signature='+hmac.new(key,message.encode(),hashlib.sha256).hexdigest()
    return ENDPOINT+'/?'+query,raw,headers

def call(p,action,body):
    if p.get('protocol')!='ark' or p.get('url')!=cloud_video.DEFAULTS['ark']:raise ValueError('自动入库目前只接入火山官方服务，不向中转站发送AK/SK')
    ak=p.get('asset_access_key','');sk=p.get('asset_secret_key','')
    if not ak or not sk:raise ValueError('请在云端服务的“虚拟角色素材库”中配置AK/SK，并先在方舟签署虚拟素材授权')
    url,raw,headers=sign(action,{**body,'ProjectName':p.get('asset_project') or 'default'},ak,sk)
    try:
        with OP.open(urllib.request.Request(url,data=raw,headers=headers),timeout=30) as r:data=json.load(r)
    except urllib.error.HTTPError as e:raise AssetRejected(cloud_video.provider_error(e,sk).replace(ak,'[AK已隐藏]')) from None
    except (OSError,ValueError):raise ValueError('素材库接口连接失败；不会自动重复上传，请核对后再试') from None
    error=data.get('ResponseMetadata',{}).get('Error')
    if error:raise AssetRejected('素材库拒绝请求：'+str(error.get('Code','Unknown'))+'；请核对虚拟素材授权、创作权益与IAM权限')
    return data.get('Result',{})

def state_path(app,pid):return app.project(pid).parent/'ark-assets.json'
def read(app,pid):
    file=state_path(app,pid)
    return json.loads(file.read_text()) if file.exists() else {'groups':{},'resources':{}}
def write_row(app,pid,key,row):
    with LOCK:
        state=read(app,pid);state['resources'][key]=copy.deepcopy(row);app.save(state_path(app,pid),state)
def locate(project,resource_id):
    for character in project['assets']:
        if character.get('type')!='角色':continue
        if character['id']==resource_id:return character,character
        for look in character.get('looks',[]):
            if look['id']==resource_id:return character,look
    raise ValueError('只能同步当前项目的角色身份图或角色造型图')
def provider(app,ident):
    p=cloud_video.profile(app.SETTINGS,ident)
    if not p or p['protocol']!='ark':raise ValueError('请选择已启用的火山方舟服务')
    return p

def view(app,pid):
    state=read(app,pid);project=app.load(pid)
    for row in state['resources'].values():
        try:_,resource=locate(project,row['resource_id']);row['stale']=resource.get('image')!=row['image']
        except ValueError:row['stale']=True
    return {'resources':state['resources'],'catalog':list(state.get('catalog',{}).values())}

def launch(app,pid,body):
    with app.LOCK:return launch_locked(app,pid,body)

def launch_locked(app,pid,body):
    project=app.load(pid);p=provider(app,body.get('model'));character,resource=locate(project,body.get('resource_id'))
    if p.get('url')!=cloud_video.DEFAULTS['ark']:raise ValueError('自动同步目前仅支持火山官方接口')
    if not p.get('asset_access_key') or not p.get('asset_secret_key'):raise ValueError('尚未配置素材库AK/SK；服务连接 → 虚拟角色素材库。它与视频API密钥不同')
    image=resource.get('image')
    if not image or not image.startswith('/media/'+pid+'/media/'):raise ValueError('请先上传或生成本角色/造型的图片')
    if not p.get('public_media_url'):raise ValueError('尚未配置素材公网HTTPS地址，火山素材库需要下载这张图片')
    app.Q.reject_duplicate(pid,'asset_sync',resource['id'])
    job={'id':app.uid(),'kind':'asset_sync','operation':'sync_ark_asset','target':'asset','target_id':resource['id'],'model':body['model'],'title':'Seedance素材同步 · '+character['name']+(' · '+resource.get('name','') if character is not resource else ''),'created':time.time(),'status':'queued','resource_id':resource['id'],'image':image,'asset_project':p.get('asset_project') or 'default'}
    return app.Q.enqueue(pid,job)

def run(queue,pid,j):
    app=queue.app;p=provider(app,j['model']);project=app.load(pid);character,resource=locate(project,j['resource_id'])
    if (p.get('asset_project') or 'default')!=j['asset_project']:raise ValueError('素材库项目已变更，请恢复配置后查询')
    if resource.get('image')!=j['image']:raise ValueError('图片已切换，本次未上传；请同步当前版本')
    digest=hashlib.sha256(app.local_file(j['image']).read_bytes()).hexdigest();key=p['id']+':'+resource['id']
    with LOCK:row=copy.deepcopy(read(app,pid)['resources'].get(key,{}))
    if row.get('sha256')!=digest or row.get('asset_project')!=j['asset_project']:
        row={'provider_id':p['id'],'resource_id':resource['id'],'character_id':character['id'],'image':j['image'],'sha256':digest,'asset_project':j['asset_project'],'status':'NotSynced'}
    try:
        if not row.get('asset_id'):
            if row.get('status') in ('SubmittingGroup','SubmittingAsset','Unknown'):raise ValueError('上次提交结果不明，请先在方舟核对，防止重复创建素材')
            group_key=p['id']+':'+j['asset_project']+':'+character['id']
            with LOCK:group_lock=GROUP_LOCKS.setdefault((pid,group_key),threading.Lock())
            with group_lock:
                queue.check(j)
                with LOCK:group=copy.deepcopy(read(app,pid)['groups'].get(group_key,{}))
                if group.get('status')=='Unknown':raise ValueError('上次创建素材组结果不明，请先在方舟核对')
                if not group.get('id'):
                    with LOCK:
                        state=read(app,pid);state['groups'][group_key]={'status':'Unknown'};app.save(state_path(app,pid),state)
                    try:result=call(p,'CreateAssetGroup',{'Name':character['name'][:64],'Description':'Shotdesk virtual character','GroupType':'AIGC'})
                    except AssetRejected:
                        with LOCK:
                            state=read(app,pid);state['groups'][group_key]={'status':'Rejected'};app.save(state_path(app,pid),state)
                        raise
                    if not result.get('Id'):raise ValueError('创建素材组未返回ID，请在方舟核对')
                    group={'id':result['Id'],'status':'Ready'}
                    with LOCK:
                        state=read(app,pid);state['groups'][group_key]=group;app.save(state_path(app,pid),state)
            queue.check(j)
            url=cloud_video.grant_media(queue,pid,j,p,[j['image']])[0]
            row.update(group_id=group['id'],status='SubmittingAsset');write_row(app,pid,key,row)
            result=call(p,'CreateAsset',{'GroupId':group['id'],'URL':url,'AssetType':'Image','Name':resource.get('name',character['name'])[:64]})
            if not result.get('Id'):raise ValueError('上传未返回素材ID，结果不明，请在方舟核对')
            row.update(asset_id=result['Id'],status='Processing');write_row(app,pid,key,row)
        for _ in range(60):
            queue.check(j);j.update(phase='asset_review');queue.persist(pid,j)
            result=call(p,'GetAsset',{'Id':row['asset_id']});status=result.get('Status')
            if status not in ('Active','Processing','Failed'):raise ValueError('素材库返回未知审核状态，ID已保留')
            row.update(status=status,checked_at=time.time());row.pop('error',None)
            if status=='Failed':
                error=result.get('Error') or {};row['error']=str(error.get('Code','ReviewFailed'))
            write_row(app,pid,key,row)
            if status=='Active':return {'asset_id':row['asset_id'],'status':'Active'}
            if status=='Failed':raise ValueError('素材审核未通过：'+row['error'])
            queue.events[j['id']].wait(10)
        return {'asset_id':row['asset_id'],'status':'Processing','notice':'仍在审核，稍后点刷新审核，不会重新上传'}
    except Exception as exc:
        if row.get('status')=='SubmittingAsset':row['status']='Rejected' if isinstance(exc,AssetRejected) else 'Unknown'
        row['error']=str(exc)[:600];write_row(app,pid,key,row);raise

def image_input(app,pid,p,item):
    resource_id=item.get('look_id') or item['asset_id'];state=read(app,pid);row=state['resources'].get(p['id']+':'+resource_id)
    if not row:return app.reference(item['url'])
    if row.get('status') not in ('Active','Manual'):raise ValueError('Seedance素材尚未可用：'+item.get('name','')+'；请在角色卡查看审核状态')
    if row['image']!=item['url'] or row['sha256']!=hashlib.sha256(app.local_file(item['url']).read_bytes()).hexdigest():raise ValueError('角色或造型图片已更换，请先重新同步Seedance素材')
    if row['asset_project']!=(p.get('asset_project') or 'default'):raise ValueError('素材与当前火山项目不一致，请核对配置')
    return 'asset://'+row['asset_id']


def manage(app,pid,body):
    """Register externally obtained IDs without asserting official review approval."""
    with app.LOCK,LOCK:
        project=app.load(pid);p=provider(app,body.get('model'))
        if p.get('url')!=cloud_video.DEFAULTS['ark']:raise ValueError('素材ID绑定目前仅支持火山官方服务')
        state=read(app,pid);catalog=state.setdefault('catalog',{});action=body.get('operation')
        scope=p['id']+':'+(p.get('asset_project') or 'default')+':'
        if action=='register':
            ident=str(body.get('asset_id','')).strip().removeprefix('asset://')
            if not re.fullmatch(r'asset-[A-Za-z0-9_-]{1,150}',ident):raise ValueError('请复制完整素材ID（asset-…）或 asset://…，不是素材组ID')
            name=str(body.get('name','')).strip()[:100]
            if not name:raise ValueError('请填写素材名称')
            image=body.get('thumbnail') or ''
            if image:
                if not isinstance(image,str) or not image.startswith('/media/'+pid+'/media/'):raise ValueError('缩略图必须上传到当前项目')
                app.local_file(image).read_bytes()
            key=scope+ident;catalog[key]={'key':key,'asset_id':ident,'name':name,'thumbnail':image,'provider_id':p['id'],'asset_project':p.get('asset_project') or 'default','source':'manual','status':'Manual','created':time.time()}
        elif action in ('bind','unbind'):
            character,resource=locate(project,body.get('resource_id'));key=p['id']+':'+resource['id']
            app.Q.reject_duplicate(pid,'asset_sync',resource['id'])
            if action=='unbind':state['resources'].pop(key,None)
            else:
                entry=catalog.get(str(body.get('catalog_key','')))
                if not entry or entry['provider_id']!=p['id'] or entry['asset_project']!=(p.get('asset_project') or 'default'):raise ValueError('请选择当前服务与项目下的素材')
                image=resource.get('image')
                if not image:raise ValueError('请先上传此素材对应的角色或造型图，再绑定素材ID')
                digest=hashlib.sha256(app.local_file(image).read_bytes()).hexdigest()
                state['resources'][key]={'provider_id':p['id'],'resource_id':resource['id'],'character_id':character['id'],'image':image,'sha256':digest,'asset_project':entry['asset_project'],'asset_id':entry['asset_id'],'source':'manual','status':'Manual','catalog_key':entry['key']}
        elif action=='remove':
            key=str(body.get('catalog_key',''))
            if not key.startswith(scope):raise ValueError('素材不属于当前服务或项目')
            if any(r.get('catalog_key')==key for r in state['resources'].values()):raise ValueError('素材仍被绑定，请先解除绑定')
            catalog.pop(key,None)
        else:raise ValueError('未知素材操作')
        app.save(state_path(app,pid),state)
        return view(app,pid)
