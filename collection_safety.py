"""Conservative access gates and bounded collection; no evasion features."""
import json
import re
import time
import os
from functools import wraps
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit, unquote
from urllib.request import Request, urlopen

AGENT = 'JobCollector'
MIN_INTERVAL = 10
MAX_ACTIONS = 40
MAX_SESSION_SECONDS = 300
POLICY_TTL = 86400


class SafetyStop(RuntimeError):
    pass


def single_collector(directory):
    def decorate(function):
        @wraps(function)
        def run(*args,**kwargs):
            root=Path(directory);root.mkdir(parents=True,exist_ok=True);lock=root/'worker.lock'
            try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
            except FileExistsError:raise SafetyStop('已有采集进程或未清理的进程锁；请先停止已有任务') from None
            try:
                os.write(fd,str(os.getpid()).encode());os.close(fd)
                return function(*args,**kwargs)
            finally:lock.unlink(missing_ok=True)
        return run
    return decorate


def robots_allowed(text, url):
    """Wildcard/end-anchor matching, most specific agent and longest path rule."""
    groups=[];agents=[];rules=[];started=False
    for raw in text.splitlines()+['User-agent: __end__']:
        line=raw.split('#',1)[0].strip()
        if ':' not in line:continue
        key,value=(part.strip() for part in line.split(':',1));key=key.lower()
        if key=='user-agent':
            if started:
                groups.append((agents,rules));agents=[];rules=[];started=False
            agents.append(value.lower())
        elif key in ('allow','disallow') and agents:
            started=True
            if value:rules.append((key,value))
    matches=[]
    for names,entries in groups:
        specificity=max((0 if name=='*' else len(name) for name in names if name=='*' or name in AGENT.lower()),default=-1)
        if specificity>=0:matches.append((specificity,entries))
    if not matches:return True
    best=max(item[0] for item in matches)
    parts=urlsplit(url);target=unquote(parts.path or '/')+('?' + unquote(parts.query) if parts.query else '')
    decisions=[]
    for specificity,entries in matches:
        if specificity!=best:continue
        for key,pattern in entries:
            end=pattern.endswith('$');body=pattern[:-1] if end else pattern
            regex='^'+'.*'.join(re.escape(part) for part in unquote(body).split('*'))+('$' if end else '')
            if re.search(regex,target):decisions.append((len(body.replace('*','')),key=='allow'))
    return max(decisions,default=(0,True))[1]


def read_json(path):
    if not path.exists():return {}
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data,dict):raise ValueError('Expected object')
        return data
    except (ValueError,OSError):raise SafetyStop('保护状态文件无法读取；停止采集，请检查本地数据文件') from None


def write_json(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)


def check_policy(url, directory, now=None):
    now=time.time() if now is None else now
    directory=Path(directory);parts=urlsplit(url)
    if parts.scheme not in ('http','https') or not parts.hostname:raise SafetyStop('非网页地址，停止自动采集')
    origin=f'{parts.scheme}://{parts.netloc}'
    cache_path=directory/'policy-cache.json';cache=read_json(cache_path);record=cache.get(origin)
    if not record or now-record.get('checked_at',0)>POLICY_TTL:
        record={'checked_at':now,'source':origin+'/robots.txt','status':'unknown'}
        try:
            request=Request(record['source'],headers={'User-Agent':AGENT+'/0.3 (policy check)'})
            with urlopen(request,timeout=10) as response:
                raw=response.read(65537)
                text=raw.decode('utf-8-sig',errors='replace')
                if (len(raw)<=65536 and urlsplit(response.url).hostname==parts.hostname and
                        not re.search(r'<(?:!doctype|html|script|head)',text,re.I) and
                        re.search(r'^\s*user-agent\s*:',text,re.I|re.M)):
                    record.update(status='checked',text=text)
        except HTTPError as error:
            record['http_status']=error.code
            if error.code in (401,403,429):record.update(status='denied')
        except Exception:pass
        cache[origin]=record;write_json(cache_path,cache)
    if record['status']!='checked':
        raise SafetyStop('平台访问规则待核或被验证/拒绝，已关闭该地址自动采集；可人工浏览并导入资料')
    if not robots_allowed(record['text'],url):
        raise SafetyStop('平台 robots.txt 限制此路径，已阻止自动采集；不支持通过改身份或代理绕过')
    return record


class CollectionGuard:
    def __init__(self,host,directory,clock=time.time,sleeper=time.sleep,policy=check_policy):
        self.host=host;self.directory=Path(directory);self.clock=clock;self.sleep=sleeper;self.policy=policy
        self.state_path=self.directory/'collection-protection.json'
        self.state=read_json(self.state_path).get(host,{})
        self.started=clock();self.actions=0;self.challenges=0

    def audit(self,event,**data):
        self.directory.mkdir(parents=True,exist_ok=True)
        entry=dict(at=datetime.now(timezone.utc).isoformat(timespec='seconds'),host=self.host,event=event,**data)
        with (self.directory/'collection-events.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(entry,ensure_ascii=False)+'\n')

    def persist(self):
        states=read_json(self.state_path);states[self.host]=self.state;write_json(self.state_path,states)

    def checkpoint(self):
        now=self.clock()
        if now<self.state.get('cooldown_until',0):raise SafetyStop('该平台处于冷却期，重新启动任务也不会解除；请稍后再检查')
        if now-self.started>=MAX_SESSION_SECONDS:raise SafetyStop('已达到单平台5分钟任务时限，停止自动采集')
        if self.actions>=MAX_ACTIONS:raise SafetyStop('已达到单平台40次自动页面动作上限')
        day=int(now//86400)
        if self.state.get('day')!=day:self.state.update(day=day,daily_actions=0)
        if self.state.get('daily_actions',0)>=MAX_ACTIONS:raise SafetyStop('已达到本工具单平台每日40次自动页面动作上限')

    def before(self,action,url):
        self.checkpoint()
        policy=self.policy(url,self.directory,now=self.clock()) or {}
        delays=re.findall(r'^\s*crawl-delay\s*:\s*(\d+(?:\.\d+)?)\s*$',policy.get('text',''),re.I|re.M)
        rates=re.findall(r'^\s*request-rate\s*:\s*(\d+)\s*/\s*(\d+)\s*$',policy.get('text',''),re.I|re.M)
        interval=max([MIN_INTERVAL]+[float(d) for d in delays]+[int(seconds)/int(count) for count,seconds in rates if int(count)>0])
        if interval>=MAX_SESSION_SECONDS:raise SafetyStop('平台声明的访问间隔超出本工具单任务时限，停止自动采集')
        wait=interval-(self.clock()-self.state.get('last_action',0))
        if wait>0:self.sleep(wait)
        self.checkpoint();self.actions+=1
        self.state['last_action']=self.clock();self.state['daily_actions']=self.state.get('daily_actions',0)+1
        self.persist();self.audit('action',action=action,path=urlsplit(url).path)

    def trip(self,reason,seconds=3600):
        self.state['cooldown_until']=max(self.state.get('cooldown_until',0),self.clock()+seconds)
        self.persist();self.audit('cooldown',reason=reason,seconds=seconds)
        raise SafetyStop(reason+'；本工具已停止并进入冷却期，不自动重试')

    def response(self,response):
        if response is None:return
        code=response.status
        if code not in (401,403,429) and not 500<=code<=599:return
        seconds=300 if 500<=code<=599 else 3600
        retry=response.headers.get('retry-after','')
        if retry:
            try:seconds=max(seconds,int(retry))
            except ValueError:
                try:seconds=max(seconds,parsedate_to_datetime(retry).timestamp()-self.clock())
                except (TypeError,ValueError,OverflowError):pass
        self.trip(f'平台返回HTTP {code}',seconds)

    def observe(self,response):
        if response.request.resource_type not in ('document','xhr','fetch'):return
        host=urlsplit(response.url).hostname or ''
        if host!=self.host and not host.endswith('.'+self.host):return
        try:self.response(response)
        except SafetyStop:pass  # The persisted cooldown stops the next checkpoint.

    def challenge(self):
        self.challenges+=1;self.audit('manual_verification',count=self.challenges)
        previous=self.state.get('challenge_at')
        self.state['challenge_at']=self.clock();self.persist()
        if self.challenges>1 or (previous is not None and self.clock()-previous<3600):
            self.trip('一小时内重复出现登录或安全验证')

