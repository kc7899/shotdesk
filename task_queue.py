"""Persistent unified jobs with target-scoped cancellation; no global model interrupts."""
import copy, http.client, importlib.util, json, os, socket, statistics, subprocess, threading, time, urllib.parse
from pathlib import Path
import cloud_video
import shot_preparation
import llm_skills

ACTIVE={'queued','running','cancelling'}
TERMINAL={'completed','failed','cancelled'}
class Cancelled(Exception): pass

def align_h3_encoder_inputs(graph):
    """Keep the whole frame; align intermediate H3 images to codec spatial blocks."""
    for ident,node in list(graph.items()):
        if node.get('class_type')!='BlehTAEVideoEncode' or node.get('inputs',{}).get('latent_type')!='minimaxh3video':continue
        source=node['inputs'].get('image')
        if not isinstance(source,list) or len(source)!=2:continue
        upstream=graph.get(str(source[0]),{})
        fields=upstream.get('inputs',{})
        if upstream.get('class_type')=='ImageResizeKJ' and fields.get('divisible_by')==32 and fields.get('crop')=='disabled':continue
        key='shotdesk_h3_align_'+str(ident)
        while key in graph:key+='_'
        graph[key]={'class_type':'ImageResizeKJ','inputs':{'image':source,'width':0,'height':0,'upscale_method':'bilinear','keep_proportion':False,'divisible_by':32,'crop':'disabled'},'_meta':{'title':'H3 codec dimension alignment (no crop)'}}
        node['inputs']['image']=[key,0]
    return graph

def comfy_error(history):
    messages=history.get('status',{}).get('messages',[])
    for entry in reversed(messages):
        if not isinstance(entry,(list,tuple)) or len(entry)<2 or entry[0]!='execution_error' or not isinstance(entry[1],dict):continue
        error=entry[1];node=str(error.get('node_id','?'));kind=str(error.get('node_type','?'))
        message=str(error.get('exception_message') or error.get('exception_type') or 'Unknown execution error').strip()
        return 'ComfyUI 执行失败：'+kind+'（节点 '+node+'）：'+message[:1500]
    return 'ComfyUI 执行失败：服务未返回具体异常，请查看ComfyUI日志'

class TaskQueue:
    def __init__(self, app):
        self.app=app;self.events={};self.connections={};self.processes={};self.media_lock=threading.Lock();self.text_lock=threading.Lock();self.export_lock=threading.Lock();self.transport=None;self.monitors=set();self.media_pending=[];self.media_dispatching=False;self.bulk_stopping=set()
        self.list_lock=threading.RLock();self.list_cache={}
        self.comfy=os.getenv('COMFY_URL','http://127.0.0.1:8188')
    def check(self,j):
        if self.events.setdefault(j['id'],threading.Event()).is_set() or j.get('cancel_requested'): raise Cancelled('用户已停止任务')
    def persist(self,pid,j): self.app.job_save(pid,j)
    def start(self,pid,j):
        with self.app.LOCK:
            self.check(j);j.update(status='running',started_at=j.get('started_at') or time.time(),phase='running');self.persist(pid,j)
    def done(self,pid,j,**fields):
        with self.app.LOCK:
            self.check(j);j.update(status='completed',finished_at=time.time(),phase='completed',**fields);self.persist(pid,j)
    def enqueue(self,pid,j):
        j.setdefault('project_id',pid);j.setdefault('project_name',self.app.load(pid)['name']);j.setdefault('created',time.time());j.setdefault('status','queued')
        self.events.setdefault(j['id'],threading.Event());self.persist(pid,j)
        if j['kind'] in ('image','video','audio'):
            with self.app.LOCK:
                self.media_pending.append((pid,j))
                if not self.media_dispatching:
                    self.media_dispatching=True;threading.Thread(target=self.drain_media,daemon=True).start()
        else:threading.Thread(target=self.worker,args=(pid,j),daemon=True).start()
        return self.public(pid,j)
    def drain_media(self):
        while True:
            with self.app.LOCK:
                if not self.media_pending:self.media_dispatching=False;return
                self.media_pending.sort(key=lambda item:item[1]['created']);pid,j=self.media_pending.pop(0)
            try:self.worker(pid,j)
            except Exception as exc:
                print('Media worker failed:',j['id'],str(exc),flush=True)
    def worker(self,pid,j):
        try:
            lock=threading.Lock() if j['kind']=='asset_sync' else self.media_lock if j['kind'] in ('image','video','audio') else self.text_lock if j['kind']=='text' else self.export_lock
            while not lock.acquire(timeout=.2): self.check(j)
            try:
                self.check(j)
                if j['kind'] in ('image','video'): self.run_media(pid,j)
                elif j['kind']=='asset_sync':
                    self.start(pid,j);result=self.app.ark_assets.run(self,pid,j);self.done(pid,j,result=result)
                elif j['kind']=='audio':self.app.run_speech(pid,j)
                elif j['kind']=='text':
                    self.start(pid,j)
                    if j.get('operation')=='prepare_shots':
                        result=shot_preparation.run(self.app,pid,j);self.done(pid,j,result=result)
                    elif j.get('operation') in ('optimize_look','optimize_prop'):
                        result=self.app.optimize_look(j);self.done(pid,j,result=result)
                    elif j.get('operation')=='extract_assets':
                        result=self.app.extract_assets(j);self.done(pid,j,result=result)
                    else:
                        result=self.app.plan_storyboard(j['snapshot'],j) if j.get('operation') in ('generate_storyboard','generate_storyboard_plan','generate_video_prompts') else self.app.plan(j['snapshot'],j)
                        with self.app.LOCK:
                            self.check(j);current=self.app.load(pid)
                            if j.get('operation')=='generate_script':
                                result={'script':result['script']}
                                if any(current.get(key,'')!=j['snapshot'].get(key,'') for key in ('content','script')):
                                    j['result']=result
                                    raise ValueError('故事或剧本已被修改，本次生成未覆盖；生成正文保留在任务 result.script 中')
                            elif j.get('operation') in ('generate_storyboard','generate_storyboard_plan','generate_video_prompts'):
                                result={'shots':result['shots']}
                                if any(current.get(key)!=j['snapshot'].get(key) for key in ('script','assets','shots','video_mode','video_model','ratio','prompt_language','storyboard_requirements','reset_epochs')) or self.storyboard_media_active(pid):
                                    j['result']=result
                                    raise ValueError('剧本、资产、分镜或生成设置已变更，或镜头任务正在运行；本次未覆盖，分镜保留在任务 result.shots 中')
                            elif current['shots'] or current['assets'] or current['content']!=j['snapshot']['content']: raise ValueError('项目内容或分镜已变更，本次结果未覆盖现有制作内容')
                            self.app.update(pid,lambda p:p.update(result));self.done(pid,j)
                else:
                    self.start(pid,j);result=self.app.compose(pid,j);self.done(pid,j,**result)
            finally:
                if j['kind']=='audio' and j.get('speech_remote_id') and j.get('status')!='completed':self.app.wait_speech_release(j)
                lock.release()
        except Cancelled:
            self.mark_cancelled(pid,j)
        except Exception as exc:
            cancelled=self.events.setdefault(j['id'],threading.Event()).is_set()
            if cancelled:self.mark_cancelled(pid,j)
            else:
                j.update(status='failed',finished_at=time.time(),phase='failed',error=str(exc)[:2000]);self.persist(pid,j)
        finally:
            self.connections.pop(j['id'],None);self.processes.pop(j['id'],None)
            if j['kind']=='compose' and j['status']!='completed':
                for f in (self.app.project(pid).parent/'media').glob('*'+j['id']+'*'): f.unlink(missing_ok=True)
    def mark_cancelled(self,pid,j):
        try:
            if j.get('transport')=='cloud':cloud_video.stop(self,j)
            if j.get('kind')=='audio' and not self.app.speech_terminal(j):raise ValueError('已停止接收结果，等待IndexTTS当前推理释放资源')
            if j.get('remote_id') and not j.get('prompt_id'):
                state=self.app.request(self.app.GATEWAY+'/v1/video/generations/'+j['remote_id'],timeout=10)
                if state.get('prompt_id'):j['prompt_id']=state['prompt_id']
                elif state['status'] not in ('completed','failed'):raise ValueError('旧网关任务尚未提供可停止的任务 ID')
            if j.get('prompt_id'):self.stop_comfy(j['prompt_id'])
            j.update(status='cancelled',cancel_requested=True,finished_at=time.time(),phase='cancelled');j.pop('cancel_error',None)
        except Exception as exc:
            j.update(status='cancelling',cancel_requested=True,phase='cancelling',cancel_error=str(exc));j.pop('finished_at',None)
            self.monitor_cancel(pid,j['id'])
        self.persist(pid,j)
    def engine(self):
        if self.transport is None:
            path=Path(os.getenv('TRANSPORT_MODULE',str(self.app.ROOT/'workflow_transport.py')))
            spec=importlib.util.spec_from_file_location('shotdesk_media_transport',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            module.ROOT=Path(os.getenv('WORKFLOW_ROOT',str(self.app.ROOT/'workflows')));module.COMFY=self.comfy;self.transport=module
        return self.transport
    def run_media(self,pid,j):
        self.check(j)
        if j.get('transport')=='cloud':return cloud_video.run(self,pid,j)
        if j.get('remote_id') and j.get('transport')!='comfy': return self.run_legacy(pid,j)
        if not j.get('prompt_id'):
            j.update(phase='preparing');self.persist(pid,j)
            engine=self.engine();graph,output,hashes=engine.build_graph(j['request'],j['id'],j['kind']);align_h3_encoder_inputs(graph);self.check(j)
            self.app.save(self.app.job_path(pid,j['id']).with_suffix('.workflow.json'),graph)
            # Cancellation and submission are ordered under one lock; an accepted ID is always persisted.
            with self.app.LOCK:
                self.check(j);j['phase']='submitting';self.persist(pid,j);result=self.app.request(self.comfy+'/prompt',{'prompt':graph,'client_id':'shotdesk','extra_data':{'shotdesk_job_id':j['id']}},timeout=60)
                if not result.get('prompt_id') or result.get('node_errors'):raise ValueError('ComfyUI 拒绝工作流：'+json.dumps(result,ensure_ascii=False))
                j.update(prompt_id=result['prompt_id'],output_node=output,reference_sha256=hashes,transport='comfy',submitted_at=time.time(),phase='upstream_queue');self.persist(pid,j)
        deadline=time.monotonic()+7200
        while time.monotonic()<deadline:
            if self.events[j['id']].is_set():
                self.stop_comfy(j['prompt_id']);raise Cancelled()
            history=self.app.request(self.comfy+'/history/'+j['prompt_id'],timeout=15).get(j['prompt_id'])
            if history:
                if history.get('status',{}).get('status_str')=='error':raise ValueError(comfy_error(history))
                values=history.get('outputs',{}).get(j['output_node'],{})
                artifacts=[a for field in ('images','gifs','videos','audio') for a in values.get(field,[])]
                if artifacts:
                    if not j.get('started_at'):
                        # Fast tasks can finish between polls; Comfy records the true execution start.
                        messages=history.get('status',{}).get('messages',[])
                        start=next((v.get('timestamp') for name,v in messages if name=='execution_start'),None)
                        j['started_at']=start/1000 if start else j['submitted_at']
                    self.check(j);artifact=artifacts[0];query=urllib.parse.urlencode({k:artifact.get(k,'') for k in ('filename','subfolder','type')});suffix='.png' if j['kind']=='image' else '.mp4';dest=self.app.project(pid).parent/'media'/(j['id']+suffix)
                    with self.app.OP.open(self.comfy+'/view?'+query,timeout=180) as response:dest.write_bytes(response.read())
                    self.check(j)
                    with self.app.LOCK:
                        self.check(j);self.app.finish_job(pid,j,f'/media/{pid}/media/{dest.name}');self.done(pid,j,url=f'/media/{pid}/media/{dest.name}')
                    return
                if history.get('status',{}).get('completed'):raise ValueError('ComfyUI 已结束但没有预期输出')
            queue=self.app.request(self.comfy+'/queue',timeout=15)
            if any(item[1]==j['prompt_id'] for item in queue.get('queue_running',[])) and not j.get('started_at'): self.start(pid,j)
            if self.events[j['id']].wait(1):continue
        raise TimeoutError('生成超时；已保留任务 ID，不会自动重复提交')
    def run_legacy(self,pid,j):
        while True:
            self.check(j);state=self.app.request(self.app.GATEWAY+'/v1/video/generations/'+j['remote_id'],timeout=15)
            if state.get('prompt_id'):j['prompt_id']=state['prompt_id']
            if state['status']=='failed':raise ValueError(state.get('error','旧任务失败'))
            if state['status']=='completed':break
            if state['status']=='running' and not j.get('timing_approximate'):
                j['started_at']=state.get('created') or j['created'];j['timing_approximate']=True;self.start(pid,j)
            self.events[j['id']].wait(2)
        suffix='.png' if j['kind']=='image' else '.mp4';dest=self.app.project(pid).parent/'media'/(j['id']+suffix)
        with self.app.OP.open(self.app.GATEWAY+'/media/'+j['remote_id'],timeout=180) as response:dest.write_bytes(response.read())
        with self.app.LOCK:self.check(j);self.app.finish_job(pid,j,f'/media/{pid}/media/{dest.name}');self.done(pid,j,url=f'/media/{pid}/media/{dest.name}')
    def stop_comfy(self,prompt_id):
        if not prompt_id:raise ValueError('缺少可停止的上游任务 ID')
        self.app.request(self.comfy+'/queue',{'delete':[prompt_id]},timeout=15)
        # Deleting a queued/finished task must not send an interrupt at all.
        interrupted=False;deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            state=self.app.request(self.comfy+'/queue',timeout=15)
            running=any(row[1]==prompt_id for row in state.get('queue_running',[]))
            if not running and not any(row[1]==prompt_id for row in state.get('queue_pending',[])):return
            if running and not interrupted:
                self.app.request(self.comfy+'/interrupt',{'prompt_id':prompt_id},timeout=15);interrupted=True
            time.sleep(.3)
        raise TimeoutError('模型仍在退出，请稍后再次停止；未标记为已停止')
    def cancel_all(self):
        # Freeze cancellation intent for the whole snapshot before stopping upstream work.
        # New jobs submitted after this snapshot are deliberately outside this request.
        with self.app.LOCK:
            targets=[];upstream=[]
            rows=[row for row in self.list() if row.get('status') in ACTIVE]
            for row in rows:self.events.setdefault(row['id'],threading.Event()).set()
            for row in rows:
                pid,jid=row['project_id'],row['id']
                j=json.loads(self.app.job_path(pid,jid).read_text())
                if j['status'] not in ACTIVE:continue
                self.events.setdefault(jid,threading.Event()).set();j['cancel_requested']=True
                local_only=j['status']=='queued' and not any(j.get(k) for k in ('prompt_id','remote_id','speech_remote_id','cloud_task_id','cloud_provider')) and jid not in self.connections and jid not in self.processes
                if local_only:j.update(status='cancelled',phase='cancelled',finished_at=time.time());j.pop('cancel_error',None)
                else:
                    j.update(status='cancelling',phase='cancelling')
                    if (pid,jid) not in self.bulk_stopping:self.bulk_stopping.add((pid,jid));upstream.append((0 if j['kind'] in ('text','compose','audio') else 1,pid,jid))
                self.persist(pid,j);targets.append({'project_id':pid,'id':jid,'status':j['status']})
        def stop_snapshot():
            for _,pid,jid in sorted(upstream):
                try:self.cancel(pid,jid)
                except Exception as exc:
                    with self.app.LOCK:
                        try:
                            j=json.loads(self.app.job_path(pid,jid).read_text())
                            if j['status'] in ACTIVE:j.update(status='cancelling',cancel_error=str(exc));self.persist(pid,j)
                        except FileNotFoundError:pass
                finally:
                    with self.app.LOCK:self.bulk_stopping.discard((pid,jid))
        if upstream:threading.Thread(target=stop_snapshot,daemon=True).start()
        return {'scope':'all_projects','requested':len(targets),'cancelled':sum(j['status']=='cancelled' for j in targets),'cancelling':sum(j['status']=='cancelling' for j in targets),'jobs':targets}

    def cancel(self,pid,jid):
        if len(jid)!=32 or any(c not in 'abcdef0123456789' for c in jid):raise ValueError('任务 ID 无效')
        with self.app.LOCK:
            j=json.loads(self.app.job_path(pid,jid).read_text())
            if j['status'] not in ACTIVE:return self.public(pid,j)
            self.events.setdefault(jid,threading.Event()).set();j.update(status='cancelling',cancel_requested=True);self.persist(pid,j)
        try:
            if j.get('transport')=='cloud':cloud_video.stop(self,j)
            if j.get('kind')=='audio' and not self.app.speech_terminal(j):raise ValueError('已停止接收结果，等待IndexTTS当前推理释放资源')
            prompt=j.get('prompt_id')
            if j.get('remote_id') and not prompt:
                upstream=self.app.request(self.app.GATEWAY+'/v1/video/generations/'+j['remote_id'],timeout=10);prompt=upstream.get('prompt_id')
            if j.get('remote_id') and not prompt and upstream.get('status') not in ('completed','failed'):raise ValueError('旧网关任务尚未提供可停止的任务 ID，暂未确认停止')
            if prompt:self.stop_comfy(prompt)
            conn=self.connections.get(jid)
            if conn:
                if conn.sock:
                    try:conn.sock.shutdown(socket.SHUT_RDWR)
                    except OSError:pass
                conn.close()
            proc=self.processes.get(jid)
            if proc and proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
            with self.app.LOCK:
                latest=json.loads(self.app.job_path(pid,jid).read_text())
                if latest['status']=='completed':return self.public(pid,latest)
                latest.update(status='cancelled',cancel_requested=True,finished_at=latest.get('finished_at') or time.time(),phase='cancelled');latest.pop('cancel_error',None);self.persist(pid,latest)
            return self.public(pid,latest)
        except Exception as exc:
            with self.app.LOCK:
                latest=json.loads(self.app.job_path(pid,jid).read_text());latest.update(status='cancelling',cancel_error=str(exc));self.persist(pid,latest)
            self.monitor_cancel(pid,jid)
            return self.public(pid,latest)
    def monitor_cancel(self,pid,jid):
        with self.app.LOCK:
            if jid in self.monitors:return
            self.monitors.add(jid)
        def watch():
            try:
                while True:
                    time.sleep(2)
                    try:
                        j=json.loads(self.app.job_path(pid,jid).read_text())
                        if j['status']!='cancelling':return
                        if j.get('transport')=='cloud':cloud_video.stop(self,j)
                        if j.get('kind')=='audio' and not self.app.speech_terminal(j):continue
                        if not j.get('prompt_id') and j.get('remote_id'):
                            state=self.app.request(self.app.GATEWAY+'/v1/video/generations/'+j['remote_id'],timeout=10)
                            if state.get('prompt_id'):j['prompt_id']=state['prompt_id']
                            elif state['status'] not in ('completed','failed'):continue
                        if j.get('prompt_id'):self.stop_comfy(j['prompt_id'])
                        with self.app.LOCK:
                            current=json.loads(self.app.job_path(pid,jid).read_text())
                            if current['status']!='cancelling':return
                            current.update(status='cancelled',finished_at=time.time(),phase='cancelled');current.pop('cancel_error',None);self.persist(pid,current)
                        return
                    except FileNotFoundError:return
                    except Exception:continue
            finally:
                with self.app.LOCK:self.monitors.discard(jid)
        threading.Thread(target=watch,daemon=True).start()
    def text_request(self,body,j):
        body=llm_skills.apply(self.app,body,j)
        self.check(j);url=urllib.parse.urlsplit(self.app.llm_endpoint(body.get('model',self.app.TEXT_MODEL)));cls=http.client.HTTPSConnection if url.scheme=='https' else http.client.HTTPConnection;conn=cls(url.hostname,url.port,timeout=600)
        body=dict(body,stream=True);self.connections[j['id']]=conn
        try:
            conn.connect();self.check(j);conn.request('POST',url.path or '/',json.dumps(body,ensure_ascii=False).encode(),self.app.text_headers(self.app.llm_endpoint(body.get('model',self.app.TEXT_MODEL))));response=conn.getresponse()
            if response.status>=400:raise ValueError(response.read(2000).decode(errors='replace'))
            text=[];finish_reason=None;tool_calls={}
            while True:
                self.check(j);line=response.readline()
                if not line:break
                if not line.startswith(b'data:'):continue
                chunk=line[5:].strip()
                if chunk==b'[DONE]':break
                item=json.loads(chunk)
                if item.get('error'):
                    error=item['error'];raise ValueError('文字服务返回错误：'+str(error.get('message',error) if isinstance(error,dict) else error))
                choice=(item.get('choices') or [{}])[0];content=choice.get('delta',{}).get('content')
                if choice.get('finish_reason') is not None:finish_reason=choice['finish_reason']
                if content:text.append(content)
                for fragment in choice.get('delta',{}).get('tool_calls',[]):
                    index=fragment.get('index',0);call=tool_calls.setdefault(index,{'id':'','type':'function','function':{'name':'','arguments':''}})
                    if fragment.get('id'):call['id']+=fragment['id']
                    for field in ('name','arguments'):
                        if fragment.get('function',{}).get(field):call['function'][field]+=fragment['function'][field]
            self.check(j)
            if not text and finish_reason is None:raise ValueError('文字服务连接结束但未返回内容或结束标记')
            message={'content':''.join(text)}
            if tool_calls:message['tool_calls']=[tool_calls[k] for k in sorted(tool_calls)]
            return {'choices':[{'message':message,'finish_reason':finish_reason}]}
        finally:conn.close();self.connections.pop(j['id'],None)
    def run_process(self,j,cmd):
        if not j:return subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=600)
        with self.app.LOCK:
            self.check(j);proc=subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE);self.processes[j['id']]=proc
        try:
            try:_,err=proc.communicate(timeout=600)
            except subprocess.TimeoutExpired:proc.kill();proc.communicate();raise TimeoutError('合片处理超时')
            self.check(j)
            if proc.returncode:raise ValueError('合片失败：'+err.decode(errors='replace')[-1500:])
        finally:self.processes.pop(j['id'],None)
    def start_text(self,pid):
        with self.app.LOCK:
            p=self.app.load(pid)
            if not p['content'].strip():raise ValueError('请先填写故事内容')
            self.reject_duplicate(pid,'text','project')
            skill=self.app.script_skill_bundle()
            return self.enqueue(pid,{'id':self.app.uid(),'kind':'text','target':'project','target_id':'project','operation':'generate_script','title':'生成剧本','model':self.app.llm_model(p),'snapshot':p,'script_skill':{k:v for k,v in skill.items() if k!='text'},'script_skill_text':skill['text']})
    def storyboard_media_active(self,pid):
        return any(j.get('status') in ACTIVE and j.get('kind') in ('image','video','audio','compose') for j in self.list(pid))
    def storyboard_checkpoint(self,pid,p,skill):
        candidates=[]
        for row in self.list(pid):
            if row.get('operation') not in ('generate_storyboard','generate_storyboard_plan') or row.get('status')!='failed':continue
            path=self.app.job_path(pid,row['id'])
            try:job=json.loads(path.read_text())
            except (OSError,ValueError):continue
            if job.get('operation') not in ('generate_storyboard','generate_storyboard_plan') or job.get('status')!='failed' or not job.get('storyboard_planning_parts'):continue
            if job.get('storyboard_skill',{}).get('planning_format')!=skill.get('planning_format') or skill.get('planning_format')!='unified-references-v1':continue
            if job.get('storyboard_skill',{}).get('director_format')!=skill.get('director_format'):continue
            if skill.get('director_format') and job.get('storyboard_skill',{}).get('version')!=skill.get('version'):continue
            if bool(job.get('storyboard_skill',{}).get('source_owned_events'))!=bool(skill.get('source_owned_events')):continue
            if skill.get('performance_format') and job.get('storyboard_skill',{}).get('performance_format')!=skill['performance_format']:continue
            if skill.get('prompt_language') and job.get('storyboard_skill',{}).get('prompt_language')!=skill['prompt_language']:continue
            snapshot=job.get('snapshot',{})
            if any(snapshot.get(k)!=p.get(k) for k in ('script','assets','shots','ratio','video_mode','video_model','llm_model','prompt_language','storyboard_requirements','reset_epochs')):continue
            candidates.append(job)
        if not candidates:return {}
        job=max(candidates,key=lambda j:j.get('created',0))
        return {'storyboard_resume_from':job['id'],'storyboard_seed_parts':copy.deepcopy(job['storyboard_planning_parts']),'storyboard_seed_prompts':copy.deepcopy(job.get('storyboard_prompt_parts',[]))}

    def start_storyboard(self,pid,replace_existing=False,stage='all',scope='missing',shot_id=None):
        with self.app.LOCK:
            p=self.app.load(pid)
            if not p.get('script','').strip():raise ValueError('请先生成并审核剧本，再生成分镜')
            if stage not in ('all','planning','prompts'):raise ValueError('stage须为all/planning/prompts')
            if scope not in ('missing','all'):raise ValueError('scope须为missing/all')
            if stage=='prompts' and not p['shots']:raise ValueError('请先生成分镜规划')
            if stage!='prompts' and p['shots'] and not replace_existing:raise ValueError('已有分镜，请明确确认替换后再生成')
            if self.storyboard_media_active(pid):raise ValueError('请先等待或停止当前图片、视频、配音或合片任务，再重新生成分镜')
            self.reject_duplicate(pid,'text','project')
            skill=self.app.storyboard_skill_bundle(p)
            extra=self.storyboard_checkpoint(pid,p,skill) if stage!='prompts' else {}
            if stage=='prompts':
                ids=[s['id'] for s in p['shots'] if (not shot_id or s['id']==shot_id) and (scope=='all' or self.app.storyboard.prompt_is_missing(self.app,s))]
                if not ids:raise ValueError('没有需要编写的镜头；可选择全部重写')
                extra['storyboard_shot_ids']=ids
                extra['storyboard_mode_official']={mode:self.app.storyboard_skill_bundle(dict(p,video_mode=mode,video_model=skill['video_model'])).get('official_text','') for mode in ('reference','first_frame','video_reference')}
                candidates=[j for j in self.list(pid) if j.get('operation')=='generate_video_prompts' and j.get('status')=='failed']
                for candidate in sorted(candidates,key=lambda j:j.get('created',0),reverse=True):
                    stored=json.loads(self.app.job_path(pid,candidate['id']).read_text())
                    if stored.get('snapshot')==p and stored.get('storyboard_shot_ids')==ids and (not skill.get('director_format') or stored.get('storyboard_skill',{}).get('version')==skill.get('version')) and all(stored.get('storyboard_skill',{}).get(k)==skill.get(k) for k in ('video_mode','video_model','format','prompt_language','performance_format','source_owned_events','director_format')):
                        extra['storyboard_seed_prompts']=copy.deepcopy(stored.get('storyboard_prompt_parts',[]));break
            operation={'all':'generate_storyboard','planning':'generate_storyboard_plan','prompts':'generate_video_prompts'}[stage]
            title={'all':'一键完成分镜','planning':'生成分镜规划','prompts':'编写视频提示词'}[stage]
            return self.enqueue(pid,{**extra,'storyboard_stage':stage,'storyboard_skill':{k:v for k,v in skill.items() if k not in ('text','official_text','prompt_generator_text')},'storyboard_skill_text':skill['text'],'storyboard_official_text':skill.get('official_text',''),'huobao_prompt_generator_text':skill.get('prompt_generator_text',''),'id':self.app.uid(),'kind':'text','target':'project','target_id':'project','operation':operation,'title':title,'model':self.app.llm_model(p),'snapshot':p})
    def start_compose(self,pid):
        with self.app.LOCK:
            p=self.app.load(pid)
            if not p['shots'] or any(not s.get('video') for s in p['shots']):raise ValueError('请先完成全部镜头视频')
            self.reject_duplicate(pid,'compose','project')
            return self.enqueue(pid,{'id':self.app.uid(),'kind':'compose','target':'project','target_id':'project','title':'合片导出','model':'ffmpeg','snapshot':p})
    def reject_duplicate(self,pid,kind,target_id):
        for j in self.list(pid):
            if j.get('kind')==kind and j.get('target_id')==target_id and j.get('status') in ACTIVE:raise ValueError('相同任务已在队列中')
    def public(self,pid,j):
        keep={k:v for k,v in j.items() if k not in ('request','snapshot','_llm_skill_config','reference_sha256','script_skill_text','extraction_skill_text','storyboard_skill_text','storyboard_official_text','huobao_prompt_generator_text','huobao_trace','huobao_rows','huobao_asset_prompt_draft','storyboard_draft','storyboard_prompt_diagnostics','storyboard_json_diagnostics','storyboard_planning_parts','storyboard_seed_parts','storyboard_prompt_parts','storyboard_seed_prompts','storyboard_mode_official','director_scenes','director_location_context','h3v2_diagnostics','h3v2_profiles')};keep['project_id']=pid;keep.setdefault('project_name',pid[:8]);return keep
    def list(self,pid=None):
        with self.list_lock:return self._list(pid)
    def _list(self,pid=None):
        jobs=[];projects={}
        files=(self.app.project(pid).parent/'jobs').glob('*.json') if pid else self.app.DATA.glob('*/jobs/*.json')
        for f in files:
            if f.name.endswith('.workflow.json'):continue
            try:
                stamp=f.stat();key=[stamp.st_mtime_ns,stamp.st_size];cache=self.list_cache.get(str(f));project_id=f.parent.parent.name
                if cache and cache[0]==key:
                    jobs.append(copy.deepcopy(cache[1]));continue
                index=f.parent/'.queue-index'/f.name
                try:
                    record=json.loads(index.read_text())
                    if record['stamp']==key:
                        self.list_cache[str(f)]=(key,record['job']);jobs.append(copy.deepcopy(record['job']));continue
                except (OSError,ValueError,KeyError,TypeError):pass
                j=json.loads(f.read_text())
                if 'kind' not in j:continue
                if project_id not in projects:projects[project_id]=self.app.load(project_id)
                p=projects[project_id];j.setdefault('project_name',p['name']);j.setdefault('model',(j.get('request') or {}).get('model'));obj=next((x for x in p['shots']+p['assets'] if x['id']==j.get('target_id')),{})
                j.setdefault('title',obj.get('title') or obj.get('name') or '生成任务')
                if not j.get('finished_at') and j['status']=='completed':
                    version=next((v for s in p['shots']+p['assets'] for v in s.get('versions',[]) if v.get('id')==j['id']),{})
                    if version.get('created'):j['finished_at']=version['created']
                row=self.public(project_id,j);self.list_cache[str(f)]=(key,row);jobs.append(copy.deepcopy(row))
                # Discard large generation inputs before caching. The full job is untouched.
                try:
                    if f.stat().st_mtime_ns==key[0]:
                        index.parent.mkdir(exist_ok=True);self.app.save(index,{'stamp':key,'job':row})
                except OSError:pass
            except (FileNotFoundError,ValueError,KeyError):continue
        jobs.sort(key=lambda j:j.get('created',0),reverse=True)
        samples={}
        for j in jobs:
            if j['status']=='completed' and j.get('started_at') and j.get('finished_at') and not j.get('timing_approximate'):
                seconds=j['finished_at']-j['started_at']
                if seconds>0:samples.setdefault((j['kind'],j.get('model'),j.get('video_duration')),[]).append(seconds)
        for j in jobs:
            j['elapsed_seconds']=max(0,(j.get('finished_at') or time.time())-j['started_at']) if j.get('started_at') else None
            sample=samples.get((j['kind'],j.get('model'),j.get('video_duration')),[])[:10]
            j['eta_at']=None
            if j['status']=='running' and j.get('started_at') and len(sample)>=3:
                expected=statistics.median(sample)
                if j['elapsed_seconds']<expected:j.update(eta_at=j['started_at']+expected,eta_samples=len(sample))
        return jobs
    def resume(self):
        for row in self.list():
            if row.get('status') not in ACTIVE:continue
            pid=row['project_id'];f=self.app.job_path(pid,row['id']);j=json.loads(f.read_text())
            if j.get('status') not in ACTIVE:continue
            if j.get('cancel_requested') and j.get('kind')=='audio' and j.get('speech_remote_id'):
                self.enqueue(pid,j)
            elif j.get('cancel_requested'):
                # Confirm upstream cancellation again after a process restart.
                threading.Thread(target=self.cancel,args=(pid,j['id']),daemon=True).start()
            elif j.get('kind')=='asset_sync':self.enqueue(pid,j)
            elif j.get('phase') in ('submitting','speech_submitting','cloud_submitting') and not j.get('prompt_id') and not j.get('speech_remote_id') and not j.get('cloud_task_id'):
                j.update(status='failed',finished_at=time.time(),error='提交时服务重启，上游结果不明确；保留记录，请核对后重试');self.persist(pid,j)
            elif j.get('cloud_task_id') or j.get('prompt_id') or j.get('remote_id') or j.get('speech_remote_id') or j['status']=='queued':self.enqueue(pid,j)
            else:
                j.update(status='failed',finished_at=time.time(),error='服务曾重启，执行结果不明确；请检查后重试');self.persist(pid,j)
