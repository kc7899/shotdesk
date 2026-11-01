"""Portable ComfyUI API-workflow adapter. No weights, prompt rewriting or custom nodes."""
import base64,copy,hashlib,json,math,os,re,threading,time,urllib.request,urllib.parse,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parent/'workflows'
COMFY=os.getenv('COMFY_URL','http://127.0.0.1:8188')
OP=urllib.request.build_opener(urllib.request.ProxyHandler({}));LOCK=threading.RLock()
PORTABLE=True
ALLOWED_MODES={'reference','first_frame','text','audio','music','video_reference','upscale','interpolate'}
class Recipes:IMAGES={};VIDEOS={}
recipes=Recipes();IMAGE_MODELS={};VIDEO_MODELS={}
def definitions():
    ROOT.mkdir(parents=True,exist_ok=True);result=[]
    for p in sorted(ROOT.glob('*.json')):
        if p.name.endswith('.example.json'):continue
        value=json.loads(p.read_text());validate(value);result.append(value)
    if len({x['id'] for x in result})!=len(result):raise ValueError('工作流ID重复')
    return result

def validate(value):
    if not isinstance(value,dict) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',str(value.get('id',''))):raise ValueError('工作流ID只允许字母、数字、点、短横线和下划线')
    if value.get('kind') not in ('image','video'):raise ValueError('工作流类型须为image或video')
    graph=value.get('graph')
    if not isinstance(graph,dict) or not graph or len(graph)>2000 or any(not isinstance(n,dict) or not isinstance(n.get('class_type'),str) or not isinstance(n.get('inputs'),dict) for n in graph.values()):raise ValueError('请导入ComfyUI的API格式工作流，不是画布UI格式')
    if str(value.get('output_node')) not in graph:raise ValueError('输出节点不存在')
    bindings=value.get('bindings')
    if not isinstance(bindings,dict) or not bindings.get('prompt'):raise ValueError('请指定prompt参数对应的节点输入')
    if any(any(k in n['inputs'] for k in ('seed','noise_seed')) for n in graph.values()) and not bindings.get('seed'):raise ValueError('工作流含随机种子节点，请映射seed，避免重复出图')
    if value['kind']=='video' and (not value.get('modes') or set(value['modes'])-ALLOWED_MODES):raise ValueError('视频工作流需要有效的modes生成方式')
    max_refs=value.get('max_references',0)
    if isinstance(max_refs,bool) or not isinstance(max_refs,int) or not 0<=max_refs<=32:raise ValueError('max_references须为0–32整数')
    for key,targets in bindings.items():
        if not re.fullmatch(r'prompt|seed|width|height|duration|frames|fps|first_frame|image_\d+',key):raise ValueError('不支持的参数映射：'+key)
        if not isinstance(targets,list) or not targets:raise ValueError('参数映射须为非空列表')
        for target in targets:
            if not isinstance(target,list) or len(target)!=2 or str(target[0]) not in graph or target[1] not in graph[str(target[0])]['inputs']:raise ValueError('参数映射引用了不存在的节点输入')
    if max_refs and any('image_'+str(i) not in bindings for i in range(max_refs)):raise ValueError('每一个参考图名额都须有image_N映射，编号从0开始')
    if value['kind']=='video' and 'first_frame' in value.get('modes',[]) and 'first_frame' not in bindings:raise ValueError('首帧工作流须映射first_frame')
    if value['kind']=='video' and 'reference' in value.get('modes',[]) and not max_refs:raise ValueError('资产参考工作流须声明参考图名额')
    if value['kind']=='video' and not ('duration' in bindings or 'frames' in bindings):raise ValueError('视频工作流须映射duration或frames，不能静默忽略镜头时长')
    if any(m in value.get('modes',[]) for m in ('audio','music','video_reference','upscale','interpolate')):raise ValueError('通用导入器暂不接收音频/视频输入映射；请使用已实现这些输入的专用适配器')
    for key,default in [('width',512),('height',512),('fps',16),('frame_alignment',1),('frame_offset',0)]:
        n=value.get(key,default)
        if isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) or (n<0 if key=='frame_offset' else n<=0):raise ValueError(key+'必须为有效正数')
    return value

def catalog():
    return {'images':[descriptor(x) for x in definitions() if x['kind']=='image'],'videos':[descriptor(x) for x in definitions() if x['kind']=='video']}
def descriptor(x):
    return {'id':x['id'],'display_name':x.get('name',x['id']),'modes':x.get('modes',[]),'max_references':x.get('max_references',0),'operation':'generate','requires_image':bool(x.get('max_references',0)),'supports_resolution':bool(x['bindings'].get('width') and x['bindings'].get('height')),'canonical_model':x['id'],'legacy_resolution':None,'verification':'imported-unverified','dependencies':x.get('dependencies',{}),'available':None}
def import_definition(value,replace=False):
    validate(value)
    with LOCK:
        ROOT.mkdir(parents=True,exist_ok=True);p=ROOT/(value['id']+'.json')
        if p.exists() and not replace:raise ValueError('已有同名工作流；确认替换后传replace:true')
        tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)
    return descriptor(value)
def json_request(path):
    with OP.open(COMFY+path,timeout=10) as response:return json.load(response)
def check_definition(value):
    validate(value)
    try:info=json_request('/object_info')
    except Exception:return {'ok':False,'reachable':False,'missing_nodes':[],'missing_models':[],'notice':'无法连接ComfyUI；请检查服务地址'}
    missing_nodes=[];missing_models=[]
    mapped={(str(node),key) for targets in value['bindings'].values() for node,key in targets}
    for ident,node in value['graph'].items():
        spec=info.get(node['class_type'])
        if spec is None:missing_nodes.append(node['class_type']);continue
        inputs={**spec.get('input',{}).get('required',{}),**spec.get('input',{}).get('optional',{})}
        for key,actual in node['inputs'].items():
            choices=inputs.get(key)
            if (ident,key) not in mapped and isinstance(actual,str) and choices and isinstance(choices[0],list) and actual not in choices[0]:
                missing_models.append({'node':ident,'input':key,'value':actual})
    return {'ok':not missing_nodes and not missing_models,'reachable':True,'missing_nodes':sorted(set(missing_nodes)),'missing_models':missing_models,'notice':'依赖检查不代表实际出图/视频质量已验证'}
def upload_image(value):
    if not isinstance(value,str) or not value.startswith('data:image/') or ';base64,' not in value:raise ValueError('参考图须为平台提供的图片data URL')
    raw=base64.b64decode(value.split(',',1)[1],validate=True)
    if len(raw)>32*1024*1024:raise ValueError('参考图超过32MB')
    extension='png' if raw.startswith(b'\x89PNG') else 'webp' if raw[:4]==b'RIFF' else 'jpg';name='shotdesk-'+uuid.uuid4().hex+'.'+extension;boundary='shotdesk-'+uuid.uuid4().hex
    payload=(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\nContent-Type: image/{extension}\r\n\r\n').encode()+raw+f'\r\n--{boundary}--\r\n'.encode()
    req=urllib.request.Request(COMFY+'/upload/image',data=payload,headers={'Content-Type':'multipart/form-data; boundary='+boundary})
    with OP.open(req,timeout=60) as response:result=json.load(response)
    return '/'.join(filter(None,[result.get('subfolder',''),result['name']])),hashlib.sha256(raw).hexdigest()
def build_graph(body,job_id,kind):
    spec=next((x for x in definitions() if x['id']==body['model'] and x['kind']==kind),None)
    if spec is None:raise ValueError('工作流未配置；请在服务连接中导入API格式工作流')
    check=check_definition(spec)
    if not check['ok']:raise ValueError('工作流依赖未就绪：'+json.dumps(check,ensure_ascii=False))
    graph=copy.deepcopy(spec['graph']);size=body.get('video_size') or {};width=size.get('width',spec.get('width',512));height=size.get('height',spec.get('height',512))
    if not size and body.get('aspect_ratio')=='9:16':width,height=min(width,height),max(width,height)
    elif not size and body.get('aspect_ratio')=='16:9':width,height=max(width,height),min(width,height)
    elif not size and body.get('aspect_ratio')=='1:1':width=height=min(width,height)
    if not size and (body.get('aspect_ratio') in ('3:4','4:3') or width==height and body.get('aspect_ratio') in ('16:9','9:16')):
        rw,rh=map(int,body['aspect_ratio'].split(':'));side=max(width,height);width=max(8,round(side*min(1,rw/rh)/8)*8);height=max(8,round(side*min(1,rh/rw)/8)*8)
    duration=float(body.get('duration',4));fps=float(spec.get('fps',16));align=int(spec.get('frame_alignment',1));offset=int(spec.get('frame_offset',0))
    frames=max(1,round((duration*fps-offset)/align)*align+offset)
    values={'prompt':body['prompt'],'seed':body.get('seed',int(uuid.uuid4().hex[:12],16)),'width':width,'height':height,'duration':duration,'fps':fps,'frames':frames};hashes=[]
    refs=body.get('image') or []
    if isinstance(refs,str):refs=[refs]
    if len(refs)>spec.get('max_references',0):raise ValueError('参考图数量超过工作流映射名额')
    for i,value in enumerate(refs):values['image_'+str(i)],digest=upload_image(value);hashes.append(digest)
    if body.get('first_frame_image'):
        if not spec['bindings'].get('first_frame'):raise ValueError('工作流未映射首帧输入')
        values['first_frame'],digest=upload_image(body['first_frame_image']);hashes.append(digest)
    for key,targets in spec['bindings'].items():
        if key not in values:
            if key=='first_frame' or key.startswith('image_'):raise ValueError('工作流需要额外参考图片；请关联资源或选择输入数量合适的工作流')
            continue
        for ident,field in targets:graph[str(ident)]['inputs'][field]=values[key]
    return graph,str(spec['output_node']),hashes
