"""Source-owned story events, constrained camera recipes, deterministic prompt compilation.

The director model chooses how to film. It never supplies replacement story prose.
"""
import copy,hashlib,json,math,re

FRAMES=('全景','中景','近景','特写','双人中景','过肩')
MOVES=('固定机位','缓慢推进','缓慢拉远','跟随主体')
META=re.compile(r'^(?:预计时长|场名|剧终|第.{0,8}[集幕]|\d+-\d+\s|日\s*[·・]\s*内|夜\s*[·・]\s*外)')


def speech_seconds(text):
    return len(re.findall(r'[\u3400-\u9fff\d]',text))/4+len(re.findall(r'[A-Za-z]+',text))/2.5


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def ledger(api,p):
    """Read screenplay lines into immutable, ordered, scene-scoped source events."""
    import storyboard as b
    source=p['script'];spoken={line['start']:line for line in b.script_dialogue_lines(source,p.get('assets',[]),True)}
    assets=p.get('assets',[]);roles=[a for a in assets if a.get('type')=='角色'];locations=[a for a in assets if a.get('type')=='场景']
    scene='scene-1';scene_intro=[];location=None;events=[];offset=0;previous='';recent=[];context={}
    for raw in source.splitlines(keepends=True):
        text=raw.strip();start=offset;offset+=len(raw)
        if not text:continue
        if re.fullmatch(r'场景\s*\d+.*',text):
            scene='scene-'+str(len(context)+1);scene_intro=[text];location=None;recent=[];context[scene]={'heading':scene_intro,'location_id':None}
            previous=text;continue
        context.setdefault(scene,{'heading':scene_intro,'location_id':None})
        loc=next((a for a in locations if a.get('name')==text),None)
        if loc:location=loc['id'];context[scene]['location_id']=location;previous=text;continue
        if re.fullmatch(r'[日夜]\s*[·・]\s*[内外]',text):
            context[scene]['heading'].append(text);previous=text;continue
        if text.startswith('【场名') or META.match(text):previous=text;continue
        if text.startswith('【次日') or text.startswith('【构图呼应'):
            context[scene]['heading'].append(text);previous=text;continue
        line=spoken.get(start)
        if line is None:
            candidate=re.match(r'^([^：:\n]{1,12})[：:]\s*(.+)$',text)
            # Preserve uncatalogued speakers, but not labels introduced by a preceding caption heading.
            if candidate and not roles and not text.startswith(('【','[')) and not previous.endswith(('：',':')) and not re.match(r'场景|时间|地点|标题|人物|胸牌|电脑屏幕',candidate[1]) and not b.STAGE_DIRECTION.fullmatch(candidate[2]):
                line={'speaker':candidate[1].strip(),'text':candidate[2],'start':start}
        known=[a['id'] for a in roles if a.get('name') and a['name'] in text]
        if line:
            names=line.get('members') or [line['speaker']]
            known=list(dict.fromkeys(known+[a['id'] for a in roles if a.get('name') in names]));kind='dialogue';content=line['text'];cost=speech_seconds(content)+.2
            recent=list(dict.fromkeys(names+recent))[:3]
        else:
            content=text;kind='action';cost=min(4,max(1,len(text)/18))
            if text.startswith('【声音】'):kind='sound';content=text[len('【声音】'):];cost=.4
            elif text.startswith('【') and text.endswith('】'):
                if re.search(r'保留完整动作|合计约',text):kind='timing';cost=0
                elif re.search(r'停顿|停留',text):kind='pause';cost=float((re.search(r'(\d+(?:\.\d+)?)\s*秒',text) or [None,1])[1])
                elif re.search(r'定格|切黑|硬切|渐黑|切至|切回',text):kind='transition';cost=float((re.search(r'(\d+(?:\.\d+)?)\s*秒',text) or [None,.4])[1])
                elif re.search(r'全景|中景|近景|特写|机位|镜头|过肩',text):kind='camera';cost=0
                else:kind='direction';cost=0
            if text.startswith('【') and not text.endswith('】') and re.search(r'^【[^】]*(?:全景|中景|近景|特写|过肩)[^】]*】',text):kind='camera'
            if re.match(r'^(他|她|两人|三人|四人|众人|大家)',text):
                count=2 if text.startswith('两人') else 3 if text.startswith(('三人','众人','大家')) else 1
                known=list(dict.fromkeys(known+[a['id'] for a in roles if a.get('name') in recent[:count]]))
            names=[a['name'] for a in roles if a['id'] in known]
            if names:recent=list(dict.fromkeys(names+recent))[:3]
        events.append({'id':'B'+str(len(events)+1),'scene_id':scene,'kind':kind,'text':content,'start':start,'end':offset,'seconds':round(cost,2),'role_ids':known,**({'dialogue':{k:copy.deepcopy(line[k]) for k in ('speaker','text','members') if k in line}} if line else {})})
        previous=text
    # An action-duration note stretches its adjacent action group; it is not an
    # instruction to wait silently and only then perform those actions.
    for i,event in enumerate(events):
        if event['kind']!='timing':continue
        target=re.search(r'(\d+(?:\.\d+)?)\s*秒',event['text'])
        if not target:continue
        adjacent=events[i+1:] if '组' in event['text'] else list(reversed(events[:i]));group=[]
        for candidate in adjacent:
            if candidate['scene_id']!=event['scene_id'] or candidate['kind']!='action':break
            group.append(candidate)
            if len(group)==3:break
        budget=sum(e['seconds'] for e in group)
        if group:
            for e in group+[event]:e['action_group']=event['id']
        if budget and budget<float(target[1]):
            for e in group:e['seconds']=round(e['seconds']*float(target[1])/budget,2)
    for value in context.values():
        if value['location_id'] is None and len(locations)==1:value['location_id']=locations[0]['id']
    return {'version':'source-events-v1','script_sha256':hashlib.sha256(source.encode()).hexdigest(),'scenes':context,'events':events}


def units(book,target=10):
    """Partition source events without dropping actions or crossing scene/time boundaries."""
    result=[];pending=[];seconds=0;speech=0
    def flush():
        nonlocal pending,seconds,speech
        if pending:
            result.append({'id':'U'+str(len(result)+1),'scene_id':pending[0]['scene_id'],'beats':pending,'duration':round(max(2,seconds),1)})
        pending=[];seconds=0;speech=0
    for beat in book['events']:
        # Directions immediately following an action stay with it, even if the estimate grows.
        tail=beat['kind'] in ('pause','transition','sound','direction','timing')
        camera=beat['kind']=='camera' or beat['text'].startswith('【') and beat['kind']=='pause' and re.search('全景|中景|近景|特写|过肩',beat['text'])
        same_group=pending and beat.get('action_group') and beat.get('action_group')==pending[-1].get('action_group')
        force=pending and (beat['scene_id']!=pending[0]['scene_id'] or camera or (not same_group and not tail and seconds+beat['seconds']>target and (speech or seconds>=target)) or (speech>=4 and beat['kind']=='dialogue'))
        if force:flush()
        pending.append(copy.deepcopy(beat));seconds+=beat['seconds'];speech+=beat['kind']=='dialogue'
        if beat['kind']=='transition' and not re.search(r'定格',beat['text']):flush()
    flush()
    # A final sound after a freeze belongs to the same ending, not a new unrelated scene.
    if len(result)>1 and all(x['kind']=='sound' for x in result[-1]['beats']) and result[-2]['scene_id']==result[-1]['scene_id']:
        result[-2]['beats']+=result[-1]['beats'];result[-2]['duration']+=result[-1]['duration'];result.pop()
    return result


def prop_aliases(assets):
    # Use asset names and unambiguous lexical suffixes, never invented object descriptions.
    aliases={}
    for asset in assets:
        if asset.get('type')!='道具':continue
        name=asset.get('name','')
        for part in [name]+re.split(r'[与和、/·]',name):
            if not part:continue
            aliases.setdefault(part,set()).add(asset['id'])
            for size in range(2,min(4,len(part))+1):aliases.setdefault(part[-size:],set()).add(asset['id'])
            # Strip descriptive asset prefixes, not arbitrary one-character suffixes
            # (e.g. 招聘启事 must never bind every occurrence of 事).
            noun=re.sub(r'^(?:道具|旧|新)','',part)
            if noun:aliases.setdefault(noun,set()).add(asset['id'])
    return {word:next(iter(ids)) for word,ids in aliases.items() if len(ids)==1}


def resource_ids(p,unit,scene,prior):
    ids=list(dict.fromkeys(aid for beat in unit['beats'] for aid in beat['role_ids']))
    if not ids:
        ids=list(dict.fromkeys(aid for beat in prior[-2:] for aid in beat['role_ids']))
    text='\n'.join(beat['text'] for beat in unit['beats']+prior);aliases=prop_aliases(p['assets'])
    ids+=list(dict.fromkeys(aid for word,aid in aliases.items() if word in text and aid not in ids))
    if scene.get('location_id') and scene['location_id'] not in ids:ids.append(scene['location_id'])
    return ids


def direct(api,p,task,book,groups):
    """Optional AI direction. Malformed choices fall back to source-compatible camera recipes."""
    import storyboard as b
    assets={a['id']:a for a in p['assets']};recipes={};batch_size=10
    handles={aid:'R'+str(i) for i,(aid,a) in enumerate(assets.items(),1) if a.get('type')=='角色'};original_ids={v:k for k,v in handles.items()}
    look_handles={aid:{l['id']:'L'+str(i) for i,l in enumerate(a.get('looks',[]),1)} for aid,a in assets.items() if aid in handles}
    for start in range(0,len(groups),batch_size):
        batch=groups[start:start+batch_size];b.progress(api,task,'analysis',start,len(groups));choices=[];payload=[]
        for unit in batch:
            roles=list(dict.fromkeys(aid for beat in unit['beats'] for aid in beat['role_ids']));props={'unit_id':{'const':unit['id']},'title':{'type':'string','maxLength':40},'framing':{'enum':list(FRAMES)},'movement':{'enum':list(MOVES)},'focus_id':{'enum':[handles[aid] for aid in roles]+[None]},'looks':{'type':'object','properties':{handles[aid]:{'enum':list(look_handles[aid].values())+[None]} for aid in roles},'additionalProperties':False}}
            previous=[beat for beat in book['events'] if beat['scene_id']==unit['scene_id'] and beat['end']<=unit['beats'][0]['start'] and beat['kind']=='action'][-12:]
            props['continuity_ids']={'type':'array','items':{'enum':[beat['id'] for beat in previous]} if previous else {'type':'string'},'maxItems':min(3,len(previous))}
            choices.append({'type':'object','properties':props,'required':list(props),'additionalProperties':False})
            payload.append({'unit_id':unit['id'],'scene':book['scenes'][unit['scene_id']],'facts':[{**{k:beat[k] for k in ('id','kind','text')},'role_ids':[handles[aid] for aid in beat['role_ids']]} for beat in unit['beats']],'previous_facts':[{k:beat[k] for k in ('id','text')} for beat in previous]})
        schema={'type':'object','properties':{'recipes':{'type':'array','items':{'anyOf':choices},'maxItems':len(batch)}},'required':['recipes'],'additionalProperties':False}
        message=task['storyboard_skill_text']
        response=api.Q.text_request({'model':task['model'],'messages':[{'role':'system','content':message},{'role':'user','content':json.dumps({'units':payload,'characters':[{'id':handles[a['id']],'name':a['name'],'looks':[{'id':look_handles[a['id']][l['id']],'name':l.get('name'),'description':l.get('prompt','')} for l in a.get('looks',[])]} for a in p['assets'] if a.get('type')=='角色']},ensure_ascii=False)}],'temperature':.2,'max_tokens':3500,'response_format':{'type':'json_schema','json_schema':{'name':'source_camera_recipes','schema':schema}},'chat_template_kwargs':{'enable_thinking':False}},task)
        try:
            choice=response['choices'][0];raw=choice['message']['content'];raw=re.sub(r'<think>.*?</think>','',raw,flags=re.S);obj=json.loads(raw[raw.find('{'):raw.rfind('}')+1]);rows=obj.get('recipes',[])
            if not isinstance(rows,list):rows=[]
        except (ValueError,TypeError,KeyError,IndexError):rows=[]
        allowed={unit['id']:unit for unit in batch}
        for recipe in rows:
            if not isinstance(recipe,dict) or not isinstance(recipe.get('unit_id'),str) or recipe['unit_id'] not in allowed:continue
            unit=allowed[recipe['unit_id']];roles={aid for beat in unit['beats'] for aid in beat['role_ids']}
            recipe=copy.deepcopy(recipe);recipe['focus_id']=original_ids.get(recipe.get('focus_id')) if isinstance(recipe.get('focus_id'),str) else None
            recipe['looks']={original_ids[handle]:next((lid for lid,short in look_handles[original_ids[handle]].items() if short==look),None) for handle,look in recipe.get('looks',{}).items() if handle in original_ids} if isinstance(recipe.get('looks'),dict) else {}
            safe={'title':str(recipe.get('title',''))[:40],'framing':recipe.get('framing') if recipe.get('framing') in FRAMES else '中景','movement':recipe.get('movement') if recipe.get('movement') in MOVES else '固定机位','focus_id':recipe.get('focus_id') if recipe.get('focus_id') in roles else None,'looks':{aid:lid for aid,lid in (recipe.get('looks') or {}).items() if aid in roles and any(l['id']==lid for l in assets[aid].get('looks',[]))} if isinstance(recipe.get('looks'),dict) else {}}
            prior_ids={beat['id'] for beat in book['events'] if beat['scene_id']==unit['scene_id'] and beat['end']<=unit['beats'][0]['start'] and beat['kind']=='action'}
            safe['continuity_ids']=list(dict.fromkeys(x for x in recipe.get('continuity_ids',[]) if isinstance(x,str) and x in prior_ids))[:3] if isinstance(recipe.get('continuity_ids'),list) else []
            recipes.setdefault(recipe['unit_id'],safe)
        missing=[unit['id'] for unit in batch if unit['id'] not in recipes]
        if missing:task.setdefault('storyboard_quality_notes',[]).append({'stage':'direction','units':missing,'reason':'摄影选择不完整，沿用原文景别与固定机位，不改剧情'})
        b.progress(api,task,'analysis',start+len(batch),len(groups))
    return recipes


def compile_shot(api,p,shot):
    """Compile the same source contract for both the UI and the model-facing video prompt."""
    import storyboard as b
    contract=shot['source_contract'];beats=contract['beats'];mode=api.video_mode(shot,p);reference=mode in ('reference','video_reference')
    slots=b.reference_slots(api,p,shot) if reference else [];mapping={p_asset['name']:slot['label'] for slot in slots for p_asset in p['assets'] if p_asset['id']==slot['asset_id']}
    for word,aid in prop_aliases(p['assets']).items():
        slot=next((slot for slot in slots if slot['asset_id']==aid),None)
        if slot:mapping.setdefault(word,slot['label'])
    pattern=re.compile('|'.join(re.escape(name) for name in sorted(mapping,key=len,reverse=True))) if mapping else None
    def label(text):
        text=text.replace('@','')
        return pattern.sub(lambda match:mapping[match[0]],text) if pattern else text
    camera=contract['camera'];source_frame=next((frame for beat in beats if beat['kind'] in ('camera','pause','transition') and beat['text'].startswith('【') for frame in FRAMES if frame in beat['text']),None)
    framing=source_frame or camera.get('framing','中景');movement='固定机位' if any('固定' in beat['text'] for beat in beats if beat['kind']=='camera') else camera.get('movement','固定机位')
    # Facts remain in their source language. A language preference cannot license rewriting their meaning.
    chinese=any(re.search(r'[\u3400-\u9fff]',beat['text']) for beat in beats+contract.get('prior_facts',[])) or any(re.search(r'[\u3400-\u9fff]',text) for text in contract.get('scene',{}).get('heading',[]));shot['prompt_language']='zh' if chinese else 'en'
    english_frames=dict(zip(FRAMES,('Wide shot','Medium shot','Close shot','Close-up','Medium two-shot','Over-the-shoulder shot')))
    english_moves=dict(zip(MOVES,('locked camera','slow push in','slow pull back','follow the subject')))
    main=['[Shot 1] '+(framing+'，'+movement+'。' if chinese else english_frames[framing]+', '+english_moves[movement]+'.')]
    dialogue_index=0;sounds=[];timeline=[];clock=0
    for beat in beats:
        timeline.append({'beat_id':beat['id'],'start':round(clock,2),'end':round(clock+beat['seconds'],2),'kind':beat['kind']});clock+=beat['seconds']
        if beat['kind']=='dialogue':main.append('{{dialogue:'+str(dialogue_index)+'}}');dialogue_index+=1
        elif beat['kind']=='sound':sounds.append(label(beat['text']));main.append(label(beat['text']).strip('【】'))
        elif beat['kind']=='camera' and beat['text'].strip('【】') in (framing,'固定'+framing):continue
        else:main.append(label(beat['text']).replace('【','').replace('】',''))
    shot['duration']=math.ceil(max(shot.get('duration',0),clock+.1,2)*10)/10;shot['source_timeline']=timeline
    text='\n'.join(main)
    if b.is_h3(api.video_model(shot,p)):
        entry={'summary':shot.get('title') or ('人物对话。' if chinese else 'Character dialogue.'),'detailed_description':text,'integrated_multimodal_description':text,'overall_soundscape':'；'.join(sounds) or ('本场自然环境声。' if chinese else 'Natural room tone.'),'non_diegetic_music':'N/A'}
        text=b.assemble_h3(api,p,shot,entry,mode)
        # Character references define identity and opening attire, not immutable masks, gestures or poses.
        if reference:
            parts=b.sections(text,True);retention=[]
            for slot in slots:
                asset=next(a for a in p['assets'] if a['id']==slot['asset_id'])
                retention.append(slot['label']+(': partially_preserved - '+('保留人物身份与造型。' if chinese else 'Preserve identity and outfit.') if asset['type']=='角色' else ': fully_preserved - '+('保留外观。' if chinese else 'Preserve appearance.')))
            text=text.replace(parts['retention_analysis'],'\n'.join(retention) or 'N/A',1)
        text=b.render_dialogue(api,p,shot,text,mode);b.validate(api,p,shot,text,mode);shot.update(video_prompt=text,prompt_format='h3-official-v1',prompt_video_mode=mode)
    else:
        for i,line in enumerate(shot['dialogue']):text=text.replace('{{dialogue:'+str(i)+'}}',line['speaker']+'：'+line['text'])
        shot['video_prompt']=text;shot.pop('prompt_format',None)
    api.sync_duration(shot);api.sync_shot_mentions(p,shot,strict=True)
    return shot


def plan(api,p,task):
    import storyboard as b
    book=ledger(api,p);groups=units(book);task['source_storyboard_digest']=book['script_sha256'];recipes=direct(api,p,task,book,groups);shots=[];prior_by_scene={};looks_by_scene={};assets={a['id']:a for a in p['assets']}
    for unit in groups:
        scene=book['scenes'][unit['scene_id']];prior=prior_by_scene.setdefault(unit['scene_id'],[]);recipe=recipes.get(unit['id'],{'framing':'中景','movement':'固定机位','focus_id':None,'looks':{}})
        prior_actions=[beat for beat in prior if beat['kind']=='action'];chosen_prior=[beat for beat in prior_actions if beat['id'] in recipe.get('continuity_ids',[])] or prior_actions[-2:]
        ids=resource_ids(p,unit,scene,chosen_prior)
        chosen=looks_by_scene.setdefault(unit['scene_id'],{})
        for aid in ids:
            if assets[aid].get('type')=='角色' and aid not in chosen:chosen[aid]=(recipe.get('looks') or {}).get(aid) or assets[aid].get('default_look_id')
        looks={aid:lid for aid,lid in chosen.items() if aid in ids and lid and any(l['id']==lid for l in assets[aid].get('looks',[]))}
        dialogue=[copy.deepcopy(beat['dialogue']) for beat in unit['beats'] if beat['kind']=='dialogue'];facts=[beat['text'] for beat in unit['beats'] if beat['kind']!='dialogue']
        title=recipe.get('title') or next((re.sub(r'[【】。！\n]','',text)[:20] for text in facts if len(text)>3),'剧情对话')
        opening=[beat['text'] for beat in chosen_prior];scene_names=[assets[aid]['name'] for aid in ids if assets[aid].get('type')=='场景'];names=[assets[aid]['name'] for aid in ids if assets[aid].get('type')=='角色']
        initial=[beat['text'] for beat in unit['beats'] if beat['kind']=='action'][:2]
        image='，'.join([recipe.get('framing','中景')]+scene_names)+'。'+('；'.join(opening) if opening else '；'.join(initial))
        contract={'version':'source-events-v1','script_sha256':book['script_sha256'],'scene_id':unit['scene_id'],'scene':copy.deepcopy(scene),'span':[unit['beats'][0]['start'],unit['beats'][-1]['end']],'beats':copy.deepcopy(unit['beats']),'prior_facts':copy.deepcopy(chosen_prior),'camera':recipe}
        shot={'id':api.uid(),'title':title,'description':'\n'.join(facts) or '按原文次序对话。','image_prompt':image,'video_prompt':'','duration':unit['duration'],'dialogue':dialogue,'asset_ids':ids,'character_looks':looks,'versions':[],'video_override':None,'source_contract':contract,'timing':{'method':'source-event-budget-v1','minimum_seconds':unit['duration'],'verified_by_audio':False}}
        if task.get('storyboard_stage')!='planning':compile_shot(api,p,shot)
        else:api.sync_shot_mentions(p,shot,strict=True)
        api.validate_resources(dict(p,shots=[shot]));shots.append(shot);prior.extend(unit['beats']);b.progress(api,task,'h3_prompts',len(shots),len(groups))
    task['storyboard_source_coverage']={'events':len(book['events']),'scenes':len(book['scenes']),'dialogue':sum(beat['kind']=='dialogue' for beat in book['events']),'shots':len(shots),'script_sha256':book['script_sha256']}
    task['storyboard_draft']=copy.deepcopy(shots);b.progress(api,task,'complete',len(shots),len(shots));return {'shots':shots}


def write_existing(api,p,task):
    """Use verified source contracts; legacy handmade shots keep the previous compatibility path."""
    import storyboard as b
    shots=copy.deepcopy(p['shots']);selected=set(task['storyboard_shot_ids']);done=0
    for shot in shots:
        if shot['id'] not in selected:continue
        contract=shot.get('source_contract')
        expected=[beat['dialogue'] for beat in contract.get('beats',[]) if beat.get('kind')=='dialogue'] if isinstance(contract,dict) else None
        facts=[beat['text'] for beat in contract.get('beats',[]) if beat.get('kind')!='dialogue'] if isinstance(contract,dict) else None
        if isinstance(contract,dict) and contract.get('script_sha256')==hashlib.sha256(p['script'].encode()).hexdigest() and shot.get('dialogue')==expected and shot.get('description')==('\n'.join(facts) or '按原文次序对话。'):compile_shot(api,p,shot)
        else:
            local=copy.deepcopy(task);local['storyboard_skill'].pop('source_owned_events',None);local['storyboard_shot_ids']=[shot['id']];local.pop('project_id',None)
            local['storyboard_skill_text']=(api.ROOT/'docs/skills/shotdesk-storyboard/references/legacy-v8.md').read_text()
            result=b.write_existing(api,dict(p,shots=[shot]),local);shot.update(result['shots'][0]);task.setdefault('storyboard_quality_notes',[]).append({'shot_id':shot['id'],'reason':'旧镜头无原文事件契约，沿用兼容编写；重新规划可启用原文驱动'})
        done+=1;b.progress(api,task,'h3_prompts',done,len(selected))
    return {'shots':shots}
