"""Explicit cloud video protocols; credentials stay in private service settings."""
import copy,json,re,time,urllib.request,urllib.error,urllib.parse
PROTOCOLS={'ark','minimax','replicate','fal'}
DEFAULTS={'ark':'https://ark.cn-beijing.volces.com/api/v3','minimax':'https://api.minimax.io','replicate':'https://api.replicate.com/v1','fal':'https://queue.fal.run'}
OP=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def validate_profiles(rows,old,url_validator):
    if not isinstance(rows,list) or len(rows)>20:raise ValueError('云端视频服务须为列表，最多20项')
    previous={x['id']:x for x in old};result=[];seen=set()
    for row in rows:
        if not isinstance(row,dict) or set(row)-{'id','name','protocol','url','model','api_key','clear_key','enabled','max_references','modes','resolution','key_configured'}:raise ValueError('云端视频服务字段不正确')
        ident=row.get('id','');protocol=row.get('protocol')
        if not isinstance(ident,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,60}',ident) or ident in seen:raise ValueError('云端服务ID无效或重复')
        seen.add(ident)
        if protocol not in PROTOCOLS:raise ValueError('不支持的云端视频协议')
        item=copy.deepcopy(row);item.pop('key_configured',None);item['url']=url_validator(row.get('url') or DEFAULTS[protocol]);item['name']=str(row.get('name') or ident).strip()[:100]
        model=row.get('model','')
        if not isinstance(model,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./:-]{0,179}',model) or '..' in model:raise ValueError('请填写服务实际使用的模型ID')
        item['model']=model
        refs=row.get('max_references',9)
        if isinstance(refs,bool) or not isinstance(refs,int) or not 0<=refs<=30:raise ValueError('参考图片数量须为0–30')
        item['max_references']=refs
        modes=row.get('modes',['text','first_frame','reference'])
        if not isinstance(modes,list) or not modes or set(modes)-{'text','first_frame','reference'} or ('reference' in modes and not refs):raise ValueError('云端生成方式无效')
        item['modes']=modes
        for flag in ('enabled','clear_key'):
            if flag in row and not isinstance(row[flag],bool):raise ValueError('服务开关须为布尔值')
        key=row.get('api_key') or previous.get(ident,{}).get('api_key','')
        if row.get('clear_key'):key=''
        if not isinstance(key,str) or len(key)>8192 or '\n' in key or '\r' in key:raise ValueError('API密钥无效')
        item.pop('clear_key',None);item['api_key']=key;item['enabled']=row.get('enabled',True)
        resolution=row.get('resolution') or ('2K' if protocol=='minimax' else '720p')
        if resolution not in ('480p','720p','1080p','480P','768P','2K'):raise ValueError('云端分辨率不受支持')
        item['resolution']=resolution;result.append(item)
    return result

def public_profiles(rows):return [{**{k:v for k,v in x.items() if k!='api_key'},'key_configured':bool(x.get('api_key'))} for x in rows]
def profile(settings,model):return next((x for x in settings.read().get('video_providers',[]) if 'cloud-'+x['id']==model and x.get('enabled',True)),None)
def catalog(settings):
    return [{'id':'cloud-'+x['id'],'display_name':x['name'],'provider':x['protocol'],'modes':x['modes'],'max_references':x['max_references'],'supports_resolution':True,'canonical_model':'cloud-'+x['id'],'legacy_resolution':None,'operation':'generate','verification':'configured-unverified','available':bool(x.get('api_key')),'requires_image':False} for x in settings.read().get('video_providers',[]) if x.get('enabled',True)]
def request(p,path,body=None,method=None):
    key=p.get('api_key')
    if not key:raise ValueError('请先在服务连接中设置云端视频API密钥')
    headers={'Content-Type':'application/json','Authorization':('Key ' if p['protocol']=='fal' else 'Bearer ' if p['protocol']!='replicate' else 'Token ')+key}
    req=urllib.request.Request(p['url']+path,data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None,headers=headers,method=method)
    try:
        with OP.open(req,timeout=60) as r:
            raw=r.read();data=json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        # Don't retain provider bodies: they may echo credentials or input data URLs.
        raise ValueError('云端视频接口拒绝请求（HTTP '+str(e.code)+'）；请检查余额、模型权限和参数') from None
    except (OSError,ValueError):raise ValueError('云端视频接口连接失败或响应无效；不会自动重复提交') from None
    if data.get('base_resp',{}).get('status_code',0):raise ValueError('MiniMax接口返回错误码 '+str(data['base_resp']['status_code']))
    return data

def compile_prompt(p,text,inputs):
    if not inputs:return text
    lines=[]
    for index,item in enumerate(inputs,1):
        alias=('@Image'+str(index)) if p['protocol']=='fal' else '[Image'+str(index)+']'
        source='参考图'+str(index)+' / <Subject '+str(index)+'> / <Picture '+str(index)+'> / Reference image '+str(index)
        lines.append(source+' = '+alias+' : '+str(item.get('name','')))
    return text+'\n\n'+ '\n'.join(lines)

def payload(p,b):
    duration=b.get('duration',4)
    if isinstance(duration,bool) or float(duration)!=int(duration) or not 1<=int(duration)<=30:raise ValueError('云端视频时长须为1–30秒整数，以所选模型支持范围为准')
    duration=int(duration);refs=b.get('image') or [];refs=[refs] if isinstance(refs,str) else refs
    first=b.get('first_frame_image');protocol=p['protocol'];resolution=b.get('cloud_resolution') or p['resolution']
    if first and refs:raise ValueError('首帧和资产参考不能混用')
    if len(refs)>p['max_references']:raise ValueError('参考图超过云端模型配置名额')
    mode='first_frame' if first else 'reference' if refs else 'text'
    if mode not in p['modes']:raise ValueError('云端模型未配置此生成方式')
    text=b['prompt']
    if protocol in ('ark','minimax'):
        content=[{'type':'text','text':text}]
        content.extend({'type':'image_url','image_url':{'url':v},'role':'reference_image'} for v in refs)
        if first:content.append({'type':'image_url','image_url':{'url':first},'role':'first_frame'})
        result={'model':p['model'],'content':content,'duration':duration,'resolution':resolution,'ratio':b.get('aspect_ratio','16:9')}
        if protocol=='minimax':
            if p['model']=='MiniMax-H3' and (not 4<=duration<=15 or resolution not in ('768P','2K')):raise ValueError('MiniMax-H3官方完整模型支持4–15秒，768P或2K')
        else:result.update(generate_audio=b.get('generate_audio',True),seed=b.get('seed',-1))
        return result
    result={'prompt':text,'duration':str(duration) if protocol=='fal' else duration,'resolution':resolution,'aspect_ratio':('auto' if protocol=='fal' else 'adaptive') if first else b.get('aspect_ratio','16:9'),'generate_audio':b.get('generate_audio',True)}
    if protocol=='fal':
        if refs:result['image_urls']=refs
        if first:result['image_url']=first
    else:
        if refs:result['reference_images']=refs
        if first:result['image']=first
    return result

def submit(p,b):
    data=payload(p,b)
    if len(json.dumps(data).encode())>64*1024*1024:raise ValueError('云端请求超过64MB，请缩小参考图')
    protocol=p['protocol'];model=p['model']
    path='/contents/generations/tasks' if protocol=='ark' else '/v2/video_generation' if protocol=='minimax' else '/models/'+model+'/predictions' if protocol=='replicate' else '/'+model
    response=request(p,path,{'input':data} if protocol=='replicate' else data)
    ident=response.get('task_id') if protocol=='minimax' else response.get('request_id') if protocol=='fal' else response.get('id')
    if not isinstance(ident,(str,int)) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',str(ident)):raise ValueError('云端提交未返回任务ID；结果不明，请核对服务商记录，勿重复提交')
    return str(ident)
def task_path(p,ident):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',str(ident)):raise ValueError('云端任务ID无效')
    return '/contents/generations/tasks/'+ident if p['protocol']=='ark' else '/v2/query/video_generation/'+ident if p['protocol']=='minimax' else '/predictions/'+ident if p['protocol']=='replicate' else '/'+ '/'.join(p['model'].split('/')[:2])+'/requests/'+ident

def poll(p,ident):
    path=task_path(p,ident);data=request(p,path+'/status' if p['protocol']=='fal' else path)
    if p['protocol']=='minimax':data=data.get('task',data)
    state=str(data.get('status','')).lower();url=None
    if state in ('succeeded','completed','success'):
        if p['protocol']=='fal':data=request(p,path)
        content=data.get('content') or {};output=data.get('output');video=data.get('video') or {}
        url=content.get('video_url') or content.get('url') or video.get('url') or (output[0] if isinstance(output,list) and output else output if isinstance(output,str) else None)
        if not url:raise ValueError('云端任务完成但未返回视频地址')
        return 'completed',url
    if state in ('failed','canceled','cancelled','expired'):return state,None
    if state not in ('queued','pending','running','processing','starting','in_queue','in_progress'):raise ValueError('云端任务返回未知状态；任务ID已保留')
    return ('running' if state in ('running','processing','in_progress') else 'queued'),None

def cancel(p,ident):
    state,_=poll(p,ident)
    if state in ('completed','failed','canceled','cancelled','expired'):return True
    protocol=p['protocol'];path=task_path(p,ident)
    if protocol=='minimax':
        if state=='running':return False
        request(p,'/v2/video_generation/'+ident,method='DELETE')
    elif protocol=='ark':request(p,path,method='DELETE')
    else:request(p,path+'/cancel',{},method='POST' if protocol=='replicate' else 'PUT')
    return poll(p,ident)[0] in ('completed','failed','canceled','cancelled','expired')

def run(queue,pid,j):
    p=profile(queue.app.SETTINGS,j['request']['model'])
    if not p:raise ValueError('该云端服务已移除或禁用；请恢复原配置以查询任务')
    snapshot={k:p[k] for k in ('id','protocol','url','model')}
    if j.get('cloud_provider') and j['cloud_provider']!=snapshot:raise ValueError('云端任务服务配置已变更，不能使用其他地址或模型查询原任务')
    if not j.get('cloud_task_id'):
        with queue.app.LOCK:
            queue.check(j);j.update(transport='cloud',phase='cloud_submitting',cloud_provider=snapshot);queue.persist(pid,j)
        # One submission only, persist its ID even if cancellation arrived during HTTP.
        ident=submit(p,j['request'])
        with queue.app.LOCK:j.update(cloud_task_id=ident,submitted_at=time.time(),phase='upstream_queue');queue.persist(pid,j)
    deadline=time.monotonic()+7200
    while time.monotonic()<deadline:
        queue.check(j);state,url=poll(p,j['cloud_task_id'])
        if state=='completed':
            parsed=urllib.parse.urlsplit(url)
            if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password:raise ValueError('云端返回的视频地址无效')
            dest=queue.app.project(pid).parent/'media'/(j['id']+'.mp4');j['phase']='downloading';queue.persist(pid,j)
            with OP.open(url,timeout=180) as r, dest.open('wb') as f:
                while True:
                    queue.check(j);chunk=r.read(1024*1024)
                    if not chunk:break
                    f.write(chunk)
            with queue.app.LOCK:
                queue.check(j);local=f'/media/{pid}/media/{dest.name}';queue.app.finish_job(pid,j,local);queue.done(pid,j,url=local)
            return
        if state in ('failed','canceled','cancelled','expired'):raise ValueError('云端视频任务结束：'+state+'；任务ID '+j['cloud_task_id'])
        if state=='running' and not j.get('started_at'):queue.start(pid,j)
        j['phase']='upstream_running' if state=='running' else 'upstream_queue';queue.persist(pid,j);queue.events[j['id']].wait(10)
    raise TimeoutError('云端任务等待超时，任务ID已保留；请核对服务商记录，不会自动重提')

def stop(queue,j):
    if not j.get('cloud_task_id'):
        if j.get('cloud_provider'):raise ValueError('云端提交正在确认，取得任务ID后才能停止')
        return
    p=profile(queue.app.SETTINGS,j['request']['model'])
    if not p or any(p.get(k)!=v for k,v in j['cloud_provider'].items()):raise ValueError('请恢复原云端服务配置后停止任务')
    if not cancel(p,j['cloud_task_id']):raise ValueError('云端模型仍在运行，等待服务商确认结束；可能继续计费')
