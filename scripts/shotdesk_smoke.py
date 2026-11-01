#!/usr/bin/env python3
"""Create an isolated two-shot project, generate media and verify an exported film.
Generation is opt-in and consumes the configured local services. Never edits an existing project.
"""
import argparse,json,os,subprocess,tempfile,time,urllib.request
from pathlib import Path
from shotdesk_setup import Client

def run(client,args):
    report={'schema_version':1,'success':False,'project_id':None,'jobs':[],'validation':{},'media_quality_reviewed':False,'stage':'preflight'}
    def persist():Path(args.report).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    def wait(job):
        report['jobs'].append({'id':job['id'],'kind':job['kind']});persist();end=time.monotonic()+args.timeout
        while time.monotonic()<end:
            rows=client.call('/api/projects/'+report['project_id']+'/jobs');state=next(x for x in rows if x['id']==job['id'])
            if state['status']=='completed':return state
            if state['status'] in ('failed','cancelled'):raise ValueError('Smoke task '+job['id']+' ended '+state['status']+'; inspect this test project queue')
            time.sleep(1)
        client.call('/api/projects/'+report['project_id']+'/jobs/'+job['id']+'/stop',{})
        raise ValueError('Timed out; requested stop for the smoke task only. Confirm resource release in its queue.')
    try:
        if not args.allow_generate:raise ValueError('Use --allow-generate after authorizing local compute; no project was created')
        catalog=client.call('/api/model-catalog')
        if not any(x['id']==args.image_model for x in catalog.get('images',[])):raise ValueError('Image workflow is not registered')
        if not any(x['id']==args.video_model for x in catalog.get('videos',[])):raise ValueError('Video workflow is not registered')
        p=client.call('/api/projects',{'name':'Shotdesk acceptance '+time.strftime('%Y%m%d-%H%M%S')});pid=p['id'];report['project_id']=pid;persist();base='/api/projects/'+pid
        asset={'id':'smoke-scene','type':'场景','name':'安静的桌面','prompt':'A single red ceramic cup on a clean wooden table, soft daylight, quiet room, no people, no writing.','generation_requirements':'','versions':[]}
        resolution={'preset':'custom','width':args.width,'height':args.height}
        if args.video_model.startswith('Pika-H3-Flex-'):
            native={(832,480):'480p',(1344,768):'768p'}
            if (args.width,args.height) not in native:raise ValueError('Pika H3 requires native 832x480 or 1344x768 dimensions')
            resolution={'preset':native[(args.width,args.height)]}
        settings={'content':'制作一个安静的桌面短片，只有两个镜头，无人物、无对白。红色杯子放在木桌上，先远景再近景，最后结束。','script':'场景一：室内，白天。红色杯子静置在木桌中央，镜头缓慢推进。\n场景二：同一桌面。杯沿近景，柔和日光照亮杯身。无人物、无对白。','assets':[asset],'image_model':args.image_model,'video_model':args.video_model,'video_mode':args.video_mode,'ratio':'16:9','prompt_language':'en','video_resolution':resolution,'reset_epochs':p.get('reset_epochs',{})}
        if args.llm_model:settings['llm_model']=args.llm_model
        client.call(base+'/save',settings)
        if args.with_llm:
            report['stage']='script';persist()
            wait(client.call(base+'/plan',{}));report['validation']['script_generated']=bool(client.call(base).get('script'))
            report['stage']='storyboard';persist()
            wait(client.call(base+'/storyboard',{'stage':'all'}));p=client.call(base)
            if len(p['shots'])<2:raise ValueError('Storyboard produced fewer than two shots; no extra shots fabricated')
            shots=p['shots'][:2];report['validation']['storyboard_generated']=True
            # This new test project deliberately limits the GPU run to two generated shots.
            for shot in shots:shot['asset_ids']=[asset['id']];shot['character_looks']={};shot['video_override']=None
        else:
            shots=[{'id':'smoke-'+str(i+1),'title':title,'description':prompt,'image_prompt':prompt,'video_prompt':prompt,'duration':args.duration,'asset_ids':[asset['id']],'character_looks':{},'versions':[]} for i,(title,prompt) in enumerate([('远景','Wide shot of a red cup on a wooden table, slow camera push in, soft daylight, no people, no dialogue.'),('近景','Close-up of the same red cup on the table, soft daylight, a gentle camera move, no people, no dialogue.')])]
        p=client.call(base);client.call(base+'/save',{'shots':shots,'reset_epochs':p.get('reset_epochs',{})})
        report['stage']='asset_image';persist()
        wait(client.call(base+'/generate',{'target':'asset','id':asset['id'],'kind':'image'}));report['validation']['asset_image_generated']=True
        for shot in shots:
            report['stage']='video:'+shot['id'];persist()
            if args.video_mode=='first_frame':wait(client.call(base+'/generate',{'target':'shot','id':shot['id'],'kind':'image'}))
            preview=client.call(base+'/preview-prompt',{'shot_id':shot['id'],'kind':'video'})
            if args.video_mode=='reference' and not preview.get('image_inputs'):raise ValueError('Reference binding produced no images')
            wait(client.call(base+'/generate',{'target':'shot','id':shot['id'],'kind':'video'}))
        report['stage']='compose';persist()
        film=wait(client.call(base+'/compose',{}));report['validation']['film_exported']=True;report['film_url']=film['url']
        # Download through authenticated HTTP; never use server filesystem paths.
        with tempfile.TemporaryDirectory(prefix='shotdesk-smoke-') as temp:
            target=Path(temp)/'film.mp4';headers={'Authorization':'Bearer '+client.token} if client.token else {}
            with client.opener.open(urllib.request.Request(client.url+film['url'],headers=headers),timeout=60) as response:target.write_bytes(response.read())
            result=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,width,height','-of','json',str(target)],capture_output=True,text=True,check=True,timeout=30);probe=json.loads(result.stdout)
            if not any(s.get('codec_type')=='video' for s in probe['streams']) or float(probe['format']['duration'])<=0:raise ValueError('Export has no valid video stream')
            report['validation']['media_probe']=probe
        report['success']=True;report['stage']='completed';persist();return report
    except Exception as exc:
        # Task IDs and invariant failures only; do not print remote response bodies or credentials.
        report['error']=str(exc) if isinstance(exc,ValueError) else type(exc).__name__+'; inspect the test project queue and local tools';persist();return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--url',default='http://127.0.0.1:1258');p.add_argument('--token-file');p.add_argument('--image-model',required=True);p.add_argument('--video-model',required=True);p.add_argument('--video-mode',choices=['text','reference','first_frame'],default='text');p.add_argument('--allow-generate',action='store_true');p.add_argument('--with-llm',action='store_true');p.add_argument('--llm-model');p.add_argument('--width',type=int,default=512);p.add_argument('--height',type=int,default=288);p.add_argument('--duration',type=float,default=2);p.add_argument('--timeout',type=int,default=600);p.add_argument('--report',default='shotdesk-smoke-report.json');a=p.parse_args()
    token=Path(a.token_file).read_text().strip() if a.token_file else os.getenv('SHOTDESK_TOKEN','');result=run(Client(a.url,token),a);print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['success'] else 1
if __name__=='__main__':raise SystemExit(main())
