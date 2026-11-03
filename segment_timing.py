"""Anchored screenplay duration budgets, independent of single-clip limits."""
import copy,math,re

def validate(rows):
    if not isinstance(rows,list) or len(rows)>20:raise ValueError('段落时长要求最多20条')
    seen=set()
    for r in rows:
        if not isinstance(r,dict) or set(r)-{'id','quote','start','end','before','after','seconds','mode','script_fingerprint'}:raise ValueError('段落时长要求字段不正确')
        if not isinstance(r.get('id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',r['id']) or r['id'] in seen:raise ValueError('段落要求ID须唯一')
        seen.add(r['id'])
        if not isinstance(r.get('quote'),str) or not r['quote'].strip() or len(r['quote'])>6000:raise ValueError('请选择1–6000字的剧本文字')
        for k in ('start','end'):
            if isinstance(r.get(k),bool) or not isinstance(r.get(k),int) or r[k]<0:raise ValueError('段落定位须为有效文字位置')
        if r['end']<=r['start'] or r['end']-r['start']!=len(r['quote']):raise ValueError('段落起止位置与原文不符')
        for k in ('before','after'):
            if not isinstance(r.get(k,''),str) or len(r.get(k,''))>100:raise ValueError('段落定位上下文过长')
        if 'script_fingerprint' in r and (not isinstance(r['script_fingerprint'],str) or len(r['script_fingerprint'])>40):raise ValueError('剧本定位指纹格式不正确')
        n=r.get('seconds')
        if isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) or not 1<=n<=600:raise ValueError('段落时长须为1–600秒')
        if r.get('mode') not in ('minimum','approximate'):raise ValueError('请选择至少或大约')
    return copy.deepcopy(rows)

def script_fingerprint(script):
    value=2166136261
    for char in script:value=((value^ord(char))*16777619)&0xffffffff
    return str(len(script))+'-'+format(value,'08x')

def locate(script,row):
    q=row['quote'];candidates=[];pos=0
    if row.get('script_fingerprint')==script_fingerprint(script) and script[row['start']:row['end']]==q:return row['start'],row['end']
    while True:
        i=script.find(q,pos)
        if i<0:break
        candidates.append(i);pos=i+max(1,len(q))
    if len(candidates)==1:return candidates[0],candidates[0]+len(q)
    matches=[]
    for i in candidates:
        before=row.get('before','');after=row.get('after','')
        if (before or after) and (not before or script[:i].endswith(before)) and (not after or script[i+len(q):].startswith(after)):matches.append(i)
    if len(matches)==1:return matches[0],matches[0]+len(q)
    return None

def resolved(p,strict=False):
    out=[];script=p.get('script','')
    for row in validate(p.get('segment_timings',[])):
        span=locate(script,row);item=dict(row,status='located' if span else 'stale')
        if span:item.update(start=span[0],end=span[1])
        out.append(item)
    positioned=sorted((r for r in out if r['status']=='located'),key=lambda r:r['start'])
    for a,b in zip(positioned,positioned[1:]):
        if b['start']<a['end']:a['status']=b['status']='overlap'
    if strict and any(r['status']!='located' for r in out):raise ValueError('段落时长要求无法定位或存在重叠，请到剧本区域重新选择或移除失效条目')
    return out

def partition(p,chunker):
    rows=resolved(p,True)
    if not rows:return chunker(p['script'])
    script=p['script'];out=[];cursor=0
    def add(start,end,row=None):
        text=script[start:end]
        if not text.strip():return
        parts=chunker(text)
        headings=list(re.finditer(r'(?m)^场景\s*\d+\s*$',script[:start]))
        if headings:
            context=script[headings[-1].start():start].strip().splitlines()
            for part in parts:
                if not re.match(r'^场景\s*\d+',part['heading']):part.update(heading=context[0],scene_meta=' '.join(context[:8])[:160])
        if row:
            weight=sum(len(x['text']) for x in parts) or 1
            for part in parts:part['timing_constraint']={**row,'part_seconds':row['seconds']*len(part['text'])/weight}
        out.extend(parts)
    for row in sorted(rows,key=lambda r:r['start']):add(cursor,row['start']);add(row['start'],row['end'],row);cursor=row['end']
    add(cursor,len(script));return out

def limits(row):
    n=float(row['seconds']);return (n,float('inf')) if row['mode']=='minimum' else (max(1,n-max(2,n*.1)),n+max(2,n*.1))

def stretch(rows,target,rules):
    remaining=max(0,target-sum(float(r['duration']) for r in rows))
    for row in rows:
        if remaining<.001:break
        old=float(row['duration']);extra=min(remaining,max(0,float(rules['max'])-old))
        if rules.get('integer'):extra=min(math.ceil(remaining),math.floor(float(rules['max'])-old))
        if extra<=0:continue
        new=round(old+extra,3)
        # All intervals grow; speech minima and minimum clip lengths stay valid.
        for clip in row['clips']:
            clip['start']=round(float(clip['start'])*new/old,3);clip['end']=round(float(clip['end'])*new/old,3)
        row['clips'][0]['start']=0;row['clips'][-1]['end']=new;row['duration']=new;remaining=max(0,target-sum(float(r['duration']) for r in rows))
    return rows

def shrink_silent(rows,target,rules):
    remaining=max(0,sum(float(r['duration']) for r in rows)-target)
    for row in rows:
        if remaining<.001:break
        capacity=min(float(row['duration'])-float(rules['min']),sum(max(0,float(c['end'])-float(c['start'])-1) for c in row['clips'] if not c.get('line_ids')))
        take=min(remaining,capacity)
        if rules.get('integer'):take=min(math.ceil(remaining),math.floor(capacity))
        if take<=0:continue
        left=take;cursor=0
        for clip in row['clips']:
            length=float(clip['end'])-float(clip['start']);cut=min(left,max(0,length-1)) if not clip.get('line_ids') else 0
            left-=cut;clip['start']=round(cursor,3);cursor+=length-cut;clip['end']=round(cursor,3)
        row['duration']=round(cursor,3);remaining=max(0,sum(float(r['duration']) for r in rows)-target)
    return rows

def expand(p,rows,rules,ask):
    rows=copy.deepcopy(rows);reports=[]
    for budget in resolved(p,True):
        key=budget['id'];selected=[r for r in rows if r.get('_timing_constraint_id')==key]
        if not selected:raise ValueError('指定时长段落未生成有效镜头，原分镜保留：'+budget['quote'][:50])
        low,high=limits(budget);desired=float(budget['seconds']);total=sum(float(r['duration']) for r in selected)
        # Request real new shot coverage before filling residual time, never duplicate a clip.
        attempts=0
        while (total<low-.01 and (len(selected)*float(rules['max'])<desired-.01 or attempts==0)) and attempts<12:
            needed=max(1,desired-total);batch=min(needed,60);count=min(6,max(1,math.ceil(batch/float(rules['max']))))
            new=ask(budget,selected,batch,count)
            if not new:break
            for row in new:row['_timing_constraint_id']=key
            # Keep the original end state/dialogue as the closing beat.
            insert=next(i for i,r in enumerate(rows) if r is selected[-1]);rows[insert:insert]=new;selected=[r for r in rows if r.get('_timing_constraint_id')==key]
            total=sum(float(r['duration']) for r in selected);attempts+=1
            if total>=low-.01:break
            if len(selected)*float(rules['max'])>=desired-.01:break
        stretch(selected,desired,rules)
        if budget['mode']=='approximate':shrink_silent(selected,desired,rules)
        total=sum(float(r['duration']) for r in selected)
        met=low-.01<=total<=high+.01
        reports.append({'id':key,'seconds':budget['seconds'],'mode':budget['mode'],'planned_seconds':round(total,3),'shots':len(selected),'met':met})
        if not met:raise ValueError('段落时长未达到要求（已规划'+str(round(total,2))+'秒，要求'+str(budget['seconds'])+'秒），请调整目标或段落范围；原分镜未覆盖')
    return rows,reports

def report(p):
    out=[]
    for row in resolved(p):
        total=sum(float(s.get('duration',0)) for s in p.get('shots',[]) if s.get('timing_constraint_id')==row['id'] and s.get('timing_constraint_quote')==row['quote']);low,high=limits(row)
        out.append({**row,'planned_seconds':round(total,3),'met':row['status']=='located' and low-.01<=total<=high+.01})
    return out
