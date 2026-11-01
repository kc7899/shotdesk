#!/usr/bin/env python3
"""Read-only diagnosis by default; configure only through Shotdesk's guarded HTTP API."""
import argparse,json,os,platform,shutil,subprocess,sys,urllib.request,urllib.error,urllib.parse
from pathlib import Path

class Client:
    def __init__(self,url,token='',timeout=10):
        parsed=urllib.parse.urlsplit(url)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:raise ValueError('Use an HTTP(S) URL without embedded credentials')
        self.url=url.rstrip('/');self.token=token;self.timeout=timeout
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def call(self,path,body=None):
        headers={'Content-Type':'application/json'}
        if self.token:headers['Authorization']='Bearer '+self.token
        req=urllib.request.Request(self.url+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
        try:
            with self.opener.open(req,timeout=self.timeout) as response:
                if 'json' not in response.headers.get('Content-Type',''):raise ValueError('Expected JSON; check the Shotdesk URL and authentication')
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in (401,403):raise ValueError('Authentication required or refused; use SHOTDESK_TOKEN or --token-file') from None
            # Error bodies can contain secrets or private model output; never echo them.
            raise ValueError('HTTP '+str(exc.code)+' at '+path.split('?',1)[0]+'; request rejected, check its input fields and the service response') from None
        except (urllib.error.URLError,TimeoutError,ConnectionError,OSError):raise ValueError('Service unreachable or timed out; check address, network and startup state') from None

def executable(command):
    if not shutil.which(command[0]):return {'available':False}
    try:
        result=subprocess.run(command,capture_output=True,text=True,timeout=5)
        return {'available':result.returncode==0,'version':result.stdout.splitlines()[0][:180] if result.stdout else ''}
    except (OSError,subprocess.TimeoutExpired):return {'available':False}

def doctor(client,probe_local=False):
    report={'schema_version':1,'python':platform.python_version(),'tools':{name:executable(command) for name,command in {'docker':['docker','--version'],'compose':['docker','compose','version'],'ffmpeg':['ffmpeg','-version'],'ffprobe':['ffprobe','-version']}.items()},'studio':{'status':'unreachable'},'services':{},'workflows':[], 'generated_media_verified':False,'diagnostics_complete':False}
    try:
        settings=client.call('/api/settings');report['studio']={'status':'connected','adapter':settings.get('workflow_adapter'),'password_configured':settings.get('password_configured',False)}
        for kind,key in [('llm','llm_url'),('comfy','comfy_url'),('speech','speech_url')]:
            if not settings.get(key):report['services'][kind]={'status':'not_configured','optional':kind=='speech'};continue
            result=client.call('/api/settings/test',{'service':kind,'url':settings[key]})
            state={'status':'connected' if result.get('ok') else 'unreachable','optional':kind=='speech','generation_verified':False}
            if kind=='llm':state.update(models=result.get('models',[]),selected=settings.get('llm_model'),selected_listed=settings.get('llm_model') in result.get('models',[]))
            report['services'][kind]=state
        catalog=client.call('/api/model-catalog');report['workflows']=[{'id':x['id'],'kind':kind} for key,kind in [('images','image'),('videos','video')] for x in catalog.get(key,[])]
        jobs=client.call('/api/jobs');report['active_tasks']=sum(j.get('status') in ('queued','running','cancelling') for j in jobs);report['diagnostics_complete']=True
    except ValueError as exc:report['studio']['error']=str(exc)
    if probe_local:
        # Explicit discovery of loopback ports only, not a network scan or service launch.
        report['local_candidates']=[]
        for kind,url,path in [('llm','http://127.0.0.1:8000','/v1/models'),('llm','http://127.0.0.1:8010','/v1/models'),('comfy','http://127.0.0.1:8188','/object_info'),('speech','http://127.0.0.1:1249','/api/jobs')]:
            try:
                value=Client(url,timeout=1).call(path)
                valid=isinstance(value,dict) and ('data' in value if kind=='llm' else 'LoadImage' in value if kind=='comfy' else True)
                if valid:report['local_candidates'].append({'service':kind,'url':url+('/v1' if kind=='llm' else ''),'authentication_tested':False})
            except ValueError:pass
    report['ready_for_generation_test']=report['studio']['status']=='connected' and all(report['services'].get(k,{}).get('status')=='connected' for k in ('llm','comfy')) and any(x['kind']=='video' for x in report['workflows'])
    return report

def configure(client,path,allow_offline=False):
    config=json.loads(Path(path).read_text())
    allowed={'llm_url','llm_model','llm_api_key','comfy_url','speech_url','vision_model','access_password','clear_api_key'}
    if not isinstance(config,dict) or set(config)-allowed:raise ValueError('Unsupported settings fields')
    if config.get('llm_url') and not config.get('llm_model'):raise ValueError('Select an actual model ID; use doctor to discover models first')
    for kind,key in [('llm','llm_url'),('comfy','comfy_url'),('speech','speech_url')]:
        if config.get(key):
            body={'service':kind,'url':config[key]}
            if kind=='llm':body.update(api_key=config.get('llm_api_key',''),clear_api_key=config.get('clear_api_key',False))
            result=client.call('/api/settings/test',body)
            if not result.get('ok') and not allow_offline:raise ValueError(kind+' connection test failed; no configuration was saved')
            if kind=='llm' and result.get('models') and config['llm_model'] not in result['models']:raise ValueError('Selected model is not listed by this service; no configuration was saved')
    client.call('/api/settings',config)
    return {'saved':True,'secrets_printed':False,'next':'Run doctor, then the two-shot smoke test. Connected is not generation-verified.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--url',default='http://127.0.0.1:1258');parser.add_argument('--token-file');subs=parser.add_subparsers(dest='command',required=True)
    d=subs.add_parser('doctor');d.add_argument('--probe-local',action='store_true')
    c=subs.add_parser('configure');c.add_argument('--config',required=True);c.add_argument('--allow-offline',action='store_true')
    args=parser.parse_args()
    try:
        token=Path(args.token_file).read_text().strip() if args.token_file else os.getenv('SHOTDESK_TOKEN','');client=Client(args.url,token)
        result=doctor(client,args.probe_local) if args.command=='doctor' else configure(client,args.config,args.allow_offline)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if args.command=='configure' or result['diagnostics_complete'] else 2
    except ValueError as exc:print(json.dumps({'error':str(exc)}));return 2
    except OSError:print(json.dumps({'error':'Cannot read the private configuration or token file; no secrets are included in this report.'}));return 2
if __name__=='__main__':raise SystemExit(main())
