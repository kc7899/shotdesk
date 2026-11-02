"""Private local service settings and single-user access, standard library only."""
import hashlib,hmac,json,os,secrets,time,urllib.parse,urllib.request,threading
from pathlib import Path
class RuntimeConfig:
    fields={'llm_url','llm_model','llm_api_key','comfy_url','speech_url','vision_model','video_providers','llm_skills'}
    def __init__(self,data):self.data=Path(data);self.path=self.data/'settings.json';self.lock=threading.RLock();self.attempts={}
    def read(self):
        with self.lock:
            if not self.path.exists():return {}
            value=json.loads(self.path.read_text())
            if not isinstance(value,dict):raise ValueError('服务配置文件必须是对象')
            return value
    def write(self,value):
        with self.lock:
            self.data.mkdir(parents=True,exist_ok=True);p=self.path.with_suffix('.tmp');p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');p.chmod(0o600);p.replace(self.path)
    @staticmethod
    def url(value):
        if not isinstance(value,str) or len(value)>2048:raise ValueError('服务地址须为HTTP或HTTPS网址')
        value=value.strip().rstrip('/');parsed=urllib.parse.urlsplit(value)
        if value and (parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment):raise ValueError('服务地址须为HTTP或HTTPS网址，密钥请填在单独字段')
        return value
    def update(self,body):
        if not isinstance(body,dict) or set(body)-self.fields-{'access_password','clear_api_key'}:raise ValueError('包含不支持的服务设置')
        value=self.read()
        for key in self.fields:
            if key not in body:continue
            item=body[key]
            if key=='llm_skills':
                import llm_skills
                value[key]=llm_skills.validate(item);continue
            if key=='video_providers':
                import cloud_video
                value[key]=cloud_video.validate_profiles(item,value.get(key,[]),self.url);continue
            if not isinstance(item,str) or len(item)>8192:raise ValueError('服务设置须为文字')
            item=item.strip()
            if key.endswith('_url'):item=self.url(item)
            if key=='llm_url' and item:
                if item.endswith('/chat/completions'):item=item[:-17]
                if not item.endswith('/v1'):item+='/v1'
            if key=='llm_api_key' and not item:continue  # Empty password field means keep saved key.
            value[key]=item
        if body.get('clear_api_key'):value['llm_api_key']=''
        password=body.get('access_password')
        if password is not None:
            if not isinstance(password,str) or len(password)<10:raise ValueError('访问密码至少10个字符；留空时请不要提交此字段')
            salt=secrets.token_hex(16);value['password_salt']=salt;value['password_hash']=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),200000).hex();value['session_secret']=secrets.token_hex(32)
        self.write(value)
    def has_password(self):return bool(os.getenv('SHOTDESK_ACCESS_TOKEN') or self.read().get('password_hash'))
    def password_ok(self,password):
        token=os.getenv('SHOTDESK_ACCESS_TOKEN')
        if token:return hmac.compare_digest(str(password).encode(),token.encode())
        value=self.read()
        if not value.get('password_hash'):return False
        digest=hashlib.pbkdf2_hmac('sha256',str(password).encode(),bytes.fromhex(value['password_salt']),200000).hex()
        return hmac.compare_digest(digest,value['password_hash'])
    def session_secret(self):
        if os.getenv('SHOTDESK_ACCESS_TOKEN'):return os.environ['SHOTDESK_ACCESS_TOKEN'].encode()
        with self.lock:
            value=self.read()
            if not value.get('session_secret'):value['session_secret']=secrets.token_hex(32);self.write(value)
            return value['session_secret'].encode()
    def issue_cookie(self):
        message=str(int(time.time())+86400)+'.'+secrets.token_hex(12);return message+'.'+hmac.new(self.session_secret(),message.encode(),'sha256').hexdigest()
    def authenticated(self,headers):
        if not self.has_password():return True
        auth=headers.get('Authorization','')
        if auth.startswith('Bearer ') and self.password_ok(auth[7:]):return True
        from http.cookies import SimpleCookie
        try:
            cookies=SimpleCookie();cookies.load(headers.get('Cookie',''));token=cookies['shotdesk_session'].value;expiry,nonce,digest=token.split('.');message=expiry+'.'+nonce
            return int(expiry)>time.time() and hmac.compare_digest(digest,hmac.new(self.session_secret(),message.encode(),'sha256').hexdigest())
        except (KeyError,ValueError):return False
    def allow_login(self,ip):
        with self.lock:
            now=time.time();self.attempts={k:v for k,v in self.attempts.items() if now-v[0]<60}
            start,count=self.attempts.get(ip,(now,0));self.attempts[ip]=(start,count+1);return count<10
