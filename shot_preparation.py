"""Per-shot preparation from editable description; bounded LLM calls and partial commits."""
import copy,hashlib,json,re,time

def fingerprint(p,s,step):
    fields=('description','duration') if step=='assets' else ('description','duration','asset_ids','character_looks','video_override')
    value={k:s.get(k) for k in fields}
    value['assets']=[{k:a.get(k) for k in ('id','name','type','default_look_id','looks')} for a in p['assets']]
    if step=='prompts':value.update({k:p.get(k) for k in ('video_model','video_mode','prompt_language','storyboard_requirements')})
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def output_hash(s,step):
    value={k:s.get(k) for k in (('asset_ids','character_looks') if step=='assets' else ('video_prompt','image_prompt'))}
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def current(p,s,step):
    mark=s.get('preparation',{}).get(step,{})
    return mark.get('input')==fingerprint(p,s,step) and mark.get('output')==output_hash(s,step)

def catalog(p):
    return [{'id':a['id'],'name':a['name'],'type':a['type'],'description':a.get('prompt',''),
             'default_look_id':a.get('default_look_id'),'looks':[{'id':l['id'],'name':l.get('name'),'description':l.get('prompt','')} for l in a.get('looks',[])]}
            for a in p['assets'] if a.get('type') in ('角色','场景','道具')]

def ask(api,j,instruction,payload,validate):
    error=''
    for attempt in range(2):
        api.Q.check(j)
        response=api.Q.text_request({'model':j['model'],'messages':[{'role':'system','content':instruction},
            {'role':'user','content':json.dumps(payload,ensure_ascii=False)+(('\n上次输出需修正：'+error) if error else '')}],
            'temperature':0.2,'max_tokens':4500,'response_format':{'type':'json_object'},'chat_template_kwargs':{'enable_thinking':False}},j)
        choice=response['choices'][0];raw=choice['message'].get('content') or ''
        try:
            if choice.get('finish_reason')=='length':raise ValueError('输出未完成，请缩短单镜头内容或增加镜头')
            raw=re.sub(r'<think>.*?</think>','',raw,flags=re.S);obj=json.loads(raw[raw.find('{'):raw.rfind('}')+1])
            return validate(obj)
        except (ValueError,TypeError,KeyError,AttributeError) as exc:error=str(exc)
    raise ValueError('本镜头准备需检查：'+error)

def match_assets(api,j,p,s):
    items={a['id']:a for a in p['assets'] if a.get('type') in ('角色','场景','道具')}
    def validate(obj):
        ids=obj.get('asset_ids');looks=obj.get('character_looks',{});warnings=obj.get('warnings',[])
        if not isinstance(ids,list) or any(not isinstance(x,str) or x not in items for x in ids) or len(set(ids))!=len(ids):raise ValueError('asset_ids只能使用提供的真实ID且不得重复')
        if not isinstance(looks,dict):raise ValueError('character_looks须为对象')
        for aid,lid in looks.items():
            if aid not in ids or items[aid]['type']!='角色' or lid not in [l['id'] for l in items[aid].get('looks',[])]:raise ValueError('造型必须属于本镜已关联角色')
        if not isinstance(warnings,list) or any(not isinstance(x,str) for x in warnings):raise ValueError('warnings须为文字数组')
        if not ids:warnings.append('未匹配到可用资产，请确认本镜是否缺少参考资产')
        return {'asset_ids':ids,'character_looks':looks},warnings[:20]
    return ask(api,j,'你是镜头资产匹配员。唯一剧情依据是description。仅匹配实际出场角色、所在场景和必要道具；不新增资产，不根据旧提示词引入人物。精确选择角色自己的造型；未明确时可用其default_look_id。无法确定或缺失时列入warnings，严禁编造ID或同名跨人物造型。返回JSON {asset_ids:[真实ID],character_looks:{角色ID:造型ID},warnings:[待确认原因]}。',
               {'description':s['description'],'assets':catalog(p)},validate)

def prompts(api,j,p,s):
    selected=set(s.get('asset_ids',[]));assets=[a for a in catalog(p) if a['id'] in selected]
    known={a['id']:a for a in p['assets']}
    if any(a not in known for a in selected):raise ValueError('本镜有关联失效资产，请先匹配资产')
    aliases=[]
    for a in assets:
        label=a['name'];lid=s.get('character_looks',{}).get(a['id']) or a.get('default_look_id')
        if a['type']=='角色' and lid:
            look=next((l for l in a['looks'] if l['id']==lid),None)
            if look is None:raise ValueError('本镜造型不属于所选人物，请先匹配资产')
            label+='·'+look['name']
        aliases.append('@'+label)
    instruction='''你是专业视频镜头提示词编写员。只把description变为可拍摄、时序清楚的一段镜头，绝不改变剧情、说话人或台词。不要读取旧分镜计划或扩写原剧本。明确画面中的人物位置、相互朝向、景别机位、动作执行者与对象；只让一个明确的人说对应台词，其他人物自然反应，不写全员定格。使用给定aliases引用当前已关联资产，不能新增@引用。参考资产模式不重复人物长相、服装或道具外观；首帧模式明确可见人物关系。按提供duration分配动作与台词，时间不足时在warnings提示，不擅自修改时长、删台词或加快语速。语言跟随language，台词保留原语言。返回JSON {video_prompt:文字,image_prompt:单张首帧画面描述,warnings:[问题]}。video_prompt中按0–Ns时间段明确谁做什么、谁说什么；H3使用[Shot 1]起始，切镜才用[Shot 2] At MM:SS.mmm，每句台词用<d>[Chinese] 原话</d>（其他语言填实际语言），不要为了格式强行切镜。不要罗列人物外貌、不要写“原文动作”等占位词。storyboard_requirements仅作镜头调度、节奏与表现的补充参考；只应用当前镜头相关部分，不改description剧情、原台词、已选资产或时长，不能把全局要求逐镜机械重复。'''
    def validate(obj):
        text=obj.get('video_prompt');image=obj.get('image_prompt');warnings=obj.get('warnings',[])
        if not isinstance(text,str) or not text.strip() or not isinstance(image,str) or not image.strip():raise ValueError('须返回非空video_prompt和image_prompt')
        if not isinstance(warnings,list) or any(not isinstance(w,str) for w in warnings):raise ValueError('warnings须为文字数组')
        candidate=copy.deepcopy(s);candidate['video_prompt']=text;candidate['image_prompt']=image;candidate.pop('prompt_format',None)
        api.sync_shot_mentions(p,candidate,True)
        if set(candidate.get('asset_ids',[]))!=selected:raise ValueError('提示词引用必须与当前勾选资产和造型一致')
        for aid,lid in candidate.get('character_looks',{}).items():
            if lid!=(s.get('character_looks',{}).get(aid) or known.get(aid,{}).get('default_look_id')):raise ValueError('提示词不得更改当前造型')
        for dialogue in re.findall(r'“([^”]+)”|「([^」]+)」',s['description']):
            quote=next(x for x in dialogue if x)
            if quote not in text:raise ValueError('视频提示词未逐字保留本镜引用的台词')
        return {'video_prompt':'Duration: '+str(s['duration'])+'s\n'+re.sub(r'^\s*Duration:\s*[^\n]*\n?','',text).strip(),'image_prompt':image},warnings[:20]
    return ask(api,j,instruction,{'description':s['description'],'duration':s['duration'],'assets':assets,'aliases':aliases,
        'mode':api.video_mode(s,p),'model':api.video_model(s,p),'language':p.get('prompt_language','zh'),'storyboard_requirements':p.get('storyboard_requirements','')},validate)

def launch(api,pid,body):
    with api.LOCK:
        p=api.load(pid);operation=body.get('operation','prepare');scope=body.get('scope','missing')
        if operation not in ('assets','prompts','prepare','prepare_video') or scope not in ('missing','all'):raise ValueError('无效准备操作或范围')
        if operation=='prepare_video' and body.get('confirm_generate') is not True:raise ValueError('生成视频需明确confirm_generate:true，可能产生费用')
        ids=body.get('shot_ids')
        if ids is None:ids=[s['id'] for s in p['shots']]
        if not isinstance(ids,list) or not ids or any(not isinstance(x,str) for x in ids) or len(set(ids))!=len(ids) or set(ids)-{s['id'] for s in p['shots']}:raise ValueError('请选择有效镜头')
        api.Q.reject_duplicate(pid,'text','project')
        return api.Q.enqueue(pid,{'id':api.uid(),'kind':'text','target':'project','target_id':'project','operation':'prepare_shots','preparation_operation':operation,
            'scope':scope,'shot_ids':ids,'title':{'assets':'全部匹配资产','prompts':'生成视频提示词','prepare':'一键准备镜头','prepare_video':'准备并生成视频'}[operation],
            'model':api.llm_model(p),'created':time.time(),'status':'queued','preparation_results':[]})

def generate_media(api,pid,j,sid,kind):
    with api.LOCK:
        api.Q.check(j)
        child=api.launch(pid,'shot',sid,kind)
        j.setdefault('child_job_ids',[]).append(child['id']);api.Q.persist(pid,j)
    return wait_child(api,pid,j,child)

def wait_child(api,pid,j,child):
    try:
        while True:
            api.Q.check(j)
            row=json.loads(api.job_path(pid,child['id']).read_text())
            if row['status'] in ('completed','failed','cancelled'):
                if row['status']!='completed':raise ValueError(row.get('error') or '媒体任务未完成')
                return
            api.Q.events[j['id']].wait(.5)
    except BaseException:
        api.Q.cancel(pid,child['id']);raise

def run(api,pid,j):
    completed={r['shot_id'] for r in j.get('preparation_results',[]) if r.get('status')=='completed'}
    results=j.setdefault('preparation_results',[])
    for index,sid in enumerate(j['shot_ids']):
        api.Q.check(j)
        if sid in completed:continue
        warnings=[];row={'shot_id':sid,'status':'failed'}
        try:
            steps=['assets'] if j['preparation_operation']=='assets' else ['prompts'] if j['preparation_operation']=='prompts' else ['assets','prompts']
            for step in steps:
                api.Q.check(j);j['preparation_progress']={'completed':index,'total':len(j['shot_ids']),'stage':step,'shot_id':sid};api.Q.persist(pid,j)
                p=api.load(pid);s=next((s for s in p['shots'] if s['id']==sid),None)
                if not s:raise ValueError('镜头已删除')
                if not str(s.get('description','')).strip():raise ValueError('请先填写剧情 · 动作 · 台词')
                exists=bool(s.get('asset_ids')) if step=='assets' else bool(re.sub(r'^\s*Duration:[^\n]*','',s.get('video_prompt','')).strip())
                stamp=s.get('preparation',{}).get(step)
                if j['scope']=='missing' and (current(p,s,step) or exists and not stamp):
                    if stamp:warnings.extend(stamp.get('warnings',[]))
                    continue
                # Manual changes after a successful preparation are preserved unless explicitly overwritten.
                if j['scope']=='missing' and stamp and stamp.get('output')!=output_hash(s,step):warnings.append('保留手动修改结果');continue
                before=copy.deepcopy(s);sig=fingerprint(p,s,step)
                changes,notes=(match_assets if step=='assets' else prompts)(api,j,p,s);warnings.extend(notes)
                if step=='prompts' and s.get('image_prompt','').strip():changes.pop('image_prompt',None)
                with api.LOCK:
                    api.Q.check(j)
                    def apply(latest):
                        shot=next((x for x in latest['shots'] if x['id']==sid),None)
                        if not shot or fingerprint(latest,shot,step)!=sig or output_hash(shot,step)!=output_hash(before,step):raise ValueError('本镜内容或资产已被修改，本次结果未覆盖，请重试')
                        shot.update(changes)
                        if step=='prompts':
                            for k in ('h3_plan','h3_rendered','director_plan','prompt_stale','prompt_mentions'):shot.pop(k,None)
                            shot.update(prompt_format='shot-description-v1',prompt_video_model=api.video_model(shot,latest),prompt_video_mode=api.video_mode(shot,latest))
                        shot.setdefault('preparation',{})[step]={'input':fingerprint(latest,shot,step),'output':output_hash(shot,step),'warnings':notes,'updated':time.time()}
                    api.update(pid,apply)
            if j['preparation_operation']=='prepare_video':
                if warnings:raise ValueError('存在待确认事项，已保存准备结果，暂不生成视频：'+'；'.join(warnings))
                p=api.load(pid);s=next(s for s in p['shots'] if s['id']==sid)
                if not s.get('video'):
                    j['preparation_progress']['stage']='video';api.Q.persist(pid,j)
                    if api.video_mode(s,p)=='first_frame' and not s.get('image'):generate_media(api,pid,j,sid,'image')
                    generate_media(api,pid,j,sid,'video')
            row.update(status='completed',warnings=warnings)
        except Exception as exc:
            api.Q.check(j);row.update(error=str(exc),warnings=warnings)
        results[:]=[r for r in results if r['shot_id']!=sid];results.append(row);j['preparation_progress']={'completed':index+1,'total':len(j['shot_ids']),'stage':'complete'};api.Q.persist(pid,j)
    return {'completed':sum(r['status']=='completed' for r in results),'failed':sum(r['status']=='failed' for r in results),'needs_review':sum(bool(r.get('warnings')) for r in results)}
