"""Versioned storyboard planning and official H3 prompt adaptation. No media generation."""
import copy,hashlib,json,math,re
from collections import Counter
REF_FIELDS=('subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music')
BASE_FIELDS=('integrated_multimodal_description','overall_soundscape','non_diegetic_music')
FIRST_FRAME='For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.'
def is_h3(model):return bool(re.search(r'minimax|(?:^|[-_])h3(?:[-_]|$)',str(model),re.I))
SCHEMES=('h3-structured-v2','huobao-native-v1')
DEFAULT_SCHEME='h3-structured-v2'
def project_scheme(p):
    scheme=p.get('storyboard_scheme') or DEFAULT_SCHEME
    if scheme not in SCHEMES:raise ValueError('分镜方案须为：'+'、'.join(SCHEMES))
    return scheme
def skill_bundle(api,p):
    scheme=project_scheme(p)
    if scheme=='h3-structured-v2':
        import h3_structured
        return h3_structured.bundle(api,p)
    bundle=api.prompt_skill_bundle('shotdesk-storyboard')
    if '<!-- huobao-native-v1 -->' in bundle['text']:
        import huobao_native
        return huobao_native.bundle(api,p)
    mode=api.video_mode({},p)
    model=p.get('video_model') or api.VIDEO_STRATEGIES[mode]['models'][0]
    bundle.update(video_mode=mode,video_model=model,format='h3-official-v1' if is_h3(model) else 'generic-v1')
    if '<!-- director-coverage-v1 -->' in bundle['text']:bundle.update(director_format='coverage-v1',prompt_language=p.get('prompt_language') or 'zh')
    if '<!-- segment-director-v1 -->' in bundle['text']:bundle['segment_director']=True
    if '<!-- source-owned-events -->' in bundle['text']:bundle['source_owned_events']=True
    if '<!-- planning:start -->' in bundle['text']:bundle['planning_format']='unified-references-v1'
    if '<!-- source-dialogue -->' in bundle['text']:bundle['dialogue_format']='source-lines-v1'
    if '<!-- group-dialogue -->' in bundle['text']:bundle['dialogue_format']='source-lines-v2'
    if '<!-- single-fragment -->' in bundle['text']:bundle['h3_batch_size']=1
    if '<!-- dialogue-events -->' in bundle['text']:bundle['h3_dialogue_events']=True
    if '<!-- fixed-dialogue-slots -->' in bundle['text']:bundle['h3_dialogue_slots']=True
    if '<!-- completion-first -->' in bundle['text']:bundle['resilient_storyboard']=True
    if '<!-- event-cut-times -->' in bundle['text']:bundle['h3_event_timing']=True
    if '<!-- stable-reference-labels -->' in bundle['text']:bundle['h3_stable_refs']=True
    if '<!-- contiguous-dialogue -->' in bundle['text']:bundle['dialogue_planning']='contiguous-v1'
    if '<!-- natural-performance -->' in bundle['text']:bundle.update(performance_format='natural-v1',prompt_language=p.get('prompt_language') or 'zh')
    if is_h3(model):
        root=api.ROOT/'docs/skills/shotdesk-storyboard/references';manifest=json.loads((root/'sources.json').read_text())
        name='h3-ref-en.txt' if mode in ('reference','video_reference') else 'h3-base-en.txt'
        sources=[x for x in manifest['sources'] if x['file'] in ('h3-official-SKILL.md',name)];texts=[]
        for source in sources:
            raw=(root/source['file']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=source['sha256']:raise ValueError('H3官方规范校验不一致，请检查来源记录')
            texts.append(raw.decode())
        if len(texts)!=2:raise ValueError('H3官方规范文件缺失')
        bundle.update(official_commit=manifest['commit'],official_sources=sources,official_text='\n\n'.join(texts))
    return bundle

class ModelOutputError(ValueError):pass
class OutputLengthError(ModelOutputError):pass
class PlanningDialogueError(ModelOutputError):pass

def output_schema(kind,assets=None,unified_refs=False,source_lines=None,dialogue_ranges=False):
    if kind=='planning':
        item={'type':'object','properties':{
            'title':{'type':'string','minLength':1},'description':{'type':'string','minLength':1},'image_prompt':{'type':'string','minLength':1},
            'duration':{'type':'number','exclusiveMinimum':0},'video_prompt':{'type':'string'},
            'dialogue':{'type':'array','items':{'type':'object','properties':{'speaker':{'type':'string','minLength':1},'text':{'type':'string','minLength':1},'delivery':{'type':'string'}},'required':['speaker','text']}},
            'asset_ids':{'type':'array','items':{'type':'string'}},'character_looks':{'type':'object','additionalProperties':{'type':'string'}},
            'action_seconds':{'type':'number','minimum':0},'pause_seconds':{'type':'number','minimum':0},'duration_basis':{'type':'string'}},
            'required':['title','description','image_prompt','duration','dialogue','asset_ids','character_looks']}
        if source_lines is not None:
            item['properties']['dialogue']={'type':'array','items':{'type':'object','properties':{'line_id':{'type':'string','enum':[line['id'] for line in source_lines]},'delivery':{'type':'string'}},'required':['line_id'],'additionalProperties':False}} if source_lines else {'type':'array','maxItems':0}
        if dialogue_ranges and source_lines is not None:
            item['properties'].pop('dialogue');item['required'].remove('dialogue')
            item['properties']['dialogue_through']={'enum':[line['id'] for line in source_lines]+[None]}
            item['properties']['dialogue_delivery']={'type':'object','properties':{line['id']:{'type':'string'} for line in source_lines},'additionalProperties':False}
            item['required'].append('dialogue_through')
        if assets is not None:
            ids=[a['id'] for a in assets if a.get('type') in ('角色','场景','道具')]
            item['properties']['asset_ids']={'type':'array','items':{'type':'string','enum':ids}} if ids else {'type':'array','maxItems':0}
            roles={a['id']:{'type':'string','enum':[l['id'] for l in a.get('looks',[])]} for a in assets if a.get('type')=='角色' and a.get('looks')}
            item['properties']['character_looks']={'type':'object','properties':roles,'additionalProperties':False}
        if unified_refs:
            for key in ('asset_ids','character_looks'):item['properties'].pop(key);item['required'].remove(key)
            choices=[]
            for asset in assets or []:
                if asset.get('type') not in ('角色','场景','道具'):continue
                lids=[l['id'] for l in asset.get('looks',[])] if asset.get('type')=='角色' else []
                choices.append({'type':'object','properties':{'asset_id':{'const':asset['id']},'look_id':{'enum':lids+[None]}},'required':['asset_id','look_id'],'additionalProperties':False})
            item['properties']['references']={'type':'array','items':{'anyOf':choices}} if choices else {'type':'array','maxItems':0}
            item['required'].append('references');item['additionalProperties']=False
        return {'type':'object','properties':{'analysis':{'type':'string'},'shots':{'type':'array','minItems':1,'items':item}},'required':['shots']}
    if kind in ('h3-reference','h3-base'):
        fields=('summary','detailed_description','overall_soundscape','non_diegetic_music') if kind=='h3-reference' else BASE_FIELDS
        properties={k:{'type':'string','minLength':1} for k in fields};properties['index']={'type':'integer','minimum':0}
        return {'type':'object','properties':{'prompts':{'type':'array','minItems':1,'items':{'type':'object','properties':properties,'required':['index',*fields],'additionalProperties':False}}},'required':['prompts']}
    if kind=='prompts':return {'type':'object','properties':{'prompts':{'type':'array','minItems':1,'items':{'type':'object','properties':{'index':{'type':'integer','minimum':0},'video_prompt':{'type':'string','minLength':1}},'required':['index','video_prompt']}}},'required':['prompts']}
    return None

def check_output_types(obj,kind):
    key='shots' if kind=='planning' else 'prompts';items=obj.get(key)
    if not isinstance(items,list) or not items:raise ValueError(key+'必须是非空对象列表')
    if kind=='planning' and 'analysis' in obj and not isinstance(obj['analysis'],str):raise ValueError('analysis必须是文字')
    for i,row in enumerate(items):
        path=f'{key}[{i}]'
        if not isinstance(row,dict):raise ValueError(path+'必须是对象，不能是文字或数字')
        if kind in ('h3-reference','h3-base'):
            fields=('summary','detailed_description','overall_soundscape','non_diegetic_music') if kind=='h3-reference' else BASE_FIELDS
            if type(row.get('index')) is not int or row['index']<0 or any(not isinstance(row.get(k),str) or not row[k].strip() for k in fields):raise ValueError(path+'缺少对应模式的H3文字字段')
            continue
        if kind=='prompts':
            if type(row.get('index')) is not int or row['index']<0 or not isinstance(row.get('video_prompt'),str) or not row['video_prompt'].strip():raise ValueError(path+'须包含整数index和文字video_prompt')
            continue
        if any(not isinstance(row.get(k),str) or not row[k].strip() for k in ('title','description','image_prompt')):raise ValueError(path+'缺少文字标题/描述/静态构图')
        if not isinstance(row.get('dialogue'),list) or any(not isinstance(line,dict) or any(not isinstance(line.get(k),str) or not line[k].strip() for k in ('speaker','text')) for line in row['dialogue']):raise ValueError(path+'.dialogue须为含speaker/text对象的列表，无台词填[]')
        if not isinstance(row.get('asset_ids'),list) or any(not isinstance(a,str) for a in row['asset_ids']):raise ValueError(path+'.asset_ids须为ID文字列表')
        if not isinstance(row.get('character_looks'),dict) or any(not isinstance(v,str) for v in row['character_looks'].values()):raise ValueError(path+'.character_looks须为角色ID到造型ID的对象')
        for name in ('duration','action_seconds','pause_seconds'):
            value=row.get(name,0)
            if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or value<0 or (name=='duration' and value==0):raise ValueError(path+'.'+name+'须为有效秒数')
        if 'video_prompt' in row and not isinstance(row['video_prompt'],str):raise ValueError(path+'.video_prompt须为文字')

def check_planning_bindings(obj,assets):
    known={a['id']:a for a in assets}
    for index,row in enumerate(obj['shots'],1):
        prefix='本段镜头'+str(index)+'（'+row['title']+'）'
        ids=row['asset_ids']
        for aid in ids:
            if aid not in known or known[aid].get('type') not in ('角色','场景','道具'):raise ValueError(prefix+'引用不存在的资产ID：'+aid)
        for aid,lid in row['character_looks'].items():
            role=known.get(aid)
            if not role or role.get('type')!='角色':raise ValueError(prefix+'的造型键不是角色ID：'+aid)
            if aid not in ids:raise ValueError(prefix+'为未关联角色'+role.get('name',aid)+'指定了造型，请核对本镜实际出场角色')
            if not any(l['id']==lid for l in role.get('looks',[])):
                allowed='、'.join(l.get('name',l['id'])+'='+l['id'] for l in role.get('looks',[])) or '无可选造型，请省略该角色的造型键'
                raise ValueError(prefix+'：'+role.get('name',aid)+'引用不属于本人的造型ID '+lid+'；允许：'+allowed)

def normalize_references_plan(obj,assets,task,unified=False):
    known={a['id']:a for a in assets};obj=copy.deepcopy(obj)
    for row in obj.get('shots',[]) if isinstance(obj.get('shots'),list) else []:
        if not isinstance(row,dict):continue
        if unified:
            refs=row.get('references')
            if not isinstance(refs,list):raise ValueError('每镜须提供统一references列表，不再同时维护asset_ids与character_looks')
            if 'asset_ids' in row or 'character_looks' in row:raise ValueError('只输出references，由平台生成asset_ids/character_looks')
            ids=[];looks={}
            for ref in refs:
                if not isinstance(ref,dict) or set(ref)!={'asset_id','look_id'}:raise ValueError('references每项须含asset_id和look_id（跟随默认填null）')
                aid=ref['asset_id'];lid=ref['look_id']
                if not isinstance(aid,str) or aid not in known:raise ValueError('references引用未知资产')
                a=known[aid]
                if lid is not None and (a.get('type')!='角色' or not isinstance(lid,str) or not any(l['id']==lid for l in a.get('looks',[]))):raise ValueError('references中的造型不属于角色 '+a.get('name',aid))
                if aid in ids:
                    if looks.get(aid)!=lid:raise ValueError('同一角色重复引用了不同造型，请确定本镜造型或拆镜')
                    continue
                ids.append(aid)
                if lid is not None:looks[aid]=lid
            row.pop('references');row.update(asset_ids=ids,character_looks=looks)
        else:
            ids=row.get('asset_ids');looks=row.get('character_looks')
            if not isinstance(ids,list) or not isinstance(looks,dict):continue
            for aid,lid in list(looks.items()):
                a=known.get(aid)
                if aid not in ids and a and a.get('type')=='角色' and any(l['id']==lid for l in a.get('looks',[])):
                    del looks[aid]
                    task.setdefault('storyboard_repairs',[]).append({'title':row.get('title'),'action':'remove_inactive_look','asset_id':aid,'look_id':lid})
    return obj

def stage_skill(text,stage):
    marker='<!-- '+stage+':start -->';end='<!-- '+stage+':end -->'
    if marker not in text or end not in text:return text
    common=text.split('<!-- planning:start -->',1)[0]
    return common+'\n'+text.split(marker,1)[1].split(end,1)[0]

STAGE_DIRECTION=re.compile(r'[（(]\s*((?:点头|摇头|沉默|不说话|停顿|叹气|微笑|笑|转身|抬头|低头|挥手|招手|起身|坐下))\s*[）)]')

def script_dialogue_lines(script,assets,include_groups=False):
    names=sorted({a.get('name') for a in assets if a.get('type')=='角色' and a.get('name')},key=len,reverse=True)
    if not names:return []
    pattern=re.compile(r'^\s*('+ '|'.join(re.escape(n) for n in names)+r')(?:（[^）]*）|\([^)]*\))?\s*[:：]\s*(.+?)\s*$')
    lines=[];offset=0;previous=''
    for raw in script.splitlines(keepends=True):
        match=pattern.match(raw.rstrip('\r\n'))
        if match and not STAGE_DIRECTION.fullmatch(match[2]):lines.append({'id':'D'+str(len(lines)+1),'speaker':match[1],'text':match[2],'start':offset})
        elif include_groups:
            group=re.match(r'^\s*([^：:\n]{1,40})[:：]\s*(.+?)\s*$',raw.rstrip('\r\n'))
            if group:
                heading=group[1];members=[n for n in names if n in heading]
                explicit=len(members)>1 and re.fullmatch(r'(?:'+ '|'.join(re.escape(n) for n in names)+r'|[、，,和与及\s])+',heading)
                count={'两人':2,'二人':2,'三人':3}.get(heading)
                if count or heading in ('众人','大家'):
                    members=sorted([n for n in names if n in previous],key=previous.index)
                    explicit=len(members)==count if count else len(members)>1
                if explicit:
                    if not count:members=sorted(members,key=heading.index) if all(n in heading for n in members) else members
                    lines.append({'id':'D'+str(len(lines)+1),'speaker':'、'.join(members),'members':members,'text':group[2],'start':offset})
        if raw.strip():previous=raw.strip()
        offset+=len(raw)
    return lines

def repair_duplicate_dialogue(obj,ledger,task):
    occurrences={}
    for row in obj.get('shots',[]) if isinstance(obj.get('shots'),list) else []:
        if not isinstance(row,dict) or not isinstance(row.get('dialogue'),list):continue
        for i,line in enumerate(row['dialogue']):
            if isinstance(line,dict) and isinstance(line.get('line_id'),str):occurrences.setdefault(line['line_id'],[]).append((row,i))
    def words(value):return re.sub(r'[^\w\u3400-\u9fff]','',value)
    remove={}
    for lid,items in occurrences.items():
        if len(items)<2 or lid not in ledger:continue
        text=words(ledger[lid]['text'])
        anchored=[(row,i) for row,i in items if text and any(text==words(quote) for quote in re.findall(r'[“\"]([^”\"]+)[”\"]',str(row.get('description',''))))]
        if len(anchored)!=1:continue
        owner,pos=anchored[0]
        for row,i in items:
            if row is owner and i==pos:continue
            remove.setdefault(id(row),set()).add(i)
            task.setdefault('storyboard_repairs',[]).append({'action':'remove_duplicate_dialogue','line_id':lid,'title':row.get('title'),'kept_title':owner.get('title')})
    for row in obj.get('shots',[]) if isinstance(obj.get('shots'),list) else []:
        if isinstance(row,dict) and id(row) in remove:row['dialogue']=[line for i,line in enumerate(row['dialogue']) if i not in remove[id(row)]]

def repair_dialogue(obj,script,task,source_lines=None):
    obj=copy.deepcopy(obj);compact=re.sub(r'\s+','',script);ledger={l['id']:l for l in source_lines or []};used=[]
    if source_lines is not None:repair_duplicate_dialogue(obj,ledger,task)
    for row in obj.get('shots',[]) if isinstance(obj.get('shots'),list) else []:
        if not isinstance(row,dict) or not isinstance(row.get('dialogue'),list):continue
        kept=[]
        for line in row['dialogue']:
            if not isinstance(line,dict):kept.append(line);continue
            if 'line_id' in line:
                if not isinstance(line['line_id'],str):raise ValueError('对白line_id须为文字编号')
                source=ledger.get(line['line_id'])
                if not source:raise ValueError('对白编号不属于本段剧本：'+str(line['line_id']))
                used.append(source['id'])
                kept.append(dict(speaker=source['speaker'],text=source['text'],delivery=line.get('delivery',''),**({'members':source['members']} if source.get('members') else {})))
                continue
            text=line.get('text');speaker=line.get('speaker')
            action=STAGE_DIRECTION.fullmatch(text) if isinstance(text,str) else None
            if not isinstance(speaker,str):kept.append(line);continue
            # Only reclassify an explicitly evidenced action, never merely parenthesised speech.
            spoken=any(isinstance(text,str) and text in l['text'] for l in script_dialogue_lines(script,[{'type':'角色','name':speaker}])) if speaker else False
            if action and speaker and not spoken and (re.search(re.escape(speaker)+r'[^。！？\n：:]{0,12}'+re.escape(action[1]),script) or re.search(re.escape(speaker)+r'[^：:\n]{0,40}\n\s*'+re.escape(action[1]),script)):
                note=speaker+action[1]
                if not isinstance(row.get('description',''),str):raise ValueError('分镜动作描述须为文字')
                if action[1] not in row.get('description',''):row['description']=row.get('description','')+'；动作：'+note+'。'
                record={'title':row.get('title'),'action':'stage_direction_to_action','speaker':speaker,'text':text}
                if record not in task.setdefault('storyboard_repairs',[]):task['storyboard_repairs'].append(record)
                continue
            if source_lines is not None:
                matches=[l for l in source_lines if l['speaker']==speaker and l['text']==text]
                if not matches:raise ValueError('对白必须选择本段原文编号，不得新增或改写：'+str(text)[:60])
                source=matches[0];used.append(source['id']);line=dict(speaker=source['speaker'],text=source['text'],delivery=line.get('delivery',''))
            kept.append(line)
        row['dialogue']=kept
        # Check before accepting a segment, including legacy tasks.
        for line in kept:
            if isinstance(line,dict) and isinstance(line.get('text'),str) and re.sub(r'\s+','',line['text']) not in compact:raise ValueError('分镜对白与剧本原文不符：'+line['text'][:60])
    if source_lines is not None and used!=[l['id'] for l in source_lines]:
        expected=[l['id'] for l in source_lines];counts=Counter(used);missing=[lid for lid in expected if not counts[lid]];duplicates=[lid for lid,n in counts.items() if n>1]
        details=[]
        if missing:details.append('缺少 '+','.join(missing))
        if duplicates:details.append('重复 '+','.join(duplicates))
        if not details:details.append('顺序与原剧本不一致')
        raise ValueError('本段对白需要修正：'+'；'.join(details))
    return obj

def expand_dialogue_ranges(obj,source_lines,task):
    """Each source line is consumed once, in order. The model only chooses shot boundaries."""
    if not isinstance(obj.get('shots'),list):raise PlanningDialogueError('分镜规划须返回shots')
    ids=[line['id'] for line in source_lines];cursor=0
    for row in obj['shots']:
        if not isinstance(row,dict):raise PlanningDialogueError('分镜条目须为对象')
        if 'dialogue' in row:raise PlanningDialogueError('只输出dialogue_through，不再逐句列dialogue')
        if 'dialogue_through' not in row:raise PlanningDialogueError('镜头缺少dialogue_through，纯动作填null')
        boundary=row.pop('dialogue_through');delivery=row.pop('dialogue_delivery',{})
        if not isinstance(delivery,dict) or any(k not in ids or not isinstance(v,str) for k,v in delivery.items()):raise PlanningDialogueError('dialogue_delivery须为原文编号到语气的对象')
        if boundary is None:end=cursor
        elif not isinstance(boundary,str) or boundary not in ids:raise PlanningDialogueError('台词终点不属于本段原文')
        else:
            end=ids.index(boundary)+1
            if end<cursor:raise PlanningDialogueError('台词终点倒退，需重新确定本段镜头边界')
        row['dialogue']=[{'line_id':line['id'],'delivery':delivery.get(line['id'],'')} for line in source_lines[cursor:end]]
        cursor=end
    if cursor!=len(ids):raise PlanningDialogueError('本段末尾台词尚未安排，请完整规划到 '+ids[-1])
    return obj

def ask(api,task,messages,max_tokens=12000,output_kind=None,planning_assets=None,unified_refs=False,script=None,source_lines=None,expected_indices=None,field_limits=None,dialogue_count=None,event_duration=None,dialogue_ranges=False,dialogue_slots=False):
    messages=copy.deepcopy(messages)
    schema=output_schema(output_kind,planning_assets,unified_refs,source_lines,dialogue_ranges)
    if schema:schema['additionalProperties']=False
    if schema and field_limits:
        props=schema['properties']['prompts']['items']['properties']
        for key,limit in field_limits.items():
            if key in props:props[key]['maxLength']=limit
    if schema and dialogue_count is not None:
        item=schema['properties']['prompts']['items'];key='detailed_description' if output_kind=='h3-reference' else 'integrated_multimodal_description'
        limit=item['properties'].pop(key).get('maxLength',6000);item['required'].remove(key)
        item['properties']['events']={'type':'array','minItems':1,'maxItems':max(12,dialogue_count*2+2),'items':{'type':'object','properties':{'visual':{'type':'string','minLength':1,'maxLength':limit},'dialogue_indices':{'type':'array','items':{'type':'integer','minimum':0,'maximum':max(0,dialogue_count-1)}}},'required':['visual','dialogue_indices'],'additionalProperties':False}}
        if not dialogue_count:item['properties']['events']['items']['properties']['dialogue_indices']['maxItems']=0
        item['required'].append('events')
        if event_duration is not None:
            event=item['properties']['events']['items'];event['properties']['cut_at']={'anyOf':[{'type':'null'},{'type':'number','exclusiveMinimum':0,'exclusiveMaximum':event_duration}]}
            event['required'].append('cut_at')
    if schema and dialogue_count is not None and dialogue_slots:
        event=copy.deepcopy(item['properties']['events']['items']);event['properties'].pop('dialogue_indices');event['required'].remove('dialogue_indices')
        nullable={'anyOf':[{'type':'null'},event]}
        lines={f'line_{i}':copy.deepcopy(event) for i in range(dialogue_count)}
        item['properties']['events']={'type':'object','properties':{'opening':nullable if dialogue_count else event,'dialogue':{'type':'object','properties':lines,'required':list(lines),'additionalProperties':False},'closing':nullable},'required':['opening','dialogue','closing'],'additionalProperties':False}
    if schema and expected_indices is not None:
        prompts=schema['properties']['prompts'];prompts.update(minItems=len(expected_indices),maxItems=len(expected_indices))
        prompts['items']['properties']['index']={'type':'integer','enum':list(expected_indices)}
    output_format={'type':'json_schema','json_schema':{'name':'storyboard_'+output_kind,'schema':schema}} if schema else {'type':'json_object'}
    for attempt in range(2):
        response=api.Q.text_request({'model':task['model'],'messages':messages,'temperature':.25,'max_tokens':max_tokens,'response_format':output_format,'chat_template_kwargs':{'enable_thinking':False}},task)
        try:
            choice=response['choices'][0]
            if not isinstance(choice['message']['content'],str):raise TypeError('content不是文字')
        except (KeyError,IndexError,TypeError) as exc:raise ModelOutputError('模型返回缺少有效正文') from exc
        limited=choice.get('finish_reason')=='length'
        raw=re.sub(r'<think>.*?</think>','',choice['message']['content'],flags=re.S)
        if limited:
            diagnostics=task.setdefault('storyboard_json_diagnostics',[])
            diagnostics.append({'attempt':attempt+1,'error':'output_length_limit','kind':output_kind,'indices':expected_indices,'response':raw[:50000]});del diagnostics[:-4]
        try:
            obj=json.loads(raw[raw.find('{'):raw.rfind('}')+1])
            if not isinstance(obj,dict):raise ValueError('须返回JSON对象')
            if dialogue_ranges and source_lines is not None:obj=expand_dialogue_ranges(obj,source_lines,task)
            if output_kind=='planning' and script is not None:obj=repair_dialogue(obj,script,task,source_lines)
            if output_kind=='planning' and planning_assets is not None:obj=normalize_references_plan(obj,planning_assets,task,unified_refs)
            if dialogue_count is not None and dialogue_slots:obj=compile_dialogue_slots(obj,dialogue_count)
            if dialogue_count is not None:obj=compile_dialogue_events(obj,output_kind,dialogue_count,event_duration)
            if output_kind:check_output_types(obj,output_kind)
            if output_kind=='planning' and planning_assets is not None:check_planning_bindings(obj,planning_assets)
            if limited:task.setdefault('storyboard_repairs',[]).append({'action':'complete_json_at_output_limit','indices':expected_indices})
            return obj
        except (json.JSONDecodeError,ValueError) as exc:
            if limited:
                if output_kind in ('h3-reference','h3-base') and attempt==0:
                    task['storyboard_length_retries']=task.get('storyboard_length_retries',0)+1
                    messages.append({'role':'user','content':'上一轮超过输出上限且结果不完整。重新简洁编写本镜：保留全部原台词占位、主体/动作、机位和声音，删去反复说明与重复形容，只返回规定JSON。不要续写截断文本，不复述整部剧情。'})
                    continue
                location='第'+str(expected_indices[0]+1)+'镜视频提示词' if expected_indices else '分镜规划'
                raise OutputLengthError(location+'输出仍达到长度限制；已保留检查点，原分镜未覆盖') from exc
            diagnostics=task.setdefault('storyboard_json_diagnostics',[])
            diagnostics.append({'attempt':attempt+1,'error':str(exc),'response':raw})
            del diagnostics[:-4]
            task['storyboard_json_repairs']=task.get('storyboard_json_repairs',0)+int(attempt==0)
            if attempt:
                if dialogue_ranges and isinstance(exc,PlanningDialogueError):raise exc
                if dialogue_slots:raise ModelOutputError('视频提示词结构自动修正一次后仍未通过：'+str(exc)) from exc
                raise ModelOutputError('分镜校验失败，自动修正一次后字段结构或资产造型绑定仍不正确；原分镜未覆盖：' +str(exc)) from exc
            if dialogue_slots:
                messages.append({'role':'user','content':'当前镜头结构需修正：'+str(exc)+'。按schema重新返回固定events对象：opening、dialogue、closing。dialogue必须含所有line_0至line_'+str(dialogue_count-1)+'位置，不输出dialogue_indices。每个位置只写visual和cut_at，不复写台词或标签；opening/closing可为null。只修当前镜头。'})
                continue
            if dialogue_ranges:
                messages.append({'role':'user','content':'本段规划检查指出：'+str(exc)+'。重新返回本段完整规划，保持原剧本，只输出dialogue_through作为每镜台词终点（纯动作null），不要输出dialogue列表。程序按原文顺序分配尚未使用的台词，末尾必须覆盖本段最后一句。按错误调整镜头边界，允许增减镜头，不复制上轮错误结果。'})
                continue
            messages.extend([{'role':'assistant','content':raw},{'role':'user','content':'上一轮JSON或字段结构检查失败：'+str(exc)+'。按指定schema修正JSON与字段类型、逗号、双引号和字符串换行转义，shots/prompts的每项必须是完整对象，dialogue每项须有speaker/text，保留本轮剧情、原台词及索引。真实且正确的资产ID保留；按校验指出的问题修正无效ID或角色/造型绑定，只能选择目录中属于该角色的造型，不猜测或把错误造型换成默认。不要新增或删减镜头条目；仅返回完整JSON对象，不用代码围栏或解释。'}])

def timing(api,row,script):
    lines=row.get('dialogue')
    if not isinstance(lines,list):raise ValueError('分镜须提供逐句dialogue，无对白也须返回[]')
    speech=0
    for line in lines:
        if not isinstance(line,dict) or any(not isinstance(line.get(k),str) or not line[k].strip() for k in ('speaker','text')):raise ValueError('分镜对白缺少说话人或原文')
        text=line['text']
        if re.sub(r'\s+','',text) not in re.sub(r'\s+','',script):raise ValueError('分镜对白与剧本原文不符：'+text[:60])
        speech+=len(re.findall(r'[\u3400-\u9fff\d]',text))/4+len(re.findall(r'[A-Za-z]+',text))/2.5
    def seconds(key):
        n=row.get(key,0)
        if isinstance(n,bool) or not isinstance(n,(float,int)) or not math.isfinite(n) or n<0:raise ValueError(key+'须为非负有限秒数')
        return float(n)
    action=seconds('action_seconds');pause=max(seconds('pause_seconds'),max(0,len(lines)-1)*.25)
    proposed=api.duration_value(row.get('duration',4));minimum=max(1,speech+action+pause);duration=math.ceil(max(proposed,minimum)*10)/10
    return duration,{'method':'dialogue-budget-v1','chinese_chars_per_second':4,'english_words_per_second':2.5,'speech_seconds':round(speech,2),'extra_action_seconds':action,'pause_seconds':pause,'minimum_seconds':round(minimum,2),'proposed_duration':proposed,'adjusted':duration>proposed,'basis':str(row.get('duration_basis','')),'verified_by_audio':False}

def sections(text,reference):
    fields=REF_FIELDS if reference else BASE_FIELDS
    matches=list(re.finditer(r'(?m)^('+('|'.join(fields))+r')\s*:',text))
    if tuple(x[1] for x in matches)!=fields:raise ValueError('H3字段缺失、重复或顺序错误：'+', '.join(fields))
    wrong='integrated_multimodal_description:' if reference else 'subject_definitions:'
    if wrong in text:raise ValueError('H3资产参考与基础模式格式混用')
    parts={m[1]:text[m.end():matches[i+1].start() if i+1<len(matches) else len(text)].strip() for i,m in enumerate(matches)}
    if any(not value for value in parts.values()):raise ValueError('H3存在空段落，无背景音乐时写N/A')
    return parts

def cut_markers(main):
    masked=re.sub(r'<d>.*?</d>|"[^"\n]*"|“[^”\n]*”',lambda m:' '*len(m[0]),main,flags=re.S)
    return list(re.finditer(r'\[Shot (\d+)\]',masked))

def validate(api,p,shot,text,mode,dialogue=True):
    text=api.DURATION_LINE.sub('',text).strip();reference=mode in ('reference','video_reference');parts=sections(text,reference)
    if reference:
        if re.search(r'<(?:Subject|Picture)\s+\d+>',text):raise ValueError('资产参考草稿须用@资产，不手写Subject或Picture编号')
        refs=api.scan_prompt_mentions(p,shot,parts['subject_definitions'],True)
        if {r['asset_id'] for r in refs}!=set(shot['asset_ids']) or len(refs)!=len(set(shot['asset_ids'])):raise ValueError('H3主体定义须逐一覆盖本镜关联资产，不可重复')
        for line in parts['subject_definitions'].splitlines():
            if line.strip()!='N/A' and (not line.lstrip().startswith('@') or len(api.scan_prompt_mentions(p,shot,line,True))!=1):raise ValueError('H3主体定义每行须定义一个@资产')
    else:
        if api.scan_prompt_mentions(p,shot,text,True):raise ValueError('此视频模式不传入@资产图片，请使用普通人物名称')
        if mode=='first_frame' and not text.startswith(FIRST_FRAME+'\n\n'):raise ValueError('H3首帧提示词须先写官方0秒对齐行，再空一行')
    main=parts['detailed_description' if reference else 'integrated_multimodal_description'];marks=cut_markers(main)
    if not marks or [int(m[1]) for m in marks]!=list(range(1,len(marks)+1)):raise ValueError('H3须从[Shot 1]连续编号')
    if re.match(r'\s+At \d',main[marks[0].end():]):raise ValueError('H3首镜不标切镜时间')
    residue=re.sub(r'<d>.*?</d>|"[^"]*"','',main,flags=re.S)
    for ref in reversed(api.scan_prompt_mentions(p,shot,residue,True)):residue=residue[:ref['start']]+residue[ref['end']:]
    if shot.get('prompt_language','en')=='en' and len(re.findall(r'[\u3400-\u9fff]',residue))>5 and len(re.findall(r'[\u3400-\u9fff]',residue))>2*len(re.findall(r'[A-Za-z]+',residue)):raise ValueError('H3画面说明须用英文，中文对白保留在<d>内')
    if re.search(r'<(?:Audio|Video)\s+\d+>',text):raise ValueError('本次分镜未绑定音视频参考，不能虚构Audio或Video引用')
    last=0
    for mark in marks[1:]:
        cut=re.match(r'\s+At (\d{2}):(\d{2})\.(\d{3}),',main[mark.end():])
        if not cut:raise ValueError('H3后续镜头缺少At MM:SS.mmm切点')
        t=int(cut[1])*60+int(cut[2])+int(cut[3])/1000
        if int(cut[2])>=60 or not last<t<shot['duration']:raise ValueError('H3切点须递增且在片段时长内')
        last=t
    if dialogue:
        blocks=list(re.finditer(r'<d>(.*?)</d>',main,re.S));lines=shot.get('dialogue',[])
        if len(blocks)!=len(lines):raise ValueError('H3台词数量与规划不一致')
        speakers={};prev=0
        for line,block in zip(lines,blocks):
            spoken=re.fullmatch(r'\[[^\]\n]+\]\s*(.*)',block[1],re.S)
            if not spoken or re.sub(r'\s+','',spoken[1])!=re.sub(r'\s+','',line['text']):raise ValueError('H3须逐字保留台词，并在<d>内标注语言')
            prefix=main[prev:block.start()]
            if shot.get('director_plan',{}).get('version')=='coverage-v1':
                names=line.get('members') or [line['speaker']];expected=[speakers.setdefault(name,len(speakers)+1) for name in names];sid=expected[0];groups=re.findall(r'\((S\d+(?:,S\d+)*)\)',prefix)
                if not groups or [int(v) for v in re.findall(r'S(\d+)',groups[-1])]!=expected:raise ValueError('H3说话人S编号与本片段开口顺序不一致')
            else:
                sid=speakers.setdefault(line['speaker'],len(speakers)+1);ids=re.findall(r'\(S(\d+)\)',prefix)
                if not ids or int(ids[-1])!=sid:raise ValueError('H3说话人S编号与本片段开口顺序不一致')
            if reference:
                asset=next((a for a in p['assets'] if a.get('type')=='角色' and a.get('name')==line['speaker']),None)
                if asset and not any(r['asset_id']==asset['id'] and re.search(re.escape('@'+r['label'])+r'\s*\(S'+str(sid)+r'\)',prefix) for r in api.scan_prompt_mentions(p,shot,prefix,True)):raise ValueError('H3台词未绑定对应角色@引用及S编号')
            prev=block.end()
    return text

def normalize_cut_labels(text,reference,task=None,title=''):
    parts=sections(text,reference);key='detailed_description' if reference else 'integrated_multimodal_description';main=parts[key];count=0;changed=False
    # Spoken/quoted text is content, not editable cut syntax.
    chunks=re.split(r'(<d>.*?</d>|"[^"\n]*"|“[^”\n]*”)',main,flags=re.S)
    def replace(match):
        nonlocal count,changed
        count+=1;label='[Shot '+str(count)+']';changed=changed or match[0]!=label;return label
    for i in range(0,len(chunks),2):chunks[i]=re.sub(r'\[Shot\s+\d+\]',replace,chunks[i],flags=re.I)
    if count==0:
        masked=re.sub(r'<d>.*?</d>|"[^"\n]*"|“[^”\n]*”','',main,flags=re.S)
        if re.search(r'\bAt\s+\d{2}:\d{2}\.\d{3}',masked):raise ValueError('正文缺少切镜标签但包含切点时间，不能自动推断镜头结构')
        updated='[Shot 1] '+main;count=1;changed=True;action='add_initial_cut_label'
    else:updated=''.join(chunks);action='renumber_internal_cuts'
    if not changed:return text
    if task is not None:task.setdefault('storyboard_repairs',[]).append({'action':action,'title':title,'cuts':count})
    return text.replace(main,updated,1)

def compile_prompt(api,p,shot,text,inputs):
    mode=api.video_mode(shot,p)
    if shot.get('prompt_video_mode')!=mode:raise ValueError('视频方案已改变，请按当前方案重新编写H3提示词')
    text=validate(api,p,shot,text,mode,dialogue=False)
    if mode not in ('reference','video_reference'):return text
    parts=sections(text,True);defs=parts['subject_definitions'];sources={v.get('asset_id'):i+1 for i,v in enumerate(inputs)}
    lines=[]
    for line in defs.splitlines():
        refs=api.scan_prompt_mentions(p,shot,line,True)
        if refs:line+=f" Source: <Picture {sources[refs[0]['asset_id']]}>."
        lines.append(line)
    text=text.replace(defs,'\n'.join(lines),1)
    for r in reversed(api.scan_prompt_mentions(p,shot,text,True)):
        if r['asset_id'] not in sources:raise ValueError('H3主体缺少实际参考图片')
        text=text[:r['start']]+f"<Subject {sources[r['asset_id']]}>"+text[r['end']:]
    return text.replace('@@','@')

def assemble_h3(api,p,shot,entry,mode):
    chinese=shot.get('prompt_language')=='zh'
    if mode in ('reference','video_reference'):
        assets={a['id']:a for a in p['assets']};defs=[];keep=[]
        for slot in reference_slots(api,p,shot):
            label=slot['label'];kind=assets[slot['asset_id']]['type']
            noun={'角色':'character in the selected look','场景':'location','道具':'object'}[kind]
            defs.append(label+(' 为参考'+{'角色':'角色及所选造型','场景':'场景','道具':'道具'}[kind]+'。' if chinese else ' is the referenced '+noun+'.'))
            keep.append(label+(': fully_preserved - 保留参考'+{'角色':'身份与所选造型','场景':'空间布局与外观','道具':'形状与材质'}[kind]+'。' if chinese else ': fully_preserved - Preserve the reference '+{'角色':'identity and selected outfit','场景':'spatial layout and appearance','道具':'shape and material'}[kind]+'.'))
        summary=entry['summary'].strip()
        if not summary.startswith('[reference generation]'):summary='[reference generation] '+summary
        parts={'subject_definitions':'\n'.join(defs) or 'N/A','summary':summary,'retention_analysis':'\n'.join(keep) or 'N/A',**{k:entry[k] for k in ('detailed_description','overall_soundscape','non_diegetic_music')}}
    else:parts={k:entry[k] for k in BASE_FIELDS}
    text='\n\n'.join(k+':\n'+v.strip() for k,v in parts.items())
    return FIRST_FRAME+'\n\n'+text if mode=='first_frame' else text

def progress(api,task,stage,completed,total):
    task['storyboard_progress']={'stage':stage,'completed':completed,'total':total}
    if task.get('id') and task.get('project_id'):
        with api.LOCK:
            api.Q.check(task);task['phase']='storyboard_'+stage;api.Q.persist(task['project_id'],task)

def reference_slots(api,p,shot):
    catalog=api.mention_catalog(p);assets={a['id']:a for a in p['assets']};slots=[]
    for i,aid in enumerate(shot['asset_ids'],1):
        a=assets[aid];look=shot.get('character_looks',{}).get(aid) or a.get('default_look_id')
        label=next((r['label'] for r in catalog if r['asset_id']==aid and r.get('look_id')==look),None)
        if label is None:label=next(r['label'] for r in catalog if r['asset_id']==aid)
        slots.append({'subject':f'<Subject {i}>','picture':f'<Picture {i}>','label':'@'+label,'asset_id':aid,'look_id':look})
    return slots

def normalize_references(text,slots):
    """Translate model-visible official slot numbers back to stable draft mentions."""
    if not re.search(r'<(?:Subject|Picture)\s+\d+>',text):return text
    mapping={i+1:slot['label'] for i,slot in enumerate(slots)}
    for tag in re.finditer(r'<(?:Subject|Picture)\s+(\d+)>',text):
        if int(tag[1]) not in mapping:raise ValueError('H3引用编号不在本镜提供的reference_slots中')
    parts=sections(text,True);defs=parts['subject_definitions'];lines=[]
    for line in defs.splitlines():
        subject=re.match(r'^\s*<Subject\s+(\d+)>',line)
        if subject:
            pics=[int(x) for x in re.findall(r'<Picture\s+(\d+)>',line)]
            if any(i!=int(subject[1]) for i in pics):raise ValueError('H3主体定义的图片来源与reference_slots不一致')
        # The compiler restores the exact source at submission time; do not retain stale numbers.
        line=re.sub(r'(?i)\bsource\s*:\s*<Picture\s+\d+>\.?','',line)
        line=re.sub(r'(?i)\b(?:from|in|shown in|referenced from|based on)\s*<Picture\s+\d+>','',line)
        line=re.sub(r'<Picture\s+\d+>','',line)
        lines.append(re.sub(r'\s+([,.])',r'\1',line.strip()))
    text=text.replace(defs,'\n'.join(lines),1)
    return re.sub(r'<(?:Subject|Picture)\s+(\d+)>',lambda m:mapping[int(m[1])],text)

def compile_dialogue_slots(obj,count):
    """Compile required named source-utterance slots into ordered events; model never lists indices."""
    obj=copy.deepcopy(obj)
    if not isinstance(obj,dict) or not isinstance(obj.get('prompts'),list):raise ValueError('缺少prompts对象列表')
    for row in obj['prompts']:
        if not isinstance(row,dict) or not isinstance(row.get('events'),dict):raise ValueError('events须为固定台词位置对象')
        layout=row['events'];lines=layout.get('dialogue');keys={f'line_{i}' for i in range(count)}
        if set(layout)!={'opening','dialogue','closing'} or not isinstance(lines,dict) or set(lines)!=keys:raise ValueError('固定台词位置缺失或包含未知位置')
        events=[]
        def add(value,indices):
            if not isinstance(value,dict) or set(value)!={'visual','cut_at'}:raise ValueError('每个画面位置只含visual和cut_at')
            events.append(dict(value,dialogue_indices=indices))
        if layout['opening'] is not None:add(layout['opening'],[])
        for i in range(count):add(lines[f'line_{i}'],[i])
        if layout['closing'] is not None:add(layout['closing'],[])
        if not events:raise ValueError('无对白镜头须提供opening画面')
        row['events']=events
    return obj

def compile_dialogue_events(obj,kind,count,duration=None):
    """Model positions immutable source lines; program owns utterance syntax."""
    obj=copy.deepcopy(obj)
    if not isinstance(obj,dict) or not isinstance(obj.get('prompts'),list):raise ValueError('须返回prompts事件列表')
    key='detailed_description' if kind=='h3-reference' else 'integrated_multimodal_description'
    for row in obj['prompts']:
        if not isinstance(row,dict) or not isinstance(row.get('events'),list) or not row['events']:raise ValueError('缺少画面events')
        used=[];chunks=[];cut_number=1;last_cut=0
        for event_index,event in enumerate(row.pop('events')):
            if not isinstance(event,dict) or not isinstance(event.get('visual'),str) or not event['visual'].strip() or not isinstance(event.get('dialogue_indices'),list):raise ValueError('事件须包含visual和dialogue_indices')
            visual=event['visual'];indices=event['dialogue_indices']
            if re.search(r'</?d>|\{\{dialogue:|\(S\d+\)',visual):raise ValueError('visual只写画面，不写台词标签、占位或S编号')
            if any(type(i) is not int or not 0<=i<count for i in indices):raise ValueError('事件引用未知台词编号')
            if duration is not None:
                if 'cut_at' not in event:raise ValueError('事件缺少cut_at；连续动作填null，真正切镜填秒数')
                cut=event['cut_at']
                if cut is not None and (type(cut) not in (float,int) or not math.isfinite(cut) or event_index==0 or not last_cut<cut<duration):raise ValueError('cut_at须为片段内递增切点；首事件与连续动作填null')
                # An event is not a cut. Ignore redundant leading model labels; structured cut_at owns timing.
                visual=re.sub(r'^\s*\[Shot\s+\d+\]\s*','',visual,flags=re.I)
                if re.search(r'\[Shot\s+\d+\]|\bAt\s+\d{2}:\d{2}\.\d{3}',visual,re.I):raise ValueError('visual不写镜号或切点时间，只在cut_at指定切镜')
                if not visual.strip():raise ValueError('事件缺少画面内容')
                if event_index==0:visual='[Shot 1] '+visual
                elif cut is not None:
                    milliseconds=round(cut*1000)
                    if not round(last_cut*1000)<milliseconds<duration*1000:raise ValueError('cut_at毫秒精度后须递增且位于片段内')
                    cut_number+=1;minutes,remaining=divmod(milliseconds,60000);seconds,millis=divmod(remaining,1000)
                    visual=f'[Shot {cut_number}] At {minutes:02d}:{seconds:02d}.{millis:03d}, '+visual;last_cut=cut
            used.extend(indices);chunks.append(visual+' '+ ' '.join('{{dialogue:'+str(i)+'}}' for i in indices))
        if used!=list(range(count)):raise ValueError('事件台词编号须按原文顺序各出现一次，不得遗漏或重复；只修本镜台词位置')
        row[key]='\n'.join(chunks)
    return obj

def render_dialogue(api,p,shot,text,mode):
    """Render optional utterance placeholders, or add missing explicit per-utterance cues."""
    lines=shot.get('dialogue',[]);speakers={};cues=[]
    slots=reference_slots(api,p,shot) if mode in ('reference','video_reference') else []
    for line in lines:
        sid=speakers.setdefault(line['speaker'],len(speakers)+1)
        asset=next((a for a in p['assets'] if a.get('type')=='角色' and a.get('name')==line['speaker']),None)
        label=next((s['label'] for s in slots if asset and s['asset_id']==asset['id']),line['speaker'])
        if asset and mode in ('reference','video_reference') and not label.startswith('@'):raise ValueError('说话角色未关联到本镜参考资产')
        language=line.get('language') or ('Chinese' if re.search(r'[\u3400-\u9fff]',line['text']) else 'English')
        if not re.fullmatch(r'[A-Za-z -]{2,32}',language):raise ValueError('对白语言标签不正确')
        if line.get('members'):
            labels=[]
            for name in line['members']:
                member=next((a for a in p['assets'] if a.get('type')=='角色' and a.get('name')==name),None)
                labels.append(next((s['label'] for s in slots if member and s['asset_id']==member['id']),name))
            label=' and '.join(labels)
            cues.append(f"{label} (S{sid}) speak together in unison: <d>[{language}] {line['text']}</d>")
        else:cues.append(f"{label} (S{sid}) says: <d>[{language}] {line['text']}</d>")
    if not lines and '<d>' not in text:text=re.sub(r'\s*\(S\d+\)','',text)
    placeholders=list(re.finditer(r'\{\{dialogue:(\d+)\}\}',text))
    if placeholders:
        if '<d>' in text or [int(x[1]) for x in placeholders]!=list(range(len(lines))):raise ValueError('对白占位须逐句按顺序且不与<d>混用')
        return re.sub(r'\{\{dialogue:(\d+)\}\}',lambda m:cues[int(m[1])],text)
    # Accept a fully correct official response unchanged. Never infer speech from image metadata.
    try:validate(api,p,shot,text,mode);return text
    except ValueError as exc:
        if not any(key in str(exc) for key in ('S编号','@引用及S编号')):raise
    parts=sections(text,mode in ('reference','video_reference'));key='detailed_description' if mode in ('reference','video_reference') else 'integrated_multimodal_description';main=parts[key]
    main=re.sub(r'\s*\(S\d+\)','',main)
    blocks=list(re.finditer(r'<d>(.*?)</d>',main,re.S))
    if len(blocks)!=len(lines):raise ValueError('H3对白数量不符')
    for line,block in zip(lines,blocks):
        match=re.fullmatch(r'\[[^\]\n]+\]\s*(.*)',block[1],re.S)
        if not match or re.sub(r'\s+','',match[1])!=re.sub(r'\s+','',line['text']):raise ValueError('H3对白与原文不符，不能按位置盲目替换')
    fixed=main
    for i in reversed(range(len(blocks))):
        start=blocks[i-1].end() if i else 0;prefix=fixed[start:blocks[i].start()]
        actor=cues[i].split(' (S',1)[0];cue=re.split(r' (?:says|speak together in unison):',cues[i],maxsplit=1)[0]
        pattern=r'(?P<actor>'+re.escape(actor)+r'|He|She|They|The woman|The man|[A-Z][a-z]+(?: [A-Z][a-z]+){0,2})\s+(?P<verb>says|replies|asks|responds|whispers|shouts|exclaims|answers)(?P<tail>[^.!?\n<>]{0,200})$'
        match=re.search(pattern,prefix)
        if match:
            prefix=prefix[:match.start()]+cue+' '+match['verb']+match['tail']
            fixed=fixed[:start]+prefix+fixed[blocks[i].start():]
        else:fixed=fixed[:blocks[i].start()]+cues[i]+fixed[blocks[i].end():]
    return text.replace(parts[key],fixed,1)

def source_cut(text,target):
    # Keep all source characters and prefer existing line/sentence boundaries.
    for pattern in (r'\n',r'[。！？；.!?;]'):
        points=[m.end() for m in re.finditer(pattern,text[:target]) if m.end()>=target*.5]
        if points:return points[-1]
    return target

def planning_segments(text,limit=1200):
    if len(text)<=1800:return [(0,len(text))]
    spans=[];start=0
    while len(text)-start>limit:
        end=start+source_cut(text[start:],limit);spans.append((start,end));start=end
    if start<len(text):spans.append((start,len(text)))
    return spans

def reusable_planning_parts(api,task,context,ledger):
    accepted=[];end=0
    for part in task.get('storyboard_seed_parts',[]):
        if not isinstance(part,dict) or type(part.get('start')) is not int or type(part.get('end')) is not int or part['start']!=end or not end<part['end']<=len(context['script']):break
        try:
            obj={'shots':part['shots']};check_output_types(obj,'planning');check_planning_bindings(obj,context['assets'])
            if ledger:
                actual=[(line['speaker'],line['text']) for row in part['shots'] for line in row['dialogue']]
                expected=[(line['speaker'],line['text']) for line in ledger if part['start']<=line['start']<part['end']]
                if actual!=expected:break
            for row in part['shots']:timing(api,row,context['script'])
        except (KeyError,TypeError,ValueError):break
        accepted.append(copy.deepcopy(part));end=part['end']
    return accepted

def plan_in_parts(api,task,context,instruction):
    script=context['script'];ledger=script_dialogue_lines(script,context.get('assets',[]),task.get('storyboard_skill',{}).get('dialogue_format')=='source-lines-v2') if task.get('storyboard_skill',{}).get('dialogue_format') in ('source-lines-v1','source-lines-v2') else [];pending=[(a,z,0) for a,z in planning_segments(script)];rows=[];analyses=[];done=0;calls=0;diagnostics=[]
    seeds=reusable_planning_parts(api,task,context,ledger) if task.get('storyboard_seed_parts') else []
    if seeds:
        task['storyboard_planning_parts']=copy.deepcopy(seeds);task['storyboard_resumed_segments']=len(seeds)
        for part in seeds:
            rows.extend(copy.deepcopy(part['shots']));analyses.append(part.get('analysis',''));done+=1
            diagnostics.append({'start':part['start'],'end':part['end'],'shots':len(part['shots']),'truncated':False,'reused':True})
        end=seeds[-1]['end'];pending=[(max(a,end),z,d) for a,z,d in pending if z>end]
        task['storyboard_planning_checks']=diagnostics
    ranges=bool(ledger) and task.get('storyboard_skill',{}).get('dialogue_planning')=='contiguous-v1'
    if ranges:instruction+='\n台词分配协议覆盖前述逐句列表示例：每镜不输出dialogue，改为dialogue_through（本镜结束的原文D编号，纯动作null），可另写dialogue_delivery:{D编号:语气}。程序从上镜终点接着按原序分配台词，不需要逐句抄编号；终点不可倒退，最后一个有对白的镜头必须到本段末句，不得替后段提前规划。'
    scoped=instruction+'\n分段规划时，script是全剧上下文，planning_scope.source_segment才是本轮唯一待规划原文。仅为该段事件和台词生成shots，其他段落仅供理解，不提前拍后文、不重复前文，不漏掉本段内容；段落边界不等于换场/切镜。若原文从长台词中间开始，按全剧恢复说话人，只引用本段原文。continuity_context是前段规划，只供衔接。analysis简述本段；不复述整剧或返回之前的shots。'
    while pending:
        over_budget=calls>=64
        if over_budget and not task.get('storyboard_skill',{}).get('resilient_storyboard'):raise ValueError('分段规划达到本轮64次请求上限，未覆盖原分镜')
        start,end,depth=pending.pop(0);calls+=1
        progress(api,task,'analysis',done,done+len(pending)+1)
        payload=copy.deepcopy(context)
        source=[l for l in ledger if start<=l['start']<end] if ledger else None
        if ledger:
            payload['source_dialogue']=source
            payload['dialogue_output']=('只输出dialogue_through，每镜一个原文终点编号或null；程序顺序分配原文。最后须覆盖本段末句。' if ranges else 'dialogue每项只填line_id与delivery，不复述speaker/text。只选择本段原台词编号，保持顺序；动作不属于对白。')
        if start!=0 or end!=len(script):
            payload['planning_scope']={'start':start,'end':end,'source_segment':script[start:end]}
            payload['continuity_context']={'previous_analysis':analyses[-1] if analyses else '', 'previous_shots':[{k:r.get(k) for k in ('title','description','image_prompt','asset_ids','character_looks')} for r in rows[-2:]]}
        try:
            if over_budget:raise ModelOutputError('本轮模型规划预算已用完，剩余片段使用原文基础方案')
            obj=ask(api,task,[{'role':'system','content':scoped if 'planning_scope' in payload else instruction},{'role':'user','content':json.dumps(payload,ensure_ascii=False)}],output_kind='planning',planning_assets=context.get('assets'),unified_refs=task.get('storyboard_skill',{}).get('planning_format')=='unified-references-v1',script=script,source_lines=source,dialogue_ranges=ranges and source is not None)
        except ModelOutputError as exc:
            if task.get('storyboard_skill',{}).get('resilient_storyboard'):
                obj=basic_plan(context,start,end,source,exc)
                task.setdefault('storyboard_quality_notes',[]).append({'stage':'planning','start':start,'end':end,'reason':str(exc)[:300]})
            else:
                if not isinstance(exc,(OutputLengthError,PlanningDialogueError)):raise
                diagnostics.append({'start':start,'end':end,'truncated':isinstance(exc,OutputLengthError),'repair_split':isinstance(exc,PlanningDialogueError),'reason':str(exc)[:250]})
                task['storyboard_planning_checks']=diagnostics
                if end-start<=160 or depth>=4:raise
                cut=start+source_cut(script[start:end],(end-start)//2)
                pending[0:0]=[(start,cut,depth+1),(cut,end,depth+1)]
                continue
        part=obj.get('shots')
        if not isinstance(part,list) or not part:raise ValueError('分镜规划未返回有效镜头，原分镜未覆盖')
        rows.extend(part);analyses.append(str(obj.get('analysis','')));done+=1
        task.setdefault('storyboard_planning_parts',[]).append({'start':start,'end':end,'analysis':obj.get('analysis',''),'shots':copy.deepcopy(part)})
        diagnostics.append({'start':start,'end':end,'shots':len(part),'truncated':False});task['storyboard_planning_checks']=diagnostics
    progress(api,task,'analysis',done,done)
    return {'analysis':'\n'.join(x for x in analyses if x),'shots':rows}

def completion_note(task,shot,reason,stage):
    note={'shot_id':shot.get('id'),'title':shot.get('title',''),'stage':stage,'reason':str(reason)[:300]}
    task.setdefault('storyboard_quality_notes',[]).append(note)
    shot['generation_quality']='basic';shot['generation_note']='已用基础方案完成，可按需润色'

def basic_plan(context,start,end,source,reason):
    """A usable source-bound plan when model prose is malformed. No new story or assets."""
    script=context['script'];assets=context.get('assets',[]);segment=script[start:end];rows=[]
    lines=source or []
    if source is None:
        offset=start
        for raw in segment.splitlines(keepends=True):
            match=re.match(r'^\s*([^：:\n]{1,12})[：:]\s*(.+?)\s*$',raw.rstrip('\r\n'))
            if match and not re.match(r'场景|时间|地点|标题|人物|内景|外景|时长|第.{0,8}[场幕集]',match[1]) and not STAGE_DIRECTION.fullmatch(match[2]):lines.append({'speaker':match[1].strip(),'text':match[2],'start':offset})
            offset+=len(raw)
    groups=[lines[i:i+3] for i in range(0,len(lines),3)] if lines else [[]]
    for index,group in enumerate(groups):
        a=start if index==0 else group[0]['start'];z=groups[index+1][0]['start'] if index+1<len(groups) else end
        passage=script[a:z].strip();names={name for line in group for name in line.get('members') or [line['speaker']]}
        ids=[x['id'] for x in assets if (x.get('type')=='角色' and (x.get('name') in names or x.get('name','') and x['name'] in passage)) or (x.get('type')=='道具' and x.get('name','') and x['name'] in passage)]
        scenes=[x for x in assets if x.get('type')=='场景'];mentioned=[x for x in scenes if x.get('name','') and x['name'] in passage]
        if not mentioned:
            prior=[(script.rfind(x.get('name',''),0,a),x) for x in scenes if x.get('name')]
            if prior and max(v[0] for v in prior)>=0:mentioned=[max(prior,key=lambda v:v[0])[1]]
            elif len(scenes)==1:mentioned=scenes
        ids.extend(x['id'] for x in mentioned if x['id'] not in ids)
        # Spoken source is stored separately; keep only action/source context in the visual description.
        action='\n'.join(line for line in passage.splitlines() if not re.match(r'^\s*[^：:]{1,35}[：:]',line)).strip()
        description=action or '按本段原文台词展开对话，保持既有场景和人物关系。'
        row={'title':'原文片段 '+str(index+1),'description':description.replace('@',''),'image_prompt':description[:600].replace('@',''),'video_prompt':'','duration':4,'dialogue':[{k:copy.deepcopy(line[k]) for k in ('speaker','text','members') if k in line} for line in group],'asset_ids':ids,'character_looks':{},'action_seconds':0,'pause_seconds':0,'duration_basis':'按原文对白与换人停顿估算','generation_quality':'basic','generation_note':'已用原文基础规划完成，可按需润色'}
        rows.append(row)
    return {'analysis':'本段采用原文基础规划，保留原句与顺序。','shots':rows}

def basic_prompt(api,p,shot,task,reason):
    mode=api.video_mode(shot,p);language=shot.get('prompt_language') or p.get('prompt_language') or 'zh'
    narrative=str(shot.get('description') or shot.get('image_prompt') or shot.get('title') or '按当前分镜展开。')
    for line in shot.get('dialogue',[]):narrative=narrative.replace(line['text'],'')
    narrative=re.sub(r'\[Shot\s+\d+\]|\bAt\s+\d{2}:\d{2}\.\d{3},?|<[^>]*>','',narrative,flags=re.I).replace('@','').strip()
    if language=='en' and re.search(r'[\u3400-\u9fff]',narrative):language='zh'
    shot['prompt_language']=language
    chinese=language=='zh'
    main='[Shot 1] '+narrative
    if not re.search(r'定格|freeze[- ]frame',narrative,re.I):main+=(' 人物按剧情自然活动，保留呼吸、眨眼和细微视线变化。' if chinese else ' Characters move naturally with subtle breathing, blinking and gaze shifts.')
    main+='\n'+'\n'.join('{{dialogue:'+str(i)+'}}' for i in range(len(shot.get('dialogue',[]))))
    if is_h3(api.video_model(shot,p)):
        entry={'summary':shot.get('title') or ('原文片段' if chinese else 'Planned scene'),'detailed_description':main,'integrated_multimodal_description':main,'overall_soundscape':'场景自然环境声。' if chinese else 'Natural scene ambience.','non_diegetic_music':'N/A'}
        text=assemble_h3(api,p,shot,entry,mode);text=render_dialogue(api,p,shot,text,mode);text=normalize_performance(text,task,shot.get('title',''),allow_freeze=bool(re.search(r'定格|freeze[- ]frame',narrative,re.I)))
        validate(api,p,shot,text,mode);shot.update(video_prompt=text,prompt_format='h3-official-v1',prompt_video_mode=mode)
    else:
        shot['video_prompt']=narrative+'\n'+'\n'.join(line['speaker']+'：'+line['text'] for line in shot.get('dialogue',[]));shot.pop('prompt_format',None);shot.pop('prompt_video_mode',None)
    api.sync_duration(shot);api.sync_shot_mentions(p,shot,strict=True);completion_note(task,shot,reason,'prompts')
    return shot

def normalize_performance(text,task,title='',allow_freeze=False):
    """Soften absolute immobility in generated directions, never source speech or quoted text."""
    if allow_freeze:return text
    chunks=re.split(r'(<d>.*?</d>|"[^"\n]*"|“[^”\n]*”)',text,flags=re.S);changed=False
    patterns=[(r'\b(?:remain|remains|stay|stays)\s+(?:completely\s+|perfectly\s+)?(?:still|motionless)\b','stay in position with subtle breathing, blinking and small natural gaze shifts'),(r'\b(?:do|does) not move(?: or react)?\b','stay in place without fleeing, with subtle breathing, blinking and natural gaze shifts'),(r'保持(?:完全)?不动|一动不动|纹丝不动|完全静止','保持原位，没有起身或逃跑，保留自然呼吸、眨眼和细微视线变化'),(r'毫无反应|没有任何反应','没有明显的大幅反应，保留自然呼吸和细微视线变化')]
    for i in range(0,len(chunks),2):
        old=chunks[i]
        for pattern,replacement in patterns:chunks[i]=re.sub(pattern,replacement,chunks[i],flags=re.I)
        changed=changed or old!=chunks[i]
    if changed:task.setdefault('storyboard_repairs',[]).append({'action':'natural_performance','title':title})
    return ''.join(chunks)

def bind_dialogue_roles(p,row,task):
    """Source speakers identify roles exactly; never infer identity from model slot numbers."""
    ids=list(row['asset_ids']);looks=dict(row['character_looks'])
    for line in row['dialogue']:
        for name in line.get('members') or [line['speaker']]:
            roles=[a for a in p['assets'] if a.get('type')=='角色' and a.get('name')==name]
            if len(roles)>1:raise ValueError('说话角色名称不唯一，无法自动关联：'+name)
            if not roles:continue  # Narrator or unnamed source speaker has no image asset.
            role=roles[0]
            if role['id'] in ids:continue
            ids.append(role['id'])
            default=role.get('default_look_id')
            if default and any(l['id']==default for l in role.get('looks',[])):looks[role['id']]=default
            task.setdefault('storyboard_repairs',[]).append({'action':'bind_source_speaker','title':row.get('title'),'asset_id':role['id'],'speaker':name})
    return dict(row,asset_ids=ids,character_looks=looks)

def planning_fingerprint(shot):
    fields={k:shot.get(k) for k in ('title','description','image_prompt','duration','dialogue','asset_ids','character_looks')}
    return hashlib.sha256(json.dumps(fields,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def resume_h3_prompts(api,p,task,shots,mode):
    parts=task.get('storyboard_seed_prompts',[]);accepted=[]
    for index,part in enumerate(parts):
        if index>=len(shots) or not isinstance(part,dict) or part.get('index')!=index or part.get('fingerprint')!=planning_fingerprint(shots[index]):break
        text=part.get('video_prompt')
        if not isinstance(text,str):break
        try:validate(api,p,shots[index],text,mode)
        except ValueError:break
        shots[index].update(video_prompt=text,prompt_format='h3-official-v1',prompt_video_mode=mode)
        accepted.append(copy.deepcopy(part))
    if accepted:
        task['storyboard_prompt_parts']=accepted;task['storyboard_resumed_prompts']=len(accepted)
        task['storyboard_prompt_checks']=[{'batch_start':i,'attempts':0,'passed':True,'reused':True} for i in range(len(accepted))]
    return len(accepted)

def prompt_is_missing(api,shot):
    return not api.DURATION_LINE.sub('',shot.get('video_prompt') or '').strip()

def write_existing(api,p,task):
    if task['storyboard_skill'].get('scheme')=='h3-structured-v2':
        import h3_structured
        return h3_structured.write_existing(api,p,task)
    if task['storyboard_skill'].get('scheme')=='huobao-native-v1':
        import huobao_native
        return huobao_native.write_existing(api,p,task)
    if task['storyboard_skill'].get('director_format')=='coverage-v1':
        import coverage_director
        return coverage_director.write_existing(api,p,task)
    if task['storyboard_skill'].get('source_owned_events'):
        import source_storyboard
        return source_storyboard.write_existing(api,p,task)
    shots=copy.deepcopy(p['shots']);selected=set(task['storyboard_shot_ids']);total=len(selected);done=0
    seed={part.get('shot_id'):part for part in task.get('storyboard_seed_prompts',[]) if isinstance(part,dict)}
    for shot in shots:
        if shot['id'] not in selected:continue
        mode=api.video_mode(shot,p);model=api.video_model(shot,p)
        effective=dict(p,video_mode=mode,video_model=model)
        bundle=skill_bundle(api,effective)
        # Use the frozen instructions. Only the official mode-specific appendix differs.
        local=copy.deepcopy({k:v for k,v in task.items() if k not in ('project_id','storyboard_seed_prompts','storyboard_prompt_parts','storyboard_progress','storyboard_repairs','storyboard_json_diagnostics','storyboard_prompt_diagnostics','storyboard_resumed_prompts','storyboard_prompt_checks')})
        local['storyboard_skill']={**task['storyboard_skill'],'video_mode':mode,'video_model':model,'format':bundle['format']}
        local['storyboard_official_text']=task.get('storyboard_mode_official',{}).get(mode) or bundle.get('official_text','')
        local['storyboard_analysis']='基于用户已确认的现有分镜，不重新规划剧情。'
        if shot.get('dialogue') is None:raise ValueError('镜头缺少逐句台词规划，请先补充dialogue或重新生成规划')
        _,budget=timing(api,dict(shot,action_seconds=0,pause_seconds=0),p['script'])
        if budget['minimum_seconds']>api.duration_value(shot.get('duration',4))+.05:
            if task['storyboard_skill'].get('resilient_storyboard'):
                shot['duration']=math.ceil(budget['minimum_seconds']*10)/10;completion_note(task,shot,'已按原文台词自动补足时长','timing')
            else:raise ValueError('镜头“'+shot.get('title','')+'”时长不足以容纳原台词，请先调整规划时长')
        if local['storyboard_skill'].get('prompt_language'):shot['prompt_language']=local['storyboard_skill']['prompt_language']
        saved=seed.get(shot['id'])
        if not saved and task.get('storyboard_stage','all')=='all':saved=next((part for part in task.get('storyboard_seed_prompts',[]) if part.get('index')==next(i for i,s in enumerate(shots) if s['id']==shot['id'])),None)
        if saved and saved.get('mode')==mode and saved.get('model')==model:local['storyboard_seed_prompts']=[dict(saved,index=0)]
        progress(api,task,'h3_prompts',done,total)
        try:
            if bundle['format']=='h3-official-v1':
                write_prompts(api,effective,local,[shot])
            else:
                messages=[{'role':'system','content':'按现有分镜编写一条完整视频提示词，不改剧情台词与资源。只返回prompts:[{index:0,video_prompt:文字}] JSON。原台词逐字保留，参考模式使用给定@标签，其他模式使用人物普通名称。提示词语言：'+str(p.get('prompt_language') or 'zh')},{'role':'user','content':json.dumps({'shot':shot,'assets':api.script_reference_context(p),'mode':mode},ensure_ascii=False)}]
                result=ask(api,local,messages,output_kind='prompts',expected_indices=[0]);shot['video_prompt']=result['prompts'][0]['video_prompt'];api.sync_duration(shot);api.sync_shot_mentions(p,shot,strict=True)
        except ValueError as exc:
            if task['storyboard_skill'].get('resilient_storyboard') and isinstance(exc,ModelOutputError):basic_prompt(api,effective,shot,task,exc)
            else:raise ValueError('镜头'+str(next(i for i,s in enumerate(shots,1) if s['id']==shot['id']))+'（'+shot.get('title','')+'）视频提示词失败：'+str(exc)) from exc
        finally:
            for key in ('storyboard_repairs','storyboard_json_diagnostics','storyboard_prompt_diagnostics','storyboard_prompt_checks'):
                if local.get(key):
                    records=copy.deepcopy(local[key])
                    for record in records:record.update(shot_id=shot['id'],shot_index=next(i for i,s in enumerate(shots) if s['id']==shot['id']))
                    task.setdefault(key,[]).extend(records)
        if local.get('storyboard_resumed_prompts'):task['storyboard_resumed_prompts']=task.get('storyboard_resumed_prompts',0)+1
        task.setdefault('storyboard_prompt_parts',[]).append({'index':done,'shot_id':shot['id'],'mode':mode,'model':model,'fingerprint':planning_fingerprint(shot),'video_prompt':shot['video_prompt']})
        done+=1;progress(api,task,'h3_prompts',done,total)
    return {'shots':shots}

def check_existing(api,p):
    report=[]
    source={(x['speaker'],x['text']) for x in script_dialogue_lines(p.get('script',''),p.get('assets',[]),True)}
    for index,original in enumerate(p.get('shots',[]),1):
        shot=copy.deepcopy(original);errors=[];warnings=[]
        stale=None
        try:
            import h3_structured
            stale=h3_structured.stale_reason(p,shot,api.video_mode(shot,p),api.video_model(shot,p))
        except (ValueError,KeyError,TypeError):pass
        if stale:warnings.append('需重新生成提示词：'+stale)
        elif shot.get('prompt_stale'):warnings.append('需重新生成提示词：'+str((shot['prompt_stale'] or {}).get('reason','视频模型已变更')))
        if shot.get('prompt_format')=='h3-structured-v2':
            import h3_structured
            try:api.validate_resources(dict(p,shots=[shot]))
            except (ValueError,KeyError,TypeError) as exc:errors.append(str(exc))
            if not str(shot.get('video_prompt','')).strip():warnings.append('尚未编写视频提示词')
            elif shot.get('h3_plan') and shot.get('video_prompt')==shot.get('h3_rendered'):
                errors.extend(h3_structured.validate_plan(p,shot,shot['h3_plan'],h3_structured.model_rules(api.video_model(shot,p))))
            else:warnings.append('提示词已手动修改，未按结构化计划校验')
            report.append({'shot_id':shot['id'],'index':index,'title':shot.get('title',''),'errors':errors,'warnings':warnings})
            continue
        if shot.get('prompt_format')=='huobao-native-v1':
            try:api.validate_resources(dict(p,shots=[shot]));api.duration_value(shot.get('duration',10))
            except (ValueError,KeyError,TypeError) as exc:errors.append(str(exc))
            if not str(shot.get('video_prompt','')).strip():warnings.append('尚未编写视频提示词')
            report.append({'shot_id':shot['id'],'index':index,'title':shot.get('title',''),'errors':errors,'warnings':warnings})
            continue
        for check in (lambda:api.validate_resources(dict(p,shots=[shot])),lambda:api.sync_shot_mentions(p,shot,strict=True)):
            try:check()
            except (ValueError,KeyError,TypeError) as exc:errors.append(str(exc))
        for line in shot.get('dialogue',[]) if isinstance(shot.get('dialogue'),list) else []:
            if isinstance(line,dict) and source and (line.get('speaker'),line.get('text')) not in source:errors.append('台词或说话人与剧本原文不符：'+str(line.get('text',''))[:60])
        if shot.get('generation_note'):warnings.append(shot['generation_note'])
        if prompt_is_missing(api,shot):warnings.append('尚未编写视频提示词')
        else:
            try:
                if is_h3(api.video_model(shot,p)):validate(api,p,shot,shot['video_prompt'],api.video_mode(shot,p))
            except (ValueError,KeyError,TypeError) as exc:errors.append(str(exc))
        try:
            old_budget=shot.get('timing') or {}
            _,budget=timing(api,dict(shot,action_seconds=shot.get('action_seconds',old_budget.get('extra_action_seconds',0)),pause_seconds=shot.get('pause_seconds',old_budget.get('pause_seconds',0))),p['script'])
            if budget['minimum_seconds']>api.duration_value(shot.get('duration',4))+.05:errors.append('时长短于当前台词与动作预算')
        except (ValueError,TypeError,KeyError) as exc:errors.append(str(exc))
        report.append({'shot_id':shot['id'],'index':index,'title':shot.get('title',''),'errors':errors,'warnings':warnings})
    return {'ok':bool(report) and not any(r['errors'] for r in report),'checked':len(report),'issues':[r for r in report if r['errors'] or r['warnings']],'missing_prompts':sum('尚未编写视频提示词' in r['warnings'] for r in report),'scope':'H3结构化镜头检查资源、时长/模型约束、参考图≤4、语速≤4字/秒、说话方≤2与提示词是否过期；Huobao镜头仅检查资源存在、正数时长与提示词缺失；旧格式沿用原校验。均不是媒体或导演质量验收'}

def plan(api,p,task):
    if task['storyboard_skill'].get('scheme')=='h3-structured-v2':
        import h3_structured
        return h3_structured.plan(api,p,task)
    if task['storyboard_skill'].get('scheme')=='huobao-native-v1':
        import huobao_native
        return huobao_native.plan(api,p,task)
    if task['storyboard_skill'].get('director_format')=='coverage-v1':
        import coverage_director
        return coverage_director.plan(api,p,task)
    if task['storyboard_skill'].get('source_owned_events'):
        import source_storyboard
        return source_storyboard.plan(api,p,task)
    skill=task['storyboard_skill'];mode=skill['video_mode'];h3=skill['format']=='h3-official-v1'
    context={'script':p['script'],'ratio':p.get('ratio'),'video_mode':mode,'video_model':skill['video_model'],'assets':api.script_reference_context(p),'mention_catalog':[{k:r.get(k) for k in ('label','asset_id','look_id','type')} for r in api.mention_catalog(p)]}
    instruction=stage_skill(task['storyboard_skill_text'],'planning')+'\n现在只执行第一阶段，分析剧情节奏，输出analysis和shots规划JSON；不要输出第二阶段。'
    language=skill.get('prompt_language')
    language_rule=('\n本项目提示词语言为'+('中文' if language=='zh' else '英文')+'：title、description、image_prompt、summary、visual及声音说明均使用此语言。原台词、人物资产名、@标签、JSON字段及协议标记不翻译。') if language else ''
    instruction+=language_rule
    progress(api,task,'analysis',0,0)
    obj=plan_in_parts(api,task,context,instruction);rows=obj.get('shots')
    if not isinstance(rows,list) or not rows:raise ValueError('分镜规划未返回有效镜头')
    shots=[];known={a['id']:a for a in p['assets']}
    for row in rows:
        if not isinstance(row,dict) or any(not isinstance(row.get(k),str) or not row[k].strip() for k in ('title','description','image_prompt')):raise ValueError('分镜规划缺少标题、描述或首帧构图')
        ids=row.get('asset_ids',[]);looks=row.get('character_looks',{})
        if not isinstance(ids,list) or any(not isinstance(aid,str) or aid not in known or known[aid].get('type') not in ('角色','场景','道具') for aid in ids):raise ValueError('分镜引用了不存在的资产')
        if not isinstance(looks,dict) or any(aid not in ids or known[aid].get('type')!='角色' or not any(l['id']==lid for l in known[aid].get('looks',[])) for aid,lid in looks.items()):raise ValueError('分镜引用了不属于该人物的造型')
        if skill.get('h3_stable_refs'):
            row=bind_dialogue_roles(p,row,task);ids=row['asset_ids'];looks=row['character_looks']
        duration,budget=timing(api,row,p['script']);shot={k:copy.deepcopy(row[k]) for k in ('title','description','image_prompt','dialogue')}
        for key in ('generation_quality','generation_note'):
            if row.get(key):shot[key]=row[key]
        shot.update(id=api.uid(),duration=duration,timing=budget,video_prompt=str(row.get('video_prompt','')),asset_ids=list(dict.fromkeys(ids)),character_looks=looks,versions=[],video_override=None)
        if language:shot['prompt_language']=language
        api.sync_shot_mentions(p,shot,strict=True);api.validate_resources(dict(p,shots=[shot]));shots.append(shot)
    task['storyboard_analysis']=str(obj.get('analysis',''));task['storyboard_draft']=copy.deepcopy(shots)
    if task.get('storyboard_stage')=='planning':
        for shot in shots:shot['video_prompt']=''
        progress(api,task,'complete',len(shots),len(shots))
        return {'shots':shots}
    if skill.get('resilient_storyboard'):
        task['storyboard_shot_ids']=[shot['id'] for shot in shots]
        return write_existing(api,dict(p,shots=shots),task)
    return write_prompts(api,p,task,shots)

def write_prompts(api,p,task,shots):
    skill=task['storyboard_skill'];mode=skill['video_mode'];h3=skill['format']=='h3-official-v1'
    language=skill.get('prompt_language')
    language_rule=('\n本项目提示词语言为'+('中文' if language=='zh' else '英文')+'，原台词、资产标签、JSON字段和协议标记不翻译。') if language else ''
    context={'script':p['script'],'ratio':p.get('ratio'),'video_mode':mode,'video_model':skill['video_model'],'assets':api.script_reference_context(p),'mention_catalog':[{k:r.get(k) for k in ('label','asset_id','look_id','type')} for r in api.mention_catalog(p)]}
    task.setdefault('storyboard_analysis','')
    if not h3:
        for shot in shots:
            if not shot['video_prompt'].strip():raise ValueError('非H3分镜缺少视频提示词')
            api.sync_duration(shot)
        return {'shots':shots}
    batch_size=1 if skill.get('h3_batch_size')==1 else 3
    resumed=resume_h3_prompts(api,p,task,shots,mode) if batch_size==1 else 0
    for start in range(0,len(shots),batch_size):
        if start<resumed:continue
        batch=shots[start:start+batch_size];progress(api,task,'h3_prompts',start,len(shots))
        instruction=stage_skill(task['storyboard_skill_text'],'rendering')+'\n\n对应模式的官方原始规范：\n'+task['storyboard_official_text']+'\n\n现在只执行第二阶段。每个index都是独立生成的一个视频片段，不能把整批当一个视频。资产参考模式严格按每镜reference_slots表使用官方<Subject N>/<Picture N>，或使用对应@标签，不能自行猜图号；平台会规范化保存稳定引用。严格采用每镜提供的speaker_ids，S编号在每个index重新从1开始，不按全批编号。逐字保留dialogue的内容、顺序和说话人，使用传入index。每句台词推荐在完整台词句应该出现的位置写{{dialogue:0}}、{{dialogue:1}}，编号仅针对本镜dialogue列表；不要再在占位旁重复写台词句。平台会替换为正确角色(S编号)及原文<d>完整台词句。也接受已完整正确的官方<d>写法。continuity_context只供相邻状态核对；只为shots列表编写，不重复邻镜台词或添加邻镜资产。只返回prompts JSON。'
        def neighbor(index):
            if not 0<=index<len(shots):return None
            shot=shots[index]
            return dict(index=index,**{key:copy.deepcopy(shot[key]) for key in ('title','description','image_prompt','asset_ids','character_looks')})
        continuity={'planning_analysis':task['storyboard_analysis'],'previous':neighbor(start-1),'next':neighbor(start+len(batch))}
        payload={**context,'continuity_context':continuity,'shots':[dict(shot,index=start+i,reference_slots=reference_slots(api,p,shot) if mode in ('reference','video_reference') else [],speaker_ids={name:'S'+str(n+1) for n,name in enumerate(dict.fromkeys(line['speaker'] for line in shot['dialogue']))}) for i,shot in enumerate(batch)]};error=None
        structured=skill.get('planning_format')=='unified-references-v1'
        prompt_kind=('h3-reference' if mode in ('reference','video_reference') else 'h3-base') if structured else 'prompts'
        if batch_size==1:
            payload.pop('script',None)
            selected=set(batch[0]['asset_ids'])
            payload['assets']=[a for a in context['assets'] if a['id'] in selected]
            payload['mention_catalog']=[r for r in context['mention_catalog'] if r['asset_id'] in selected]
            instruction+='\n本次仅编写一个独立视频，index只是工作台索引。只使用当前reference_slots，绝不沿用其他镜头的Subject/Picture/S编号；每段内部Shot从1开始。'
        if structured:instruction+='\n本轮只输出结构化H3字段，不能输出video_prompt字符串。'+('每项包含index、summary、detailed_description、overall_soundscape、non_diegetic_music；主体定义和保留分析由平台生成，不再输出。' if mode in ('reference','video_reference') else '每项包含index、integrated_multimodal_description、overall_soundscape、non_diegetic_music；首帧对齐前缀由平台生成。')+'正文从[Shot 1]开始，有对白必须在对应事件处放{{dialogue:0}}等占位，不得只写speaks却漏掉占位。'
        events=bool(structured and batch_size==1 and skill.get('h3_dialogue_events'))
        if events:
            instruction+='\n最终输出协议覆盖上文示例写法：不要输出detailed_description或integrated_multimodal_description；改为events:[{visual:英文画面动作与切点,dialogue_indices:[本镜台词的0起始索引]}]。每个事件先呈现visual再说所选台词，无台词填[]。所有台词编号按原文顺序各使用一次。visual不抄台词，不写<d>、S编号或占位符；平台自动插入原文、角色和语言。summary和声音字段仍保留。'
            if skill.get('h3_event_timing'):instruction+='\n切镜协议：每个event另含cut_at；首事件和同一镜内的连续动作/渐暗填null，只有真正换机位或剪切才填距本片段开头的秒数（递增且小于duration）。visual不写[Shot N]或At时间，平台据cut_at生成镜号和时间格式。多个events不代表多个Shot，不为每个动作强行切镜。'
            payload['dialogue_catalog']=[{'index':i,'speaker':line['speaker'],'text':line['text']} for i,line in enumerate(batch[0]['dialogue'])]
        if events and skill.get('h3_stable_refs'):
            instruction=stage_skill(task['storyboard_skill_text'],'rendering')+'\n现在只编写当前shots的events JSON，使用schema；官方H3最终段落、编号与原台词由平台编译。不要输出最终提示词格式。'
            if mode not in ('reference','video_reference'):instruction+='\n当前基础/首帧模式不提供资产图片，人物用普通名称，不写@引用。'
            payload.pop('speaker_ids',None)
            for item in payload['shots']:
                item.pop('speaker_ids',None)
                item['reference_slots']=[{k:v for k,v in slot.items() if k not in ('subject','picture')} for slot in item['reference_slots']]
        slots=bool(events and skill.get('h3_dialogue_slots'))
        if slots:instruction+='\n本轮events必须是固定位置对象，不是数组：{opening:画面或null,dialogue:{line_0:{visual,cut_at},line_1:{visual,cut_at},...},closing:画面或null}。dialogue各位置与本镜原文台词一一对应，由程序按0起始顺序填原句；只安排对应句子的画面，绝不输出dialogue_indices、台词文字或<d>。opening/closing可省略画面填null；无台词时dialogue为{}且opening必须有画面。cut_at规则不变，第一段有效画面填null，连续镜头填null。'
        instruction+=language_rule
        for attempt in range(2):
            messages=[{'role':'system','content':instruction},{'role':'user','content':json.dumps(payload,ensure_ascii=False)}]
            if error:messages.append({'role':'user','content':'上一轮未通过：'+error+'。只修正本批格式和台词，重新返回本批完整prompts。'})
            limits=None
            if structured and batch_size==1:
                speech=sum(len(line['text']) for line in batch[0]['dialogue'])
                main_limit=max(6000,1500+speech*8+len(batch[0]['description'])*3)
                limits={'summary':900,'detailed_description':main_limit,'integrated_multimodal_description':main_limit,'overall_soundscape':700,'non_diegetic_music':300}
            result=ask(api,task,messages,output_kind=prompt_kind,expected_indices=list(range(start,start+len(batch))),field_limits=limits,dialogue_count=len(batch[0]['dialogue']) if events else None,event_duration=batch[0]['duration'] if events and skill.get('h3_event_timing') else None,dialogue_slots=slots)
            try:
                prompts=result.get('prompts')
                if not isinstance(prompts,list) or len(prompts)!=len(batch):raise ValueError('未返回本批全部提示词')
                if any(not isinstance(x,dict) or isinstance(x.get('index'),bool) or not isinstance(x.get('index'),int) for x in prompts):raise ValueError('提示词索引须为整数')
                mapped={x['index']:x for x in prompts} if structured else {x['index']:x.get('video_prompt') for x in prompts}
                if set(mapped)!=set(range(start,start+len(batch))):raise ValueError('提示词索引重复或不匹配')
                checked=[]
                for i,shot in enumerate(batch,start):
                    text=assemble_h3(api,p,shot,mapped[i],mode) if structured else mapped[i]
                    if not isinstance(text,str):raise ValueError('视频提示词须为文字')
                    if skill.get('h3_stable_refs') and re.search(r'<(?:Subject|Picture|Audio|Video)\s+\d+>',json.dumps(mapped[i],ensure_ascii=False) if structured else mapped[i]):raise ValueError('只使用本镜reference_slots中的@label，不写Subject/Picture数字编号；编号由平台生成')
                    text=normalize_cut_labels(text,mode in ('reference','video_reference'),task,shot.get('title',''))
                    if mode in ('reference','video_reference'):text=normalize_references(text,reference_slots(api,p,shot))
                    text=render_dialogue(api,p,shot,text,mode)
                    if skill.get('performance_format'):text=normalize_performance(text,task,shot.get('title',''),allow_freeze=bool(re.search(r'画面定格|定格画面|freeze[- ]frame',p['script'],re.I)))
                    checked.append(validate(api,p,shot,text,mode))
                for shot,text in zip(batch,checked):
                    shot.update(video_prompt=text,prompt_format='h3-official-v1',prompt_video_mode=mode);api.sync_duration(shot);api.sync_shot_mentions(p,shot,strict=True)
                task.setdefault('storyboard_prompt_checks',[]).append({'batch_start':start,'attempts':attempt+1,'passed':True})
                if batch_size==1:
                    task.setdefault('storyboard_prompt_parts',[]).append({'index':start,'fingerprint':planning_fingerprint(batch[0]),'video_prompt':batch[0]['video_prompt']})
                progress(api,task,'h3_prompts',start+len(batch),len(shots))
                break
            except ValueError as exc:
                error=str(exc)
                if not skill.get('h3_stable_refs'):payload['previous_prompts']=result
                task.setdefault('storyboard_prompt_diagnostics',[]).append({'batch_start':start,'attempt':attempt+1,'error':error,'response':result})
                if attempt:
                    task.setdefault('storyboard_prompt_checks',[]).append({'batch_start':start,'attempts':2,'passed':False,'error':error})
                    raise ModelOutputError('H3提示词校验未通过：'+error+'；原分镜未覆盖')
    progress(api,task,'complete',len(shots),len(shots))
    return {'shots':shots}
