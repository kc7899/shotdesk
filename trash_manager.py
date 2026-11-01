"""Seven-day trash retention, reversible restore, snapshot-confirmed purge and audit log."""
import datetime,hashlib,json,math,os,re,shutil,threading,time
from pathlib import Path
TZ=datetime.timezone(datetime.timedelta(hours=8))
ENTRY=re.compile(r'([a-f0-9]{32})-[0-9]+-[a-f0-9]{8}')
class TrashManager:
    retention_days=7
    def __init__(self,app):self.app=app
    def root(self):
        root=self.app.DATA/'.trash'
        if root.is_symlink():raise ValueError('回收目录无效')
        root.mkdir(exist_ok=True);return root
    def entry(self,key):
        if not isinstance(key,str) or not ENTRY.fullmatch(key):raise ValueError('回收项目 ID 无效')
        root=self.root();folder=root/key
        if folder.is_symlink() or not folder.is_dir() or folder.resolve().parent!=root.resolve():raise ValueError('回收项目不存在或目录无效')
        meta=json.loads((folder/'deletion.json').read_text());project=json.loads((folder/'project.json').read_text())
        if meta.get('project_id')!=ENTRY.fullmatch(key)[1] or project.get('id')!=meta['project_id']:raise ValueError('回收项目记录不匹配')
        deleted=float(meta.get('deleted_at',0))
        if not math.isfinite(deleted) or deleted<=0:raise ValueError('缺少有效删除时间，不自动清理')
        size=0
        for base,dirs,files in os.walk(folder,followlinks=False):
            dirs[:]=[d for d in dirs if not (Path(base)/d).is_symlink()]
            for name in files:
                f=Path(base)/name
                if not f.is_symlink():size+=f.stat().st_size
        return {'trash_id':key,'project_id':meta['project_id'],'name':meta.get('name',project.get('name','未命名')),'deleted_at':deleted,'expires_at':deleted+self.retention_days*86400,'bytes':size}
    def listing(self):
        with self.app.LOCK:
            items=[];ignored=0
            for folder in self.root().iterdir():
                try:items.append(self.entry(folder.name))
                except (ValueError,OSError,KeyError,TypeError):ignored+=1
            items.sort(key=lambda x:x['deleted_at'],reverse=True)
            token=hashlib.sha256(json.dumps(items,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            return {'items':items,'count':len(items),'bytes':sum(i['bytes'] for i in items),'confirm_token':token,'ignored':ignored,'retention_days':self.retention_days,'cleanup_hour':4,'timezone':'Asia/Shanghai'}
    def audit(self,event):
        value={'time':time.time(),**event}
        with (self.app.DATA/'trash-cleanup.jsonl').open('a') as f:f.write(json.dumps(value,ensure_ascii=False)+'\n')
    def logs(self):
        with self.app.LOCK:
            path=self.app.DATA/'trash-cleanup.jsonl'
            if not path.exists():return []
            from collections import deque
            result=[]
            with path.open() as source:lines=deque(source,maxlen=50)
            for line in reversed(lines):
                try:result.append(json.loads(line))
                except ValueError:continue
            return result
    def restore(self,key):
        with self.app.LOCK:
            item=self.entry(key);folder=self.root()/key;destination=self.app.project(item['project_id']).parent
            if destination.exists() or destination.is_symlink():raise ValueError('同 ID 项目已存在，不能覆盖，请先处理冲突')
            # Only completed/stopped archives can be restored; never revive unfinished jobs implicitly.
            for file in (folder/'jobs').glob('*.json'):
                if file.name.endswith('.workflow.json'):continue
                job=json.loads(file.read_text())
                if job.get('status') in ('queued','running','cancelling'):raise ValueError('归档含未结束任务，请管理员先检查')
            folder.rename(destination);(destination/'deletion.json').unlink(missing_ok=True)
            self.audit({'action':'restore','project_id':item['project_id'],'name':item['name'],'bytes':item['bytes']})
            return {'restored':True,'project_id':item['project_id']}
    def purge(self,token=None,automatic=False,now=None):
        with self.app.LOCK:
            snapshot=self.listing();now=time.time() if now is None else now
            if not automatic and (not token or token!=snapshot['confirm_token']):raise ValueError('回收站内容已变化，请刷新并重新确认清空')
            selected=[item for item in snapshot['items'] if not automatic or item['expires_at']<=now];removed=[];errors=[]
            for item in selected:
                try:
                    self.entry(item['trash_id'])
                    shutil.rmtree(self.root()/item['trash_id']);removed.append(item)
                except (OSError,ValueError) as exc:errors.append({'name':item['name'],'error':str(exc)})
            result={'action':'automatic_cleanup' if automatic else 'empty_trash','count':len(removed),'bytes':sum(i['bytes'] for i in removed),'projects':[{'id':i['project_id'],'name':i['name']} for i in removed],'errors':errors,'ignored':snapshot['ignored']}
            self.audit(result);return result
    def daily_tick(self,now=None):
        now=time.time() if now is None else now;local=datetime.datetime.fromtimestamp(now,TZ)
        if local.hour<4:return False
        state_path=self.app.DATA/'trash-maintenance.json'
        with self.app.LOCK:
            state=json.loads(state_path.read_text()) if state_path.exists() else {}
            if state.get('last_cleanup_date')==local.date().isoformat():return False
            self.purge(automatic=True,now=now)
            self.app.save(state_path,{'last_cleanup_date':local.date().isoformat(),'last_cleanup_at':now});return True
    def start(self):
        def loop():
            while True:
                try:self.daily_tick()
                except Exception as exc:
                    try:self.audit({'action':'cleanup_error','error':str(exc)})
                    except OSError:pass
                time.sleep(30)
        threading.Thread(target=loop,daemon=True).start()
