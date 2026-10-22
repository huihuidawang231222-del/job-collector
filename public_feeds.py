"""Adapters for documented, unauthenticated employer job-board GET feeds."""
import json,re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlsplit,urlencode
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError,URLError
from types import SimpleNamespace
from datetime import datetime,timezone

LEVER_DOC='https://github.com/lever/postings-api'
MAX_FEED_BYTES=12*1024*1024

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args):return None

class TextParser(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.hidden+=1
        if tag in ('p','div','li','br','h1','h2','h3'):self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.hidden=max(0,self.hidden-1)
        if tag in ('p','div','li'):self.parts.append('\n')
    def handle_data(self,text):
        if not self.hidden:self.parts.append(text)

def plain(value):
    parser=TextParser();parser.feed(str(value or ''))
    return re.sub(r'\n[ \t]*\n+', '\n\n',unescape(''.join(parser.parts))).strip()

def lever_config(board_url):
    p=urlsplit(board_url);host=(p.hostname or '').lower();parts=[x for x in p.path.split('/') if x]
    if p.scheme!='https' or p.username or p.password or p.port is not None or p.query or p.fragment:
        raise ValueError('请填写不带查询参数的HTTPS雇主岗位列表地址')
    if host not in ('jobs.lever.co','jobs.eu.lever.co') or len(parts)!=1 or not re.fullmatch(r'[A-Za-z0-9_-]+',parts[0]):
        raise ValueError('当前仅支持 jobs.lever.co/公司 或 jobs.eu.lever.co/公司')
    api='api.eu.lever.co' if host=='jobs.eu.lever.co' else 'api.lever.co'
    return {'api':api,'site':parts[0],'host':host,'board':f'https://{host}/{parts[0]}'}

def documented_lever_policy(url,directory,now=None):
    """Only the exact documented GET list route; no apply/admin/internal endpoints."""
    p=urlsplit(url)
    if p.scheme!='https' or p.hostname not in ('api.lever.co','api.eu.lever.co') or not re.fullmatch(r'/v0/postings/[A-Za-z0-9_-]+',p.path):
        from collection_safety import SafetyStop
        raise SafetyStop('不是已接入的官方公开岗位接口')
    return {'text':'','source':LEVER_DOC}

def read_lever_page(config,skip,limit,guard,opener=None):
    if not 0<=skip<=10000 or not 1<=limit<=200:raise ValueError('分页参数超出范围')
    url=f"https://{config['api']}/v0/postings/{config['site']}?"+urlencode({'mode':'json','skip':skip,'limit':limit})
    guard.before('读取官方公开岗位列表',url)
    request=Request(url,headers={'User-Agent':'JobCollector/0.5 (public employer postings)','Accept':'application/json'},method='GET')
    try:
        with (opener or build_opener(NoRedirect())).open(request,timeout=30) as response:
            data=response.read(MAX_FEED_BYTES+1)
            if len(data)>MAX_FEED_BYTES:raise ValueError('岗位列表超过12MB，停止本来源')
            if 'json' not in response.headers.get('Content-Type','').lower():raise ValueError('接口未返回JSON，停止本来源')
        rows=json.loads(data)
        if not isinstance(rows,list) or any(not isinstance(x,dict) for x in rows):raise ValueError('公开岗位接口结构异常')
        return rows,url,len(data)
    except HTTPError as e:
        guard.response(SimpleNamespace(status=e.code,headers={k.lower():v for k,v in e.headers.items()}))
        raise ValueError(f'公开接口HTTP {e.code}，未重试') from None
    except (URLError,TimeoutError,ConnectionError):
        guard.trip('公开接口连接失败',seconds=300)

def normalize_lever(posting,source):
    config=lever_config(source['url']);ident=str(posting.get('id','')).strip()
    title=plain(posting.get('text'))
    if not ident or not title:return None
    if re.search(r'general application|talent community|expression of interest|open application|人才库',title,re.I):return None
    url=posting.get('hostedUrl','');p=urlsplit(url)
    if p.scheme!='https' or p.hostname!=config['host'] or p.username or p.password or p.path.rstrip('/')!=f"/{config['site']}/{ident}":return None
    sections=[]
    # descriptionPlain already includes openingPlain; do not append opening twice.
    description=posting.get('descriptionPlain') or plain(posting.get('description'))
    if description:sections.append(description)
    for item in posting.get('lists') or []:
        if isinstance(item,dict):
            section='\n'.join(x for x in [plain(item.get('text')),plain(item.get('content'))] if x)
            if section:sections.append(section)
    additional=posting.get('additionalPlain') or plain(posting.get('additional'))
    if additional:sections.append(additional)
    jd='\n\n'.join(sections).strip()
    if len(jd)<80:return None
    c=posting.get('categories') or {};locations=c.get('allLocations') or [c.get('location','')]
    if isinstance(locations,str):locations=[locations]
    location='；'.join(dict.fromkeys(str(x).strip() for x in locations if x)) or '未说明'
    salary_range=posting.get('salaryRange') or {};currency=str(salary_range.get('currency') or '')
    salary=str(posting.get('salaryDescriptionPlain') or '').strip()
    if not salary and salary_range.get('min') is not None and salary_range.get('max') is not None:
        interval={'per-year':'年','per-month':'月','per-hour':'时','per-day':'天'}.get(salary_range.get('interval'),salary_range.get('interval') or '未说明周期')
        salary=f"{salary_range['min']}-{salary_range['max']} {currency}/{interval}"
    return dict(title=title,company=source.get('company') or config['site'],location=location,salary=salary,currency=currency,jd=jd,
        source='雇主官网公开岗位接口',source_job_id=ident,source_provider='Lever',career_entry=config['board'],source_evidence=LEVER_DOC,
        source_trust=source.get('trust','雇主招聘系统，官网关联待核实'),extraction_method='Lever官方Postings API',
        url=f"https://{config['host']}/{config['site']}/{ident}",listing_state='本次公开岗位列表中存在，投递前仍需核实',
        last_checked=datetime.now(timezone.utc).isoformat(timespec='seconds'),employment_type=c.get('commitment',''),
        department=c.get('department',''),team=c.get('team',''),workplace_type=posting.get('workplaceType',''),country=posting.get('country') or '')
