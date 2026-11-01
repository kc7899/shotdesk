"""Scene blocking and actor-led coverage. Source records are inputs, never final prose.

The director supplies filmable staging; the compiler owns dialogue, resources and time.
"""
import copy,hashlib,json,math,re
import storyboard as b
import source_storyboard as source

VERSION='coverage-v1'
PIPELINE_REVISION='sound-ownership-v1'

def note(task,stage,reason,**data):
    task.setdefault('storyboard_quality_notes',[]).append(dict(stage=stage,reason=reason,**data))

def catalog(p):
    return {f'A{i}':a for i,a in enumerate(p.get('assets',[]),1) if a.get('type') in ('角色','场景','道具')}

def ask(api,task,schema,payload,instruction,max_tokens=6000):
    language=payload.get('language')
    if language=='en':instruction='Write ALL narrative fields in ENGLISH, including cast appearance, placement, voice, space, action prose and sound. Keep supplied dialogue verbatim in Chinese. '+instruction+'\nALL free-text output must be English; source dialogue and reference names remain unchanged.'
    result=api.Q.text_request({'model':task['model'],'messages':[{'role':'system','content':instruction},{'role':'user','content':json.dumps(payload,ensure_ascii=False)}],'temperature':.25,'max_tokens':max_tokens,'response_format':{'type':'json_schema','json_schema':{'name':'director_coverage','schema':schema}},'chat_template_kwargs':{'enable_thinking':False}},task)
    try:
        raw=result['choices'][0]['message']['content'];raw=re.sub(r'<think>.*?</think>','',raw,flags=re.S);value=json.loads(raw[raw.find('{'):raw.rfind('}')+1])
        return value if isinstance(value,dict) else {}
    except (ValueError,TypeError,KeyError,IndexError):return {}

def text(value,default=''):
    return value.strip() if isinstance(value,str) and value.strip() else default

def scene_roles(cat,events):
    ids={aid for event in events for aid in event.get('role_ids',[])}
    for event in events:
        if event.get('dialogue'):
            line=event['dialogue'];names=line.get('members') or [line['speaker']]
            ids.update(a['id'] for a in cat.values() if a.get('type')=='角色' and a.get('name') in names)
    return {key:a for key,a in cat.items() if a.get('type')=='角色' and a['id'] in ids}

def scene_schema(roles,events,props):
    ids=[e['id'] for e in events];fields={}
    for key,a in roles.items():
        looks=['L'+str(i) for i,_ in enumerate(a.get('looks',[]),1)]+[None]
        change={'type':'object','properties':{'at':{'enum':ids},'placement':{'type':'string'},'present':{'type':'boolean'},'look':{'enum':looks},'detail':{'type':'string'}},'required':['at','placement','present','look','detail'],'additionalProperties':False}
        fields[key]={'type':'object','properties':{'placement':{'type':'string'},'side':{'enum':['left','center','right']},'camera':{'type':'string'},'voice':{'type':'string'},'present':{'type':'boolean'},'look':{'enum':looks},'changes':{'type':'array','items':change}},'required':['placement','side','camera','voice','present','look','changes'],'additionalProperties':False}
    clip={'type':'object','properties':{'through':{'enum':ids},'props':{'type':'array','items':{'enum':list(props)} if props else {'type':'string'},'maxItems':4}},'required':['through','props'],'additionalProperties':False}
    return {'type':'object','properties':{'space':{'type':'string'},'axis':{'type':'string'},'cast':{'type':'object','properties':fields,'required':list(fields),'additionalProperties':False},'actors':{'type':'object','properties':{e['id']:{'type':'array','items':{'enum':list(roles)} if roles else {'type':'string'},'maxItems':len(roles)} for e in events if e['kind'] not in ('dialogue','sound','timing','pause','camera','direction','transition')},'additionalProperties':False},'clips':{'type':'array','items':clip}},'required':['space','axis','cast','actors','clips'],'additionalProperties':False}

def fallback_scene(cat,roles,events,language,scene):
    zh=language=='zh';cast={}
    for i,(key,a) in enumerate(roles.items()):
        looks=a.get('looks',[]);lid=a.get('default_look_id');short=next(('L'+str(n) for n,l in enumerate(looks,1) if l['id']==lid),None)
        first=next((e for e in events if e['kind']=='action' and a.get('name') in e['text']),None)
        placement=(first['text'] if first else ('画面左侧，面向交谈对象。' if i%2==0 else '画面右侧，面向交谈对象。')) if zh else ('On the left, facing the other participant.' if i%2==0 else 'On the right, facing the other participant.')
        entering=bool(first and re.search(r'走来|走进|冲进|进入|进门',first['text']))
        cast[key]={'camera':'','side':'left' if i%2==0 else 'right','appearance':text(a.get('prompt'),a.get('name','character'))[:260],'placement':placement,'voice':'自然说话声' if zh else 'a natural speaking voice','present':not entering,'look':short,'changes':[{'at':first['id'],'placement':placement,'present':True,'look':short}] if entering else []}
    return {'space':('；'.join(scene.get('heading',[])) if zh else 'The referenced location.'),'axis':'保持同一侧视角和人物左右关系。' if zh else 'Keep the camera on the same side of the conversation axis.','cast':cast,'actors':{},'clips':[]}

def blocking_context(task,scene,events,cat):
    old=task.get('director_location_context',{}).get(scene.get('location_id'))
    if not old:return None
    result={k:old[k] for k in ('space','axis') if k in old}
    opening=str(scene)+' '.join(e['text'] for e in events[:6])
    if not re.search(r'次日|翌日|第二天|next day',opening,re.I):
        result['positions']=[{'key':k,'name':cat[k]['name'],'placement':v['placement'],'present':v['present'],'look':v['look']} for k,v in old.get('cast',{}).items() if k in cat]
    return result

def direct_scene(api,p,task,book,scene_id,events):
    cat=catalog(p);roles=scene_roles(cat,events);props={k:a for k,a in cat.items() if a.get('type')=='道具'};language=p.get('prompt_language') or 'zh';scene=book['scenes'][scene_id]
    payload={'phase':'scene_blocking','language':language,'scene':scene,'location':[{'name':a['name'],'description':a.get('prompt','')} for a in cat.values() if a['id']==scene.get('location_id')],'established_blocking':blocking_context(task,scene,events,cat),'events':[{'id':e['id'],'kind':e['kind'],'text':e['text'],**({'speaker':e['dialogue']['speaker']} if e.get('dialogue') else {})} for e in events],'characters':[{'key':k,'name':a['name'],'identity':a.get('prompt',''),'looks':[{'key':'L'+str(i),'name':l.get('name'),'description':l.get('prompt','')} for i,l in enumerate(a.get('looks',[]),1)]} for k,a in roles.items()],'props':[{'key':k,'name':a['name']} for k,a in props.items()]}
    instruction=task['storyboard_skill_text']+'\n当前只做scene_blocking：建立space、axis和cast开场站位（位置/坐站/朝向）及有原文依据的changes。placement只写该时刻固定地点、坐站与朝向，不写随后会发生什么；side给出稳定的左右位置。camera为该人物唯一确定的主要覆盖机位，不能给备选或使用或/or；当前机位只拍该人物，交谈对象在画外，不拿他人肩背作为前景。用可直接执行的拍摄语言交代相机处在空间哪一侧、透过什么前景看向谁、人物看向画面哪侧；优先无遮挡的中景或中近景，不泛泛写轴线规则。changes只记录实际移动后的完整地点和朝向；抬头、拿物、表情不改位置，不为这些动作填写changes。位置不变时复用原地点。人物脸部和衣服来自真实参考资产，不复述身份/服装，不输出appearance。voice只说明音色。changes.detail仅记原文明示的外观变化（如摘下面罩后面部露出），不复述整套衣服；look只在整套换装时改变，戴帽/摘面罩不改变服装造型。场次开头明示的服装/坐站就是初始状态，不能先沿用上场的旧姿态再做一次换装。actors只为动作注明执行者；sound只是原文声响，不给声响猜测执行者，不据声响添加入画人物。被动句未明说谁做，保留被动句，不擅自补人。clips选择连续原文区间终点through，按完整动作或一次交锋分段，通常6–12秒、2–3个短对白回合，长句给足时长。门响、推门者入场及首个动作留在同段。角色与造型只选提供的键；不输出台词文本和成品提示词。用language指定语言写摄影说明。'
    if task.get('storyboard_skill',{}).get('segment_director'):
        instruction=instruction.replace('当前机位只拍该人物，交谈对象在画外，不拿他人肩背作为前景。','camera给出可用的拍摄方向，不限定单人构图；段内可按关系使用定场、双人及正反打。').replace('不输出台词文本和成品提示词。','不输出台词文本和成品提示词。片段按完整动作与对话交锋分组，不按每次换人说话切成独立视频。')
    obj=ask(api,task,scene_schema(roles,events,props),payload,instruction)
    safe=fallback_scene(cat,roles,events,language,scene);index={e['id']:i for i,e in enumerate(events)}
    safe['space']=text(obj.get('space'),safe['space']);safe['axis']=text(obj.get('axis'),safe['axis'])
    for key,a in roles.items():
        row=obj.get('cast',{}).get(key) if isinstance(obj.get('cast'),dict) else None
        if not isinstance(row,dict):note(task,'blocking','缺少角色调度，使用基础站位',character=a['name']);continue
        base=safe['cast'][key];valid_looks={'L'+str(i) for i,_ in enumerate(a.get('looks',[]),1)}
        for field in ('placement','voice','camera'):base[field]=text(row.get(field),base[field])
        base['appearance']=re.sub(r'\bL\d+\s*[（(]([^）)]+)[）)]',r'\1',base['appearance'])
        if re.search(r'或|\bor\b',base['camera'],re.I):
            base['camera']='';note(task,'blocking','机位含备选，采用本场站位的单一固定机位',character=a['name'])
        if row.get('side') in ('left','center','right'):base['side']=row['side']
        if isinstance(row.get('present'),bool):base['present']=row['present']
        if re.search(r'(?:初始|initially).*?(?:门外|厅外|outside)',base['placement'],re.I):base['present']=False
        base['placement']=re.split(r'随后|subsequently|then |later ',base['placement'],maxsplit=1,flags=re.I)[0].rstrip('，, .')
        if isinstance(row.get('look'),str) and row['look'] in valid_looks:base['look']=row['look']
        changes=[]
        for change in row.get('changes',[]) if isinstance(row.get('changes'),list) else []:
            if not isinstance(change,dict) or not isinstance(change.get('at'),str) or change['at'] not in index:continue
            changes.append({'at':change['at'],'placement':text(change.get('placement'),base['placement']),'present':change.get('present') if isinstance(change.get('present'),bool) else True,'look':change.get('look') if isinstance(change.get('look'),str) and change['look'] in valid_looks else base['look'],'detail':text(change.get('detail'))})
        base['changes']=sorted(changes,key=lambda v:index[v['at']])
        entrance=next((e for e in events if e['kind']=='action' and a['name'] in e['text'] and re.search('冲进|走进|步入|进入大厅',e['text'])),None)
        first_speech=next((e for e in events if e.get('dialogue') and a['name'] in (e['dialogue'].get('members') or [e['dialogue']['speaker']])),None)
        if entrance and (not first_speech or index[entrance['id']]<index[first_speech['id']]):
            base['present']=False;base['placement']='入口外侧，尚未入场。' if language=='zh' else 'Outside the entrance, about to enter.'
            destination='场内，站立面对交谈对象。' if language=='zh' else 'Inside the room, standing toward the other participants.'
            entered=next((v for v in base['changes'] if v['at']==entrance['id']),None)
            if entered:
                if not re.match(r'^(?:At |Behind |Beside |Near |Inside |Standing |Seated |In front |柜台|入口|位于|站在|坐在)',entered['placement'],re.I):entered['placement']=destination
                entered['present']=True
            else:base['changes'].append({'at':entrance['id'],'placement':destination,'present':True,'look':base['look']})
            base['changes']=sorted([v for v in base['changes'] if index[v['at']]>=index[entrance['id']]],key=lambda v:index[v['at']])
    if isinstance(obj.get('actors'),dict):safe['actors']={eid:[k for k in keys if isinstance(k,str) and k in roles] for eid,keys in obj['actors'].items() if eid in index and isinstance(keys,list)}
    normalize_cast_changes(cat,safe,events)
    rows=obj.get('clips',[])
    if isinstance(rows,list):safe['clips']=[{'through':r['through'],'props':[k for k in r.get('props',[]) if isinstance(k,str) and k in props]} for r in rows if isinstance(r,dict) and isinstance(r.get('through'),str) and r['through'] in index and isinstance(r.get('props'),list)]
    safe.update(scene_id=scene_id,language=language,role_ids=list(roles));return safe

def normalize_cast_changes(cat,scene,events):
    index={e['id']:i for i,e in enumerate(events)}
    scene['event_actors']={e['id']:actor_keys(cat,e,scene) for e in events}
    for key,base in scene['cast'].items():
        previous_look=base['look'];valid=[]
        for change in base['changes']:
            event=events[index[change['at']]];explicit=explicit_actors(cat,event)
            if explicit and key not in explicit:continue
            if change['look']!=previous_look and not re.search(r'穿|换装|换上|换成|制服|马甲|衣服|outfit|wearing|changes into',event['text'],re.I):change['look']=previous_look
            previous_look=change['look'];valid.append(change)
        base['changes']=valid
        # A scene-opening declaration is an initial condition, not a future transition.
        first=next((e for e in events if key in explicit_actors(cat,e)),None)
        if first and re.match(re.escape(cat[key]['name'])+r'(?:穿[^。]+?[，,])?(?:坐在|站在|位于)',first['text']):
            declared=next((v for v in valid if v['at']==first['id']),None)
            base['placement']=declared['placement'] if declared else re.sub(r'^(?:穿[^，,]+[，,])?','',re.sub('^'+re.escape(cat[key]['name']),'',first['text'].split('。')[0]))
            if declared:base['look']=declared['look'];base['present']=declared['present']

def explicit_actors(cat,event):
    if event.get('kind') not in ('action','sound'):return []
    names={a['name']:k for k,a in cat.items() if a.get('type')=='角色'}
    if not names:return []
    pattern='|'.join(re.escape(n) for n in sorted(names,key=len,reverse=True))
    groups=re.findall(r'(?:^|[。；;！？])\s*((?:'+pattern+r')(?:(?:、|和|与|及)(?:'+pattern+r'))*)',event['text'])
    agents=re.findall(r'(?:被|由)\s*('+pattern+r')',event['text'])
    return list(dict.fromkeys([names[n] for group in groups for n in re.findall(pattern,group)]+[names[n] for n in agents]))

def actor_keys(cat,event,scene):
    if event.get('dialogue'):
        line=event['dialogue'];names=line.get('members') or [line['speaker']]
        return [k for k,a in cat.items() if a.get('type')=='角色' and a.get('name') in names]
    explicit=explicit_actors(cat,event)
    if explicit:return explicit
    if event.get('kind')=='sound' or '被' in event.get('text',''):return []
    keys=scene.get('actors',{}).get(event['id'])
    if keys:return keys
    return [k for k,a in cat.items() if a.get('type')=='角色' and a['id'] in event.get('role_ids',[])]

def screen_participants(cat,event,scene):
    keys=actor_keys(cat,event,scene)
    # A glance permits an offscreen addressee; physical interaction needs its participants.
    if event.get('kind')=='action' and re.search(r'拍.{0,8}肩|递.{0,12}给|交给|握手|拥抱|按住|拉住|推搡|搂住|扶住',event['text']):
        keys=list(dict.fromkeys(keys+[k for k,a in cat.items() if a.get('type')=='角色' and a['name'] in event['text']]))
    return keys

def event_groups(events):
    """Causal sound/action and explicit complete actions cannot be separated by a clip edge."""
    result=[];i=0
    while i<len(events):
        group=[events[i]];i+=1
        while i<len(events):
            last=group[-1];current=events[i]
            same=last.get('action_group') and last.get('action_group')==current.get('action_group')
            causal=last['kind']=='sound' and current['kind']=='action'
            tail=current['kind'] in ('pause','timing','transition')
            if not (same or causal or tail):break
            group.append(current);i+=1
        result.append(group)
    return result

def split_clips(events,scene):
    groups=event_groups(events);boundary={g[-1]['id']:i for i,g in enumerate(groups)};index={e['id']:i for i,e in enumerate(events)};cuts=[];cursor=0
    for row in scene.get('clips',[]):
        at=index.get(row['through'],-1)
        group_index=next((i for i,g in enumerate(groups) if index[g[-1]['id']]>=at),-1)
        if at<0 or group_index<cursor:continue
        cuts.append((groups[cursor:group_index+1],row.get('props',[])));cursor=group_index+1
    if cursor<len(groups):cuts.append((groups[cursor:],[]))
    output=[]
    for group_list,props in cuts:
        pending=[];budget=0;turns=0
        for group in group_list:
            seconds=sum(e['seconds'] for e in group);count=sum(e['kind']=='dialogue' for e in group)
            if pending and ((budget+seconds>12 and (turns or budget>=10)) or (turns>=3 and count)):
                output.append({'beats':[e for g in pending for e in g],'props':props});pending=[];budget=0;turns=0
            pending.append(group);budget+=seconds;turns+=count
        if pending:output.append({'beats':[e for g in pending for e in g],'props':props})
    return output

def state_at(scene,events,start):
    index={e['id']:i for i,e in enumerate(events)};states={k:{f:copy.deepcopy(v.get(f,'')) for f in ('appearance','placement','side','voice','present','look','camera')} for k,v in scene['cast'].items()}
    for key,base in scene['cast'].items():
        for change in base['changes']:
            if index[change['at']]>=start:break
            states[key].update({f:change[f] for f in ('present','look')})
            if change.get('detail'):states[key]['detail']=change['detail']
            value=change['placement']
            spatial=bool(re.search(r'\b(?:at|behind|beside|near|outside|inside|seated|standing|front)\b|柜台|门口|门外|入口|等候区|办公区|楼梯|场内|大厅|位于|站在|坐在|取号机',value,re.I))
            # Pose changes are additive: a glance/hand gesture cannot erase the room position.
            if spatial:states[key]['placement']=value
            else:states[key]['pose']=value
    # Explicit source transitions outrank an omitted or stale model snapshot.
    for event in events[:start]:
        if event.get('kind')!='action':continue
        posture='站立' if re.search(r'站起|起身',event['text']) else '坐着' if re.search(r'坐下|坐到|坐回',event['text']) else ''
        move=re.search(r'(?:走到|回到|来到|走向|坐到)([^，。；]+)',event['text'])
        for key in scene.get('event_actors',{}).get(event['id'],[]):
            if key not in states:continue
            if posture:states[key]['posture']=posture
            if move:states[key]['placement']='位于'+move[1];states[key]['camera']=''

    return states

def coverage(cat,clip,scene):
    def focus(event):
        keys=screen_participants(cat,event,scene)
        # A group staying at its stations is continuity, not a requirement to
        # squeeze the whole cast into a single camera frame.
        if len(keys)>3 and not any(cat[k]['name'] in event['text'] for k in keys):return []
        return keys
    def groups(events):
        out=[];pending=[];keys=[]
        for position,event in enumerate(events):
            active=focus(event)
            if event['kind']=='sound' and not active and position+1<len(events) and events[position+1]['kind']=='action':
                following=focus(events[position+1])
                if pending and keys and following and set(following)!=set(keys):
                    out.append((pending,keys));pending=[];keys=[]
            same=pending and ((event.get('action_group') and event.get('action_group')==pending[-1].get('action_group')) or (pending[-1]['kind']=='sound' and event['kind']=='action'))
            if pending and active and keys and set(active)!=set(keys) and not same:
                out.append((pending,keys));pending=[];keys=[]
            pending.append(event)
            if active:keys=list(dict.fromkeys(keys+active))
        if pending:out.append((pending,keys))
        return out
    base=[];pending=[]
    for event in clip['beats']:
        if event.get('dialogue'):base.append({'before':pending,'line':event,'after':[]});pending=[]
        else:pending.append(event)
    if base:base[-1]['after']=pending
    else:base=[{'before':pending,'line':None,'after':[]}]
    cuts=[]
    def emit(before,line,after,visible):
        if not before and not line and not after:return
        speakers=actor_keys(cat,line,scene) if line else []
        seconds=sum(e['seconds'] for e in before+after)+(line['seconds'] if line else 0)
        cuts.append({'id':'K'+str(len(cuts)+1),'before':before,'line':line,'after':after,'visible':list(dict.fromkeys(speakers+visible)),'speaker_keys':speakers,'seconds':math.ceil(max(1.8,seconds+.3)*10)/10})
    for item in base:
        spoken=actor_keys(cat,item['line'],scene) if item['line'] else [];parts=groups(item['before'])
        if item['line']:
            leading=[];visible=[]
            for i,(events,actors) in enumerate(parts):
                if i==len(parts)-1 and (not actors or set(actors).intersection(spoken)):leading=events;visible=actors
                else:emit(events,None,[],actors)
            emit(leading,item['line'],[],visible)
        else:
            for events,actors in parts:emit(events,None,[],actors)
        for events,actors in groups(item['after']):
            if cuts and (not actors or set(actors).issubset(set(cuts[-1]['visible']))):
                cuts[-1]['after']+=events;cuts[-1]['seconds']=math.ceil((cuts[-1]['seconds']+sum(e['seconds'] for e in events))*10)/10
            else:emit(events,None,[],actors)
    return cuts

def resources(cat,clip,scene,cuts,states):
    keys=list(dict.fromkeys(k for cut in cuts for k in cut['visible']+cut['speaker_keys']))
    keys+=[k for k,a in cat.items() if a['id']==scene.get('location_id') and k not in keys]
    wanted=clip.get('props',[]);aliases=source.prop_aliases(list(cat.values()));raw='\n'.join(e['text'] for e in clip['beats'])
    named={aid for word,aid in aliases.items() if word in raw}
    keys+=list(dict.fromkeys(k for k,a in cat.items() if a.get('type')=='道具' and a['id'] in named and k not in keys))
    return keys

def fallback_view(cat,cut,states,language,axis,asset_guided=True):
    zh=language=='zh';parts=[];keys=cut['visible'];camera=states.get(keys[0],{}).get('camera','') if len(keys)==1 else '';entering=any(re.search(r'冲进|走进|进入大厅|步入',e['text']) for e in cut['before']);sides={key:states.get(key,{}).get('side','center') for key in keys}
    camera=re.sub(r'[（(]A\d+[）)]','',camera).rstrip('。. ')
    if camera and any(a['name'] in camera and k not in keys for k,a in cat.items() if a.get('type')=='角色'):camera=''
    if len(keys)==2 and (len(set(sides.values()))<2 or 'center' in sides.values()):
        ordered=sorted(keys,key=lambda k:int(k[1:]));sides={ordered[0]:'left',ordered[1]:'right'}
    for key in keys:
        state=copy.deepcopy(states.get(key,{}));appearance=state.get('appearance',cat[key]['name']);side='center' if entering and len(keys)==1 else sides[key]
        if state.get('posture'):
            place=re.sub(r'坐在|站在|坐于|站于','位于',state.get('placement',''))
            place=re.sub(r'(?:^|[，,])(?:坐|站|坐着|站立)(?=[，,]|$)','',place)
            state['placement']=place.rstrip('。')+'，'+state['posture']
        if not asset_guided:
            look=next((l for i,l in enumerate(cat[key].get('looks',[]),1) if state.get('look')=='L'+str(i)),None)
            if look:appearance+=' '+look.get('prompt','')
        if not zh:
            sentences=re.split(r'(?<=[.!])\s+',appearance);appearance=' '.join(sentences[:2]+[v for v in sentences[2:] if re.match(r'Wearing|Black face|With ',v)])[:380].rstrip(' ,.;')
            placement=state.get('placement','standing in the room');other=next((k for k in keys if k!=key),None)
            facing=''
            parts.append('@'+key+(', '+appearance if not asset_guided else '')+', '+placement+', on screen '+side+(', '+state['detail'] if state.get('detail') else ''))
        else:
            facing=''
            parts.append('@'+key+('，'+appearance if not asset_guided else '')+'，'+state.get('placement','').rstrip('。')+'，位于画面'+{'left':'左侧','right':'右侧','center':'中央'}[side]+('，'+state['detail'] if state.get('detail') else ''))
    source_camera=next((e['text'] for e in cut['before'] if e['kind']=='camera'),'')
    if '全景' in source_camera:return ('固定全景。' if zh else 'A steady wide shot. ')+'；'.join(parts)+('。' if zh else '.')
    if entering:return ('相机在室内正对入口，平视全身中景。' if zh else 'Camera inside the room facing the entrance, eye-level full shot. ')+'；'.join(parts)+('。入口和人物全身同时入画，相机固定。' if zh else '. The doorway and the full figure are visible together. The camera stays inside and steady.')+(('开场门关闭，这名入场者在门外正对门，开门后进入画面；取景只有他一人，门后通道空置。' if zh else 'At the opening the door is closed and this sole entrant is directly outside it, entering the frame after opening it; the corridor behind is empty.') if len(keys)==1 else '')
    if zh:return (camera+'。' if camera else '')+('平视双人中景。' if len(parts)==2 else '平视全景。' if len(parts)>2 else '平视中近景。')+'；'.join(parts)+'。相机稳定。'
    return (camera+'. ' if camera else '')+('Eye-level medium two-shot: ' if len(parts)==2 else 'Eye-level wide shot: ' if len(parts)>2 else 'Eye-level medium close-up: ')+'; '.join(parts)+'. The camera is steady.'

def rewrite_schema(clips):
    rows={}
    for clip in clips:
        shots={cut['id']:{'type':'object','properties':{key:{'type':'string'} for key in ('view',)},'required':['view'],'additionalProperties':False} for cut in clip['cuts']}
        rows[clip['id']]={'type':'object','properties':{'title':{'type':'string'},'shots':{'type':'object','properties':shots,'required':list(shots),'additionalProperties':False}},'required':['title','shots'],'additionalProperties':False}
    return {'type':'object','properties':{'clips':{'type':'object','properties':rows,'required':list(rows),'additionalProperties':False}},'required':['clips'],'additionalProperties':False}

def source_visual(cat,event,scene):
    value=event['text'].replace('【','').replace('】','');actors=actor_keys(cat,event,scene)
    for key,a in sorted(cat.items(),key=lambda row:len(row[1]['name']),reverse=True):
        if a['type']=='角色':value=value.replace(a['name'],'@'+key)
    if len(actors)==1:
        subject='@'+actors[0]
        if re.match(r'^[他她]',value):value=subject+value[1:]
        # An inferred performer cannot turn an unassigned passive sentence into a new fact.
    return value

def render_actions(api,p,task,scene,events,cat):
    rows=[e for e in events if e['kind']!='dialogue'];fields={e['id']:{'type':'string','minLength':1} for e in rows}
    if scene['language']=='zh':return {e['id']:source_visual(cat,e,scene) for e in rows}
    if not fields:return {}
    schema={'type':'object','properties':{'actions':{'type':'object','properties':fields,'required':list(fields),'additionalProperties':False}},'required':['actions'],'additionalProperties':False}
    payload={'language':scene['language'],'cast':{k:{'name':cat[k]['name'],'appearance':v['appearance'],'placement':v['placement']} for k,v in scene['cast'].items()},'actions':[{'id':e['id'],'type':e['kind'],'text':e['text'],'performers':['@'+k for k in actor_keys(cat,e,scene)]} for e in rows]}
    instruction='Translate the supplied screenplay actions into concise, concrete filmable sentences in the requested language. Preserve exactly the action order, outcome, number, object states and explicit pauses/transitions. Replace named people with their @A keys. Resolve a pronoun/passive clause only using supplied performers and scene context; otherwise preserve its meaning without inventing an actor. A failed attempt must remain a failed attempt. Do not add movement, speech, camera flourishes, sound effects or new story details. Values must be actual narrative sentences, never source IDs. Sound events remain literal sounds; do not infer a performer, rewrite them into character actions or use them to introduce a person. Staying put is not a freeze-frame; use natural holding-position phrasing unless the script explicitly calls for a freeze. This task is faithful rendering, not creative rewriting.'
    obj=ask(api,task,schema,payload,instruction,5000);values=obj.get('actions',{}) if isinstance(obj.get('actions'),dict) else {};out={}
    for event in rows:
        value=text(values.get(event['id']))
        if not value or re.fullmatch(r'[ABKU]\d+[.。]?',value) or re.search(r'<d>|\[Shot|原文动作|原文事件',value):value=source_visual(cat,event,scene)
        out[event['id']]=value
    missing=[]
    for event in rows:
        actors=actor_keys(cat,event,scene)
        if len(actors)==1 and event['kind']=='action' and not re.search(re.escape('@'+actors[0])+r'(?![A-Za-z0-9_])',out[event['id']]):missing.append(event)
    if missing:
        repair_schema={'type':'object','properties':{'actions':{'type':'object','properties':{e['id']:{'type':'string'} for e in missing},'required':[e['id'] for e in missing],'additionalProperties':False}},'required':['actions'],'additionalProperties':False}
        repair_payload={'language':scene['language'],'actions':[{'id':e['id'],'fact':e['text'],'actor':'@'+actor_keys(cat,e,scene)[0]} for e in missing]}
        fixed=ask(api,task,repair_schema,repair_payload,'Write one faithful active-voice visual sentence per supplied fact. Name the supplied @actor as the performer. Do not assign an actor to a sound or to an unassigned passive clause. Keep the exact action/result. Do not add anything.',1500).get('actions',{})
        for event in missing:
            value=text(fixed.get(event['id'])) if isinstance(fixed,dict) else ''
            out[event['id']]=value if value else source_visual(cat,event,scene)
    return out

def stage_clips(scene,clips,cat):
    # Concrete scene geometry and actual voice sources already determine native-H3
    # coverage. Do not ask a second writer to invent it again.
    zh=scene['language']=='zh'
    def prose(event):
        if zh or event['kind']=='sound':return source_visual(cat,event,scene)
        return scene.get('action_prose',{}).get(event['id'],source_visual(cat,event,scene))
    for clip in clips:
        for cut in clip['cuts']:
            cut['view']=fallback_view(cat,cut,cut.get('states',clip['states']),scene['language'],scene['axis'],scene.get('asset_guided',True))
            for field in ('before','after'):
                cut[field+'_text']=' '.join(prose(e) for e in cut[field] if e['kind']!='camera')
            sequence=cut['before']
            for left,right in zip(sequence,sequence[1:]):
                entrants=explicit_actors(cat,right)
                if left['kind']=='sound' and not explicit_actors(cat,left) and re.search(r'门.*被.*推开',left['text']) and len(entrants)==1 and re.search(r'冲进|走进|步入',right['text']) and cut['visible']==entrants:
                    key=entrants[0]
                    if zh:
                        action=prose(right)
                        action=re.sub(r'冲进|走进|步入','跨过门槛进入',action)
                        action=action.replace('@'+key+'戴面罩','@'+key+'戴着面罩')
                        directed='@'+key+'伸手推开大门，随后'+action
                        cut['before_text']=cut['before_text'].replace(prose(left)+' '+prose(right),directed)
                        cut['director_decisions']=[{'type':'entrance_choreography','actor':key,'supported_by':[left['id'],right['id']],'reason':'将相邻推门声与唯一明确入场者编排为连续可见动作，不改变原文sound归属'}]
            keys=cut['speaker_keys'];cut['delivery']=clip['states'].get(keys[0],{}).get('voice','') if keys else ''
        line=next((e['dialogue'] for e in clip['beats'] if e.get('dialogue')),None)
        action=next((e['text'] for e in clip['beats'] if e['kind']=='action'),None)
        clip['title']=(line['speaker']+'：'+line['text'][:16]) if line else (action[:24] if action else ('场面调度' if zh else 'Scene coverage'))
        clip['summary']=re.split(r'[。.]',scene['space'],maxsplit=1)[0]
        clip['sound']=' '.join(prose(e) for e in clip['beats'] if e['kind']=='sound') or ('轻微室内环境声。' if zh else 'Quiet indoor ambience.')
    return clips

def rewrite(api,p,task,scene,clips,cat):
    payload={'phase':'film_coverage','language':scene['language'],'space':scene['space'],'axis':scene['axis'],'cast':scene['cast'],'assets':[{'key':k,'name':a['name'],'type':a['type']} for k,a in cat.items()],'clips':[]}
    for clip in clips:
        payload['clips'].append({'id':clip['id'],'opening_state':clip['states'],'cuts':[{'id':c['id'],'visible':['@'+k for k in c['visible']],'speaker':['@'+k for k in c['speaker_keys']],'before':[{'id':e['id'],'fact':e['text'],'actors':['@'+k for k in actor_keys(cat,e,scene)]} for e in c['before']],'dialogue':c['line'].get('dialogue') if c['line'] else None,'after':[{'id':e['id'],'fact':e['text'],'actors':['@'+k for k in actor_keys(cat,e,scene)]} for e in c['after']]} for c in clip['cuts']]})
    instruction=task['storyboard_skill_text']+'\n当前film_coverage只输出title与各cut的view。view是这一次独立视频的可拍摄构图：写清visible所有@人物的可辨识外观、相对左右、坐站、面对谁、与柜台/门等环境的关系，并给出无遮挡的平视机位。首cut交代实际说话者与听者，后续仍保证实际说话者可见；相机留在axis同侧。画面像一张能摆出来的静帧，不是剧情总结。不要改写动作、填写对白、声音、delivery或时间，它们由其他模块负责。不要写原文/前情/按要求或负面清单。用language指定语言，@键不翻译。' 
    obj=ask(api,task,rewrite_schema(clips),payload,instruction,6500);rows=obj.get('clips',{}) if isinstance(obj.get('clips'),dict) else {}
    for clip in clips:
        row=rows.get(clip['id'],{});row=row if isinstance(row,dict) else {};clip['title']=text(row.get('title'),'镜头 '+clip['id']);clip['summary']=text(row.get('summary'),scene['space']);clip['sound']=text(row.get('sound'),'本场环境声。' if scene['language']=='zh' else 'Natural room ambience.')
        values=row.get('shots',{}) if isinstance(row.get('shots'),dict) else {}
        for cut in clip['cuts']:
            value=values.get(cut['id'],{});value=value if isinstance(value,dict) else {};view=text(value.get('view'))
            if not view or any(not re.search(re.escape('@'+key)+r'(?![A-Za-z0-9_])',view) for key in cut['visible']) or any(key not in clip['keys'] for key in re.findall(r'@(A\d+)(?![A-Za-z0-9_])',view)):
                view=fallback_view(cat,cut,clip['states'],scene['language'],scene['axis'],scene.get('asset_guided',True));note(task,'coverage','构图缺少实际人物，用本场站位补足',clip=clip['id'],cut=cut['id'])
            cut['view']=fallback_view(cat,cut,cut.get('states',clip['states']),scene['language'],scene['axis'],scene.get('asset_guided',True)) if cut is clip['cuts'][0] else view
            for field in ('before','after'):
                fallback=' '.join(e['text'] for e in cut[field] if e['kind'] not in ('camera','timing'))
                cut[field+'_text']=text(value.get(field),fallback) if cut[field] else ''
            keys=cut['speaker_keys'];voice=clip['states'].get(keys[0],{}).get('voice','') if keys else ''
            cut['delivery']=voice
    for clip in clips:
        for cut in clip['cuts']:
            for field in ('before','after'):
                cut[field+'_text']=' '.join(source_visual(cat,e,scene) if scene['language']=='zh' or e['kind']=='sound' else scene.get('action_prose',{}).get(e['id'],source_visual(cat,e,scene)) for e in cut[field] if e['kind']!='camera')
        clip['summary']=re.split(r'[。.]',scene['space'],maxsplit=1)[0]
        clip['sound']=' '.join(source_visual(cat,e,scene) for e in clip['beats'] if e['kind']=='sound') or ('轻微的室内环境声。' if scene['language']=='zh' else 'Quiet indoor ambience.')
    review_coverage(api,task,scene,clips)
    return clips

def review_coverage(api,task,scene,clips):
    issue={'type':'object','properties':{'clip':{'enum':[c['id'] for c in clips]},'cut':{'type':'string'},'field':{'enum':['view']},'reason':{'type':'string'},'replacement':{'type':'string'}},'required':['clip','cut','field','reason','replacement'],'additionalProperties':False}
    schema={'type':'object','properties':{'issues':{'type':'array','items':issue,'maxItems':3}},'required':['issues'],'additionalProperties':False}
    payload={'scene':{'space':scene['space'],'axis':scene['axis'],'cast':scene['cast']},'clips':[{'id':c['id'],'opening_state':c['states'],'cuts':[{'id':cut['id'],'view':cut['view'],'before_text':cut['before_text'],'after_text':cut['after_text'],'source_before':[e['text'] for e in cut['before']],'source_after':[e['text'] for e in cut['after']],'speaker':cut['speaker_keys'],'visible':cut['visible']} for cut in c['cuts']]} for c in clips]}
    instruction='你是独立的导演连续性审核员。只修构图view字段，动作和对白另由程序负责。只比较当前草稿与源事实：可见说话者、站位/朝向、动作执行者、成败/次数、入场/离场和前后状态是否一致。不评价修辞，不加剧情。没问题返回issues空数组。有明确错误仅返回该cut字段的完整修订replacement（保持原输出语言和@键），指出原因；不得添加对白或镜号时间。'
    result=ask(api,task,schema,payload,instruction,1200);issues=result.get('issues')
    if not isinstance(issues,list):
        note(task,'director_review','独立文本审阅未返回有效结果，未冒充已通过');return
    applied=0
    for issue in issues:
        if not isinstance(issue,dict):continue
        clip=next((c for c in clips if c['id']==issue.get('clip')),None)
        if not clip:continue
        cut=next((c for c in clip['cuts'] if c['id']==issue.get('cut')),None);field=issue.get('field');replacement=text(issue.get('replacement'))
        if not cut or field!='view' or not replacement:continue
        if cut is clip['cuts'][0]:continue
        if field=='view' and any(not re.search(re.escape('@'+key)+r'(?![A-Za-z0-9_])',replacement) for key in cut['visible']):continue
        cut[field]=replacement;applied+=1
    task.setdefault('director_text_reviews',[]).append({'clips':[c['id'] for c in clips],'issues':len(issues),'applied':applied,'scope':'文本导演检查，不是媒体质量验收'})

def labels(api,p,shot,cat,mode):
    slots=b.reference_slots(api,p,shot) if mode in ('reference','video_reference') else []
    mapping={key:next((s['label'] for s in slots if s['asset_id']==a['id']),a['name']) for key,a in cat.items()}
    def apply(value):
        return re.sub(r'@A\d+(?![A-Za-z0-9_])',lambda m:mapping.get(m[0][1:],'character'),value)
    return apply,slots

def compile_shot(api,p,shot,cat=None):
    plan=shot['director_plan'];cat=cat or catalog(p)
    if plan.get('asset_key_ids'):
        current={a['id']:a for a in p['assets']};cat={key:current[aid] for key,aid in plan['asset_key_ids'].items() if aid in current}
    mode=api.video_mode(shot,p);reference=mode in ('reference','video_reference');apply,slots=labels(api,p,shot,cat,mode);language=plan['language'];zh=language=='zh';shot['prompt_language']=language
    main=[apply(plan['space'])];clock=0;timeline=[];line_index=0;speakers={};cues={};described=set()
    for line in shot['dialogue']:
        names=line.get('members') or [line['speaker']]
        for name in names:speakers.setdefault(name,len(speakers)+1)
    for i,cut in enumerate(plan['cuts'],1):
        start=clock;clock+=cut['seconds'];timeline.append({'cut':i,'start':round(start,3),'end':round(clock,3),'speakers':cut['speaker_keys']})
        total_ms=round(start*1000);whole,ms=divmod(total_ms,1000)
        marker='[Shot 1] ' if i==1 else f'[Shot {i}] At {whole//60:02d}:{whole%60:02d}.{ms:03d}, '+('镜头切到' if zh else 'the camera cuts to ')
        body=[apply(cut['view'])]
        if mode=='text' and plan.get('pipeline_revision')=='segment-director-v1':
            for key in cut['visible']:
                if key in described:continue
                described.add(key);asset=cat[key];state=plan['states'].get(key,{})
                look=next((l for l in asset.get('looks',[]) if l['id']==shot.get('character_looks',{}).get(asset['id'])),None)
                identity=' '.join(v for v in (state.get('appearance') or asset.get('prompt',''),look.get('prompt','') if look else '') if v)
                if identity:body.insert(0,asset['name']+'，'+identity+'。')
        if plan.get('pipeline_revision')=='segment-director-v1':
            cast_text='、'.join(apply('@'+key) for key in cut['visible'])
            if cast_text:body.insert(0,('画面人物仅为'+cast_text+'。') if zh else ('The visible cast is limited to '+cast_text+'.'))
        if cut.get('before_text'):body.append(apply(cut['before_text']))
        if cut['line']:
            line=shot['dialogue'][line_index];line_index+=1;names=line.get('members') or [line['speaker']];ids=','.join('S'+str(speakers[n]) for n in names);who=[]
            for name in names:
                key=next((key for key,a in cat.items() if a.get('type')=='角色' and a['name']==name),None);who.append(apply('@'+key) if key else name)
            tag=line.get('language') or ('Chinese' if re.search(r'[\u3400-\u9fff]',line['text']) else 'English');delivery=text(cut.get('delivery'));cue=' and '.join(who)+f' ({ids}) '+(('以'+delivery+'说：') if zh and delivery else ('says in '+delivery+': ') if delivery else 'says: ')
            if len(names)>1:cue=' and '.join(who)+f' ({ids}) '+('齐声说：' if zh else 'say together: ')
            body.append(cue+f"<d>[{tag}] {line['text']}</d>")
        if cut.get('after_text'):body.append(apply(cut['after_text']))
        main.append(marker+' '.join(body))
    shot['duration']=math.ceil(max(clock+.25,float(shot.get('duration',0)),4 if b.is_h3(api.video_model(shot,p)) and plan.get('pipeline_revision')!='segment-director-v1' else 0)*10)/10;shot['coverage_timeline']=timeline
    body='\n'.join(main)
    if b.is_h3(api.video_model(shot,p)):
        entry={'summary':apply(plan['summary']),'detailed_description':body,'integrated_multimodal_description':body,'overall_soundscape':apply(plan['sound']),'non_diegetic_music':'N/A'}
        prompt=b.assemble_h3(api,p,shot,entry,mode)
        if reference:
            parts=b.sections(prompt,True);defs=[];keep=[]
            for slot in slots:
                key=next(k for k,a in cat.items() if a['id']==slot['asset_id']);a=cat[key]
                if a['type']=='角色':
                    defs.append(slot['label']+(' 对应所选角色造型参考。' if zh else ' is the character in the selected look reference.'));keep.append(slot['label']+(': partially_preserved - 保留人物身份与服装外观，姿态按镜头安排。' if zh else ': partially_preserved - Preserve identity and wardrobe appearance; stage the pose as described.'))
                else:
                    defs.append(slot['label']+(' 为'+a['name']+'参考。' if zh else ' provides the '+a['name']+' reference.'));keep.append(slot['label']+(': partially_preserved - 保留参考物件与环境特征，按镜头安排构图。' if zh else ': partially_preserved - Retain reference features; use the described camera and composition.'))
            prompt=prompt.replace(parts['subject_definitions'],'\n'.join(defs) or 'N/A',1).replace(parts['retention_analysis'],'\n'.join(keep) or 'N/A',1)
        if language=='en':
            visible=re.sub(r'<d>.*?</d>|@[^\s,.;:()]+','',body,flags=re.S)
            if len(re.findall(r'[\u3400-\u9fff]',visible))>2*len(re.findall(r'[A-Za-z]+',visible)) and len(re.findall(r'[\u3400-\u9fff]',visible))>5:shot['prompt_language']='zh'
        b.validate(api,p,shot,prompt,mode);shot.update(video_prompt=prompt,prompt_format='h3-official-v1',prompt_video_mode=mode)
    else:shot['video_prompt']=body;shot.pop('prompt_format',None)
    api.sync_duration(shot);api.sync_shot_mentions(p,shot,strict=True);plan['input_signature']=input_signature(shot);return shot

def speech_safe_clips(api,p,clips,scene):
    if not b.is_h3(api.video_model({},p)):return clips
    out=[]
    for clip in clips:
        for cut in coverage(catalog(p),clip,scene):
            out.append({'beats':cut['before']+([cut['line']] if cut['line'] else [])+cut['after'],'props':clip['props']})
    return out

def prepare_clips(api,p,book,scene_id,scene,offset=0):
    cat=catalog(p);events=[e for e in book['events'] if e['scene_id']==scene_id];scene=copy.deepcopy(scene);scene['location_id']=book['scenes'][scene_id].get('location_id');scene['asset_guided']=api.video_mode({},p)!='text';normalize_cast_changes(cat,scene,events);out=[];index={e['id']:i for i,e in enumerate(events)}
    for i,clip in enumerate(speech_safe_clips(api,p,split_clips(events,scene),scene),offset+1):
        clip['id']='U'+str(i);clip['states']=state_at(scene,events,index[clip['beats'][0]['id']]);clip['cuts']=coverage(cat,clip,scene)
        for cut in clip['cuts']:
            first=(cut['before']+([cut['line']] if cut['line'] else [])+cut['after'])[0]
            cut['states']=state_at(scene,events,index[first['id']])
        # Include the current conversation partner even when only one participant
        # speaks in this independently generated clip. Reference lists alone do not stage a listener.
        speaking=[k for cut in clip['cuts'] for k in cut['speaker_keys']]
        if speaking and len(set(speaking))==1 and not b.is_h3(api.video_model({},p)) and clip['states'].get(speaking[0],{}).get('present'):
            pos=index[clip['beats'][0]['id']];near=sorted((e for e in events if e.get('dialogue') and actor_keys(cat,e,scene)!=[speaking[0]]),key=lambda e:abs(index[e['id']]-pos))
            partners=next(([k for k in actor_keys(cat,e,scene) if clip['states'].get(k,{}).get('present') and k not in speaking] for e in near if any(clip['states'].get(k,{}).get('present') and k not in speaking for k in actor_keys(cat,e,scene))),[])
            clip['cuts'][0]['visible']=list(dict.fromkeys(clip['cuts'][0]['visible']+partners))
        clip['keys']=resources(cat,clip,scene,clip['cuts'],clip['states']);out.append(clip)
    return out,scene

def to_shot(api,p,book,scene,clip):
    cat=catalog(p);looks={};states=copy.deepcopy(clip['states'])
    for key in clip['keys']:
        a=cat[key]
        if a['type']!='角色':continue
        short=states[key].get('look');look=next((l for i,l in enumerate(a.get('looks',[]),1) if short=='L'+str(i)),None)
        if look:looks[a['id']]=look['id']
    plan={'version':VERSION,'asset_key_ids':{key:a['id'] for key,a in cat.items()},'pipeline_revision':PIPELINE_REVISION,'script_sha256':book['script_sha256'],'language':scene['language'],'scene_id':scene['scene_id'],'space':scene['space'],'axis':scene['axis'],'states':states,'cuts':copy.deepcopy(clip['cuts']),'summary':clip['summary'],'sound':clip['sound'],'source_span':[clip['beats'][0]['start'],clip['beats'][-1]['end']]}
    dialogue=[copy.deepcopy(e['dialogue']) for e in clip['beats'] if e.get('dialogue')];description='\n'.join(c['view']+' '+c.get('before_text','')+' '+(('说：'+c['line']['text']) if c['line'] else '')+' '+c.get('after_text','') for c in clip['cuts'])
    shot={'id':api.uid(),'title':clip['title'],'description':description,'image_prompt':clip['cuts'][0]['view'],'video_prompt':'','duration':sum(c['seconds'] for c in clip['cuts'])+.25,'dialogue':dialogue,'asset_ids':[cat[k]['id'] for k in clip['keys']],'character_looks':looks,'versions':[],'video_override':None,'director_plan':plan,'source_contract':{'version':'director-source-v1','script_sha256':book['script_sha256'],'scene_id':scene['scene_id'],'span':plan['source_span'],'beats':copy.deepcopy(clip['beats'])},'timing':{'method':'coverage-budget-v1','verified_by_audio':False}}
    # Model aliases are private. Public descriptions and image prompts use actual bindings.
    apply,_=labels(api,p,shot,cat,api.video_mode(shot,p));shot['description']=apply(description);shot['image_prompt']=apply(shot['image_prompt'])
    return shot

def plan(api,p,task):
    if task.get('storyboard_skill',{}).get('segment_director'):return segment_plan(api,p,task)
    book=source.ledger(api,p);scenes=list(book['scenes']);shots=[];cat=catalog(p);offset=0;all_scenes={}
    for si,scene_id in enumerate(scenes):
        events=[e for e in book['events'] if e['scene_id']==scene_id]
        if not events:continue
        b.progress(api,task,'analysis',si,len(scenes));scene=direct_scene(api,p,task,book,scene_id,events);scene['action_prose']=render_actions(api,p,task,scene,events,cat);clips,scene=prepare_clips(api,p,book,scene_id,scene,offset);offset+=len(clips);all_scenes[scene_id]=scene
        for start in range(0,len(clips),2):
            batch=stage_clips(scene,clips[start:start+2],cat) if b.is_h3(api.video_model({},p)) else rewrite(api,p,task,scene,clips[start:start+2],cat)
            for clip in batch:
                shot=to_shot(api,p,book,scene,clip)
                if task.get('storyboard_stage')!='planning':compile_shot(api,p,shot,cat)
                else:
                    api.sync_shot_mentions(p,shot,strict=True);shot['director_plan']['input_signature']=input_signature(shot)
                api.validate_resources(dict(p,shots=[shot]));shots.append(shot)
            b.progress(api,task,'h3_prompts',len(shots),max(len(shots),offset))
        task.setdefault('director_location_context',{})[scene.get('location_id')]={'space':scene['space'],'axis':scene['axis'],'cast':state_at(scene,events,len(events))}
    task['director_scenes']=all_scenes;task['storyboard_draft']=copy.deepcopy(shots);task['storyboard_source_coverage']={'events':len(book['events']),'dialogue':sum(bool(e.get('dialogue')) for e in book['events']),'scenes':len(scenes),'shots':len(shots),'method':VERSION};b.progress(api,task,'complete',len(shots),len(shots));return {'shots':shots}

def input_signature(shot):
    return hashlib.sha256(json.dumps({k:shot.get(k) for k in ('description','image_prompt','dialogue','asset_ids','character_looks')},ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def write_existing(api,p,task):
    shots=copy.deepcopy(p['shots']);selected=set(task['storyboard_shot_ids']);count=0;scene_cache={}
    for index,shot in enumerate(shots):
        if shot['id'] not in selected:continue
        plan=shot.get('director_plan',{})
        if plan.get('version')==VERSION and plan.get('script_sha256')==hashlib.sha256(p['script'].encode()).hexdigest() and plan.get('input_signature')==input_signature(shot):
            if plan.get('pipeline_revision') not in (PIPELINE_REVISION,'segment-director-v1'):
                # Rewriting an unchanged old generated prompt must not recycle its bad actor/camera cache.
                book=source.ledger(api,p);sid=plan['scene_id']
                if sid not in scene_cache:
                    events=[e for e in book['events'] if e['scene_id']==sid]
                    scene=direct_scene(api,p,task,book,sid,events);scene['action_prose']=render_actions(api,p,task,scene,events,catalog(p));scene_cache[sid]=scene
                shots[index]=restage_draft(api,dict(p,shots=[shot]),{sid:scene_cache[sid]})[0]
                note(task,'upgrade','旧生成镜头重新建立本场调度，未复用旧声响归因或动作缓存',shot_id=shot['id'])
            else:compile_shot(api,p,shot)
        else:
            # Editing a shot is authoritative. Never resurrect stale source dialogue,
            # asset choices or descriptions when the user only asks for a new prompt.
            local=copy.deepcopy(task);local['storyboard_skill'].pop('director_format',None);local['storyboard_skill'].pop('source_owned_events',None);local['storyboard_shot_ids']=[shot['id']];local.pop('project_id',None)
            local['storyboard_skill_text']=(api.ROOT/'docs/skills/shotdesk-storyboard/references/legacy-v8.md').read_text()
            compatible=copy.deepcopy(shot);compatible.pop('director_plan',None)
            shots[index]=b.write_existing(api,dict(p,shots=[compatible]),local)['shots'][0]
            note(task,'compatibility','旧镜头或人工修改的镜头按当前内容编写，不覆盖编辑；重新生成分镜才启用新的场面调度',shot_id=shot['id'])
        count+=1;b.progress(api,task,'h3_prompts',count,len(selected))
    return {'shots':shots}


def restage_draft(api,p,scenes):
    """Explicit draft repair with reviewed scene decisions; keeps shot IDs and media.

    Refuse stale or manually edited shots rather than restore old source content.
    The caller owns backup, concurrent-input comparison and saving the result.
    """
    book=source.ledger(api,p);cat=catalog(p);shots=copy.deepcopy(p['shots'])
    for shot in shots:
        contract=shot.get('source_contract',{});old=shot.get('director_plan',{})
        if contract.get('script_sha256')!=book['script_sha256'] or old.get('input_signature')!=input_signature(shot):
            raise ValueError('镜头已人工修改或剧本已变化，不能自动重新调度：'+shot.get('title',''))
        sid=contract['scene_id'];scene=copy.deepcopy(scenes[sid]);events=[e for e in book['events'] if e['scene_id']==sid];index={e['id']:i for i,e in enumerate(events)}
        normalize_cast_changes(cat,scene,events);scene['asset_guided']=api.video_mode(shot,p)!='text';scene['location_id']=book['scenes'][sid].get('location_id')
        clip={'id':shot['id'],'beats':copy.deepcopy(contract['beats']),'props':[]};clip['states']=state_at(scene,events,index[clip['beats'][0]['id']]);clip['cuts']=coverage(cat,clip,scene)
        for cut in clip['cuts']:
            first=(cut['before']+([cut['line']] if cut['line'] else [])+cut['after'])[0];cut['states']=state_at(scene,events,index[first['id']])
        clip['keys']=resources(cat,clip,scene,clip['cuts'],clip['states']);stage_clips(scene,[clip],cat)
        replacement=to_shot(api,p,book,scene,clip)
        for field in ('description','image_prompt','asset_ids','character_looks','director_plan','source_contract'):shot[field]=replacement[field]
        compile_shot(api,p,shot,cat)
        api.validate_resources(dict(p,shots=[shot]))
    return shots


def segment_schema(clips):
    fields={}
    for clip in clips:
        cuts={c['id']:{'type':'object','properties':{**{k:{'type':'string'} for k in ('view',)},'visible':{'type':'array','items':{'enum':(clip.get('allowed_roles') or list(clip['states']))} if clip['states'] else {'type':'string'}}},'required':['view','visible'],'additionalProperties':False} for c in clip['cuts']}
        fields[clip['id']]={'type':'object','properties':{'title':{'type':'string'},'cuts':{'type':'object','properties':cuts,'required':list(cuts),'additionalProperties':False}},'required':['title','cuts'],'additionalProperties':False}
    return {'type':'object','properties':{'segments':{'type':'object','properties':fields,'required':list(fields),'additionalProperties':False}},'required':['segments'],'additionalProperties':False}


def direct_segments(api,p,task,scene,clips,cat):
    """The director stages read-only source events; the compiler owns action and dialogue.

    Structural fallback is explicitly a draft needing review, not a silent quality pass.
    Local repair is bounded to one call and cannot rewrite other segments.
    """
    payload={'phase':'segment_direction','scene_context':{'space':scene['space'],'axis':scene['axis']},'language':scene['language'],'space':scene['space'],'axis':scene['axis'],'cast':{k:{f:v.get(f) for f in (('placement','side','present','look') if scene.get('asset_guided',True) else ('placement','side','present','look','appearance'))} for k,v in scene['cast'].items()},'assets':[{'key':k,'name':a['name'],'type':a['type']} for k,a in cat.items()],'segments':[]}
    for clip in clips:
        payload['segments'].append({'id':clip['id'],'opening_state':{k:{f:v.get(f) for f in ('placement','side','present','look','posture','detail')} for k,v in clip['states'].items() if k in clip.get('allowed_roles',clip['states'])},'cuts':[{'id':c['id'],'opening_state':{k:{f:v.get(f) for f in ('placement','side','present','look','posture','detail')} for k,v in c['states'].items() if k in clip.get('allowed_roles',clip['states'])},'visible':c['visible'],'speaker':c['speaker_keys'],'before':[{'id':e['id'],'kind':e['kind'],'text':e['text']} for e in c['before']],'dialogue':c['line'].get('dialogue') if c['line'] else None,'after':[{'id':e['id'],'kind':e['kind'],'text':e['text']} for e in c['after']]} for c in clip['cuts']]})
    instruction=task['storyboard_skill_text']+'\n当前segment_direction只输出title、cuts.view及cuts.visible。按所给每个cut设计实际开场构图：谁在哪里、朝向谁，相机在何处、景别和拍摄方向；visible仅为本切实际入画的角色键，画外人不加入。before/dialogue/after是只读的本切事件，不改写、不提前或补写它们。人物外观由参考提供，不重述衣服，不新增人物。禁止将整场剧情塞进某一cut。有speaker时镜头主角是该speaker，不以听者特写覆盖他的台词。其他角色作前景或背景时也必须列在visible。'
    available={k for c in clips for k in c.get('allowed_roles',c['states'])}
    payload['cast']={k:{'name':cat[k]['name']} for k in available}
    payload['assets']=[a for a in payload['assets'] if a['type']!='角色' or a['key'] in available]
    schema=segment_schema(clips);value=ask(api,task,schema,payload,instruction,6500)
    def normalize_row(row,clip):
        if not isinstance(row,dict) or not isinstance(row.get('cuts'),dict):return row
        # Accept exact current public labels as well as private aliases; never guess IDs.
        aliases={}
        for key,a in cat.items():
            aliases['@'+a['name']]='@'+key
            if a.get('type')=='角色' and sum(v['name']==a['name'] for v in cat.values())==1:aliases[a['name']]='@'+key
            for number,look in enumerate(a.get('looks',[]),1):
                if clip['states'].get(key,{}).get('look')=='L'+str(number):aliases['@'+a['name']+'·'+look.get('name','')]='@'+key
        pattern='|'.join(re.escape(k) for k in sorted(aliases,key=len,reverse=True))
        for cut in row['cuts'].values():
            if isinstance(cut,dict):
                for field in ('view','before_text','after_text'):
                    if isinstance(cut.get(field),str):
                        value=re.sub(r'@?[\u3400-\u9fff]+[（(](A\d+)[）)]',lambda m:'@'+m[1] if m[1] in cat else m[0],cut[field])
                        names='|'.join(re.escape(a['name']) for a in sorted(cat.values(),key=lambda a:len(a['name']),reverse=True))
                        value=re.sub(r'@?(?:'+names+r')(A\d+)(?![A-Za-z0-9_])',lambda m:'@'+m[1] if m[1] in cat else m[0],value)
                        cut[field]=re.sub(pattern,lambda m:aliases[m[0]],value) if pattern else value
                        cut[field]=re.sub(r'(@A\d+)[（(]\1[）)]',r'\1',cut[field])
        return row
    def issues_for(clip,row):
        row=normalize_row(row,clip)
        problems=[]
        if not isinstance(row,dict):return ['缺少片段']
        for c in clip['cuts']:
            r=row.get('cuts',{}).get(c['id'],{}) if isinstance(row.get('cuts'),dict) else {}
            if not isinstance(r,dict):problems.append(c['id']+'缺少镜头');continue
            view=text(r.get('view'));alltext=view
            declared=r.get('visible',c['visible'])
            if not isinstance(declared,list) or any(k not in clip.get('allowed_roles',clip['states']) for k in declared):problems.append(c['id']+'入画角色不属于本场')
            
            if not view:problems.append(c['id']+'缺少构图')
            declared_keys=set(declared) if isinstance(declared,list) else set()
            extras=[k for k in re.findall(r'@(A\d+)(?![A-Za-z0-9_])[，, ]*(?:坐|站|位于|出现在|的(?:肩|身影|背影|后脑))',view) if k in cat and cat[k]['type']=='角色' and k not in declared_keys.union(c['visible'])]
            if extras:problems.append(c['id']+'构图人物必须与visible一致，不出现未入画者的肩背/身影：'+','.join(extras))
            if c['speaker_keys']:
                targets=re.findall(r'(?:相机|机位|镜头)[^。；;]{0,50}?(?:正对|聚焦于?|拍摄|焦点在)\s*@(A\d+)(?![A-Za-z0-9_])',view)
                if any(k not in c['speaker_keys'] for k in targets):problems.append(c['id']+'镜头主角须是实际说话者'+','.join(c['speaker_keys'])+'，不要对准听者替他说话')

            refs=re.findall(r'@(A\d+)(?![A-Za-z0-9_])',alltext)
            if any(k not in cat for k in re.findall(r'@([A-Za-z][A-Za-z0-9_]*)',alltext)):problems.append(c['id']+'人物键写法无效')
            if any(k not in cat or (cat[k]['type']=='角色' and k not in clip.get('allowed_roles',clip['states'])) for k in refs):problems.append(c['id']+'引用不存在或不在本场的资源')
            if re.search(r'<d>|\[Shot|原文动作|原文事件',alltext):problems.append(c['id']+'混入协议或源文标签')
        return problems
    rows=value.get('segments',{}) if isinstance(value.get('segments'),dict) else {}
    for clip in clips:
        row=rows.get(clip['id']);problems=issues_for(clip,row)
        if problems:
            local=dict(payload,segments=[r for r in payload['segments'] if r['id']==clip['id']],draft=row,issues=problems)
            repaired=ask(api,task,segment_schema([clip]),local,instruction+'\n只修这个片段，完整返回该片段。',3000)
            row=repaired.get('segments',{}).get(clip['id']) if isinstance(repaired.get('segments'),dict) else None
            problems=issues_for(clip,row)
        if problems:
            clip['review_required']=True
            note(task,'segment_direction','片段导演草稿待审核，保留可恢复的基础构图',segment=clip['id'],issues=problems)
            continue
        clip['title']=text(row.get('title'),clip['title']);clip['summary']=clip['title']
        for cut in clip['cuts']:
            r=row['cuts'][cut['id']]
            cut['view']=r['view'].strip()
            # Visible listeners and props belong to the director's actual composition,
            # not to a preselected one-speaker reference list.
            declared=r.get('visible',cut['visible'])
            actual=[key for key in declared if key in clip['states']] if isinstance(declared,list) else []
            cut['visible']=list(dict.fromkeys(cut['visible']+actual))
            for key in cut['visible']:
                if not re.search(re.escape('@'+key)+r'(?![A-Za-z0-9_])',cut['view']):
                    cut['view']+=' @'+key+'，'+cut['states'].get(key,{}).get('placement','')+'。'
            for key in cut['visible']:
                if key not in clip['keys']:clip['keys'].append(key)
            for key in re.findall(r'@(A\d+)(?![A-Za-z0-9_])',cut['view']):
                if cat[key]['type']!='角色' and key not in clip['keys']:clip['keys'].append(key)
            for field in ('view','before_text','after_text'):
                for key in re.findall(r'@(A\d+)(?![A-Za-z0-9_])',cut[field]):
                    if cat[key]['type']=='角色' and key not in cut['visible']:
                        cut[field]=re.sub(re.escape('@'+key)+r'(?![A-Za-z0-9_])',lambda m:cat[key]['name'],cut[field])
                    elif key not in clip['keys']:clip['keys'].append(key)

    return clips


def segment_plan(api,p,task):
    book=source.ledger(api,p);cat=catalog(p);shots=[];scenes=list(book['scenes']);all_scenes={}
    for si,sid in enumerate(scenes):
        events=[e for e in book['events'] if e['scene_id']==sid]
        if not events:continue
        b.progress(api,task,'analysis',si,len(scenes))
        scene=direct_scene(api,p,task,book,sid,events)
        scene.update(location_id=book['scenes'][sid].get('location_id'),asset_guided=api.video_mode({},p)!='text',source_context=[{'kind':e['kind'],'text':e['text']} for e in events])
        for state in scene['cast'].values():state['camera']=''
        if scene['language']=='en':scene['action_prose']=render_actions(api,p,task,scene,events,cat)
        index={e['id']:i for i,e in enumerate(events)};clips=split_clips(events,scene)
        for i,clip in enumerate(clips,len(shots)+1):
            clip.update(id='U'+str(i),states=state_at(scene,events,index[clip['beats'][0]['id']]))
            clip['allowed_roles']=list(dict.fromkeys(k for event in events[:index[clip['beats'][-1]['id']]+1] for k in actor_keys(cat,event,scene)))
            clip['cuts']=coverage(cat,clip,scene)
            for cut in clip['cuts']:
                first=(cut['before']+([cut['line']] if cut['line'] else [])+cut['after'])[0]
                cut['states']=state_at(scene,events,index[first['id']])
            clip['keys']=resources(cat,clip,scene,clip['cuts'],clip['states'])
        # The mechanical draft is recovery material only; valid director prose replaces it.
        stage_clips(scene,clips,cat)
        for start in range(0,len(clips),3):
            baseline={c['id']:copy.deepcopy(c) for c in clips[start:start+3]}
            batch=direct_segments(api,p,task,scene,clips[start:start+3],cat)
            for clip in batch:
                shot=to_shot(api,p,book,scene,clip)
                shot['director_plan']['pipeline_revision']='segment-director-v1'
                shot['timing']['method']='segment-source-budget-v1'
                shot['director_plan']['review_required']=bool(clip.get('review_required'))
                if clip.get('review_required'):shot['review_warnings']=['导演片段未完成，请审核后生成媒体']
                if task.get('storyboard_stage')!='planning':
                    try:compile_shot(api,p,shot,cat)
                    except ValueError as error:
                        # Recover a malformed director rendering from typed source data,
                        # never suppress cancellation/service failures or mark it approved.
                        note(task,'segment_compile','导演表达未能编译，保留原文的基础草稿待审核',segment=clip['id'],detail=str(error))
                        fallback=baseline[clip['id']];replacement=to_shot(api,p,book,scene,fallback);replacement['id']=shot['id'];shot=replacement
                        shot['director_plan'].update(pipeline_revision='segment-director-v1',review_required=True)
                        shot['review_warnings']=['导演表达未能编译，已恢复基础构图，请审核后生成媒体']
                        shot['timing']['method']='segment-source-budget-v1';compile_shot(api,p,shot,cat)
                else:
                    api.sync_shot_mentions(p,shot,strict=True);shot['director_plan']['input_signature']=input_signature(shot)
                api.validate_resources(dict(p,shots=[shot]));shots.append(shot)
            task['storyboard_draft']=copy.deepcopy(shots)
            b.progress(api,task,'h3_prompts',len(shots),len(shots)+len(clips)-start-len(batch))
        all_scenes[sid]=scene
        task.setdefault('director_location_context',{})[scene.get('location_id')]={'space':scene['space'],'axis':scene['axis'],'cast':state_at(scene,events,len(events))}
    task['director_scenes']=all_scenes
    task['storyboard_source_coverage']={'events':len(book['events']),'dialogue':sum(bool(e.get('dialogue')) for e in book['events']),'scenes':len(scenes),'shots':len(shots),'method':'segment-director-v1'}
    b.progress(api,task,'complete',len(shots),len(shots));return {'shots':shots}
