"""Version-bound review handoff only. No model calls or automatic approval/retry."""
import hashlib,json,time
class ReviewContract:
    def __init__(self,app):self.app=app
    def context(self,p,shot,kind):
        version=next((v for v in reversed(shot.get('versions',[])) if v.get('kind')==kind and v.get('url')==shot.get(kind)),None)
        if not version:return None
        refs=[{'id':a['id'],'name':a.get('name',''),'url':a.get('image')} for a in p['assets'] if a['id'] in shot.get('asset_ids',[])]
        context={'shot_id':shot['id'],'kind':kind,'version_id':version['id'],'output_url':version['url'],'prompt':shot.get(kind+'_prompt',''),'description':shot.get('description',''),'reference_images':refs,'duration':shot.get('duration') if kind=='video' else None,'first_frame':shot.get('image') if kind=='video' else None,'ratio':p.get('ratio')}
        if kind=='video':
            context['video_mode']=version.get('video_mode') or 'first_frame'
            context['reference_audio']=version.get('source_audio')
            context['reference_video']=version.get('source_video')
            if context['video_mode'] not in ('first_frame','audio','music'):context['first_frame']=None
            if context['video_mode'] in ('reference','video_reference'):
                context['reference_images']=[{'url':url} for url in version.get('source_images',[])]
        context['context_id']=hashlib.sha256(json.dumps(context,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        return context
    def records(self,pid):
        directory=self.app.project(pid).parent/'reviews'
        return sorted([json.loads(f.read_text()) for f in directory.glob('*.json')],key=lambda r:r['created'],reverse=True)
    def inputs(self,pid):
        with self.app.LOCK:
            p=self.app.load(pid);records=self.records(pid);items=[]
            for shot in p['shots']:
                for kind in ('image','video'):
                    context=self.context(p,shot,kind)
                    if context:
                        previous=next((r for r in records if r['shot_id']==shot['id'] and r['kind']==kind),None)
                        context['review_status']=previous['decision'] if previous and previous['context_id']==context['context_id'] else 'pending'
                        context['latest_review']=previous;items.append(context)
            return {'project_id':pid,'items':items,'automatic_review_enabled':False,'automatic_retry_enabled':False}
    def record(self,pid,body):
        with self.app.LOCK:
            p=self.app.load(pid);shot=next((s for s in p['shots'] if s['id']==body.get('shot_id')),None)
            if not shot:raise ValueError('镜头不存在')
            if body.get('kind') not in ('image','video'):raise ValueError('kind 须为 image 或 video')
            context=self.context(p,shot,body['kind'])
            if not context:raise ValueError('当前结果没有可检查的版本记录')
            if body.get('version_id')!=context['version_id'] or body.get('context_id')!=context['context_id']:raise ValueError('待检查的版本或输入已变更，请重新读取 review-inputs')
            decision=body.get('decision')
            if decision not in ('pass','retry','manual_review'):raise ValueError('decision 须为 pass / retry / manual_review')
            checks=body.get('checks',[])
            if not isinstance(checks,list) or not checks or any(not isinstance(c,dict) or c.get('status') not in ('pass','fail','unknown') or not c.get('name') for c in checks):raise ValueError('checks 至少包含一项 name、status（pass/fail/unknown）和可选 reason')
            if decision=='pass' and any(c['status']!='pass' for c in checks):raise ValueError('存在失败或未知检查项，不能通过，请选择 retry 或 manual_review')
            checker=body.get('checker')
            if not isinstance(checker,dict) or checker.get('type') not in ('manual','model') or (checker['type']=='model' and not checker.get('model')):raise ValueError('checker 须标记 manual 或 model；模型检查须提供 model 名称')
            result={'id':self.app.uid(),'created':time.time(),'shot_id':shot['id'],'kind':body['kind'],'version_id':context['version_id'],'context_id':context['context_id'],'decision':decision,'checker':checker,'checks':checks,'notes':str(body.get('notes',''))}
            directory=self.app.project(pid).parent/'reviews';directory.mkdir(exist_ok=True);self.app.save(directory/(result['id']+'.json'),result)
            return result
