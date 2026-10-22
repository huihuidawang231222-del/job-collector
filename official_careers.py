"""Bounded public-career discovery/capture using Playwright, without login/evasion."""
import argparse,hashlib,json,re,time,ipaddress,socket
from collections import deque
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,urlencode,parse_qsl
from urllib.request import Request,urlopen,build_opener,HTTPRedirectHandler,getproxies
from urllib.error import HTTPError
from core import ROOT,save
from collection_safety import CollectionGuard,SafetyStop,single_collector,check_policy

DATA=ROOT/'data'; STATUS=DATA/'official-task.json'; STOP=DATA/'official-stop'
TRACKING={'trid','source','ref','referrer','gh_src'}
ATS=('jobs.smartrecruiters.com','jobs.lever.co','boards.greenhouse.io','job-boards.greenhouse.io','zhiye.com','hotjob.cn','myworkdayjobs.com','moka.cn','mokahr.com')
JOB_WORDS=re.compile(r'招聘|职位|岗位|加入我们|人才|下一页|job|career|vacanc|posting|position|recruit|analyst|engineer|工程师|分析师',re.I)
BLOCK_TEXT=re.compile(r'请完成安全验证|拖动滑块|访问过于频繁|验证你是真人|verify you are human|checking your browser|unusual traffic|access denied|请先登录',re.I)

def canonical(url):
    p=urlsplit(url)
    query=urlencode([(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if k not in TRACKING and not k.startswith('utm_')])
    return urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path or '/',query,''))

def public_url(url,resolve=False):
    p=urlsplit(url)
    if p.scheme not in ('https','http') or not p.hostname or p.username or p.password or p.port not in (None,80,443):return False
    if p.hostname.lower() in ('localhost','metadata.google.internal') or p.hostname.endswith(('.local','.internal')):return False
    try:
        addr=ipaddress.ip_address(p.hostname)
        return addr.is_global
    except ValueError:pass
    if resolve:
        try:return all(ipaddress.ip_address(x[4][0]).is_global for x in socket.getaddrinfo(p.hostname,None))
        except OSError:
            # Managed HTTPS proxies resolve public hostnames remotely; literal/private
            # addresses and local hostnames were already rejected above.
            return bool(getproxies().get(p.scheme))
    return True

class PublicRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if not public_url(newurl,resolve=True):raise SafetyStop('拒绝跳转到本地或非公开地址')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def fetch_public_html(url):
    if not public_url(url,resolve=True):raise SafetyStop('非公开网页地址')
    request=Request(url,headers={'User-Agent':'JobCollector/0.4 (public career pages)'})
    with build_opener(PublicRedirect()).open(request,timeout=25) as response:
        data=response.read(2*1024*1024+1)
        if len(data)>2*1024*1024:raise SafetyStop('页面超过2MB，未读取全部内容')
        content_type=response.headers.get('Content-Type','')
        if 'html' not in content_type:raise SafetyStop('来源不是HTML招聘页面')
        encoding=response.headers.get_content_charset() or 'utf-8'
        return response.url,data.decode(encoding,errors='replace')


def known_ats(host):return any(host==x or host.endswith('.'+x) for x in ATS)

def linked_scope(url,roots,ats_tenants):
    if not public_url(url):return False
    p=urlsplit(url);host=p.hostname or ''
    # exact/subdomain company origins, but do not expand a shared ATS to all companies
    for root in roots:
        r=urlsplit(root);rh=r.hostname or ''
        if host==rh or (not known_ats(rh) and host.endswith('.'+rh)):
            if known_ats(rh):return p.path.startswith(r.path.rstrip('/')+'/') or p.path==r.path
            return True
    return any(host==h and (p.path==path or p.path.startswith(path.rstrip('/')+'/')) for h,path in ats_tenants)

def tenant(url):
    p=urlsplit(url);parts=[x for x in p.path.split('/') if x]
    if p.hostname in ('jobs.smartrecruiters.com','jobs.lever.co','boards.greenhouse.io','job-boards.greenhouse.io'):
        return p.hostname,'/'+parts[0] if parts else '/__no_tenant__'
    return p.hostname,'/'

def matches(row,keyword,city):
    text=' '.join(str(row.get(k,'')) for k in ('title','jd','company')).casefold()
    keys=[x.strip().casefold() for x in re.split(r'[,，;；\n]',keyword) if x.strip()]
    cities=[city.casefold()]
    if city=='广州':cities+=['guangzhou','canton']
    loc=str(row.get('location','')).casefold()
    def hit(k):
        return bool(re.search(r'(?<![a-z])'+re.escape(k)+r'(?![a-z])',text)) if k.isascii() and k.isalpha() and len(k)<=4 else k in text
    return (not keys or any(hit(k) for k in keys)) and (not city or any(c in loc for c in cities))

def listing_state(row):
    value=str(row.get('valid_through',''))
    if value:
        try:
            dt=datetime.fromisoformat(value.replace('Z','+00:00'))
            if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
            if dt<datetime.now(timezone.utc):return '已过截止时间'
        except ValueError:pass
    return '页面可访问，是否在招待核实'

def official_policy(url,directory,now=None):
    """Keep platform gates; a genuine robots 404 means no published robots file."""
    try:return check_policy(url,directory,now=now)
    except SafetyStop as original:
        # Do not retry any challenged/denied robots; use cached status only.
        from collection_safety import read_json,write_json,POLICY_TTL
        p=urlsplit(url);origin=f'{p.scheme}://{p.netloc}';cache=read_json(Path(directory)/'policy-cache.json');r=cache.get(origin,{})
        if r.get('status')=='absent':return {'text':''}
        # check_policy now records 404 explicitly; other unknown/denied states stay closed.
        if r.get('http_status')==404:
            r['status']='absent';cache[origin]=r;write_json(Path(directory)/'policy-cache.json',cache);return {'text':''}
        raise original

def write_status(**fields):
    DATA.mkdir(exist_ok=True);tmp=STATUS.with_suffix('.tmp')
    tmp.write_text(json.dumps(fields,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(STATUS)

def search_queries(company,keyword,city):
    term=next((x.strip() for x in re.split(r'[,，]',keyword) if x.strip()),'招聘')
    return [f'{company} {city} {term} 官方 招聘']

def discover_search(page,query,guard):
    url='https://www.bing.com/search?'+urlencode({'q':query})
    guard.before('发现招聘入口',url)
    response=page.goto(url,wait_until='domcontentloaded',timeout=30000);guard.response(response)
    data=page.evaluate((ROOT/'official_extract.js').read_text(encoding='utf-8'))
    if BLOCK_TEXT.search(data['body']):guard.trip('搜索页面要求验证')
    # Search results are candidates, never automatically trusted or visited.
    links=page.locator('li.b_algo h2 a').evaluate_all('(nodes)=>nodes.map(a=>({url:a.href,text:a.innerText}))')
    return [dict(x,query=query,trust='搜索候选，未核实官网') for x in links if public_url(x['url'])][:10]

@single_collector(DATA)
def run(args):
    from playwright.sync_api import sync_playwright
    from browser_runtime import browser_config
    DATA.mkdir(exist_ok=True);STOP.unlink(missing_ok=True)
    sources=json.loads(Path(args.sources).read_text(encoding='utf-8'))
    if not isinstance(sources,list) or not sources or len(sources)>30:raise ValueError('来源须为1—30项数组')
    script=(ROOT/'official_extract.js').read_text(encoding='utf-8');reports=[];captured=[];candidates=[]
    existing={canonical(r['url']):r for r in __import__('core').load() if r.get('url')}
    with sync_playwright() as p:
        _,opts,_=browser_config(p.chromium)
        browser=p.chromium.launch(headless=args.headless,**opts)
        context=browser.new_context(user_agent='JobCollector/0.4 (+public career page collection)',java_script_enabled=args.transport!='html')
        # Block private destinations and any download/post/application action, including redirects.
        def route(req):
            request=req.request
            if request.method not in ('GET','HEAD') or not public_url(request.url,resolve=True):req.abort()
            else:req.continue_()
        context.route('**/*',route)
        try:
            for source in sources:
                if STOP.exists():break
                url=canonical(str(source.get('url','')))
                if not public_url(url,resolve=True):reports.append({'url':url,'state':'invalid_url'});continue
                root_host=urlsplit(url).hostname;guard=CollectionGuard(root_host,DATA,policy=official_policy)
                page=context.new_page();page.on('response',guard.observe)
                if args.transport=='html':page.route('**/*',lambda r:r.abort())
                queue=deque([(url,'用户提供/内置官网目录',0)]);visited=set();ats_tenants=set();count=0;cached=0;found=0
                try:
                    if args.discover and args.transport=='browser':
                        sg=CollectionGuard('www.bing.com',DATA,policy=official_policy)
                        for query in search_queries(source.get('company',''),args.keyword,args.city):
                            try:candidates.extend(discover_search(page,query,sg))
                            except SafetyStop as e:reports.append({'company':source.get('company'),'stage':'搜索发现','state':'protected','message':str(e)})
                    while queue and len(visited)<args.pages and count<args.limit and not STOP.exists():
                        current,provenance,depth=queue.popleft();current=canonical(current)
                        if current in visited:continue
                        visited.add(current)
                        old=existing.get(current)
                        if old and old.get('jd') and not args.refresh:
                            cached+=1;continue
                        guard.before('读取官网页面',current)
                        if args.transport=='html':
                            try:final_url,html=fetch_public_html(current)
                            except HTTPError as error:
                                from types import SimpleNamespace
                                guard.response(SimpleNamespace(status=error.code,headers={k.lower():v for k,v in error.headers.items()}))
                                raise
                            if not linked_scope(final_url,[url],ats_tenants):raise SafetyStop('页面跳转到未核实来源，停止')
                            # Browser renders public HTML with network and scripts disabled in snapshot mode.
                            snapshot_html=re.sub(r'<script(?![^>]*type=[\"\']application/ld\+json)[^>]*>.*?</script>','',html,flags=re.S|re.I)
                            page.set_content('<base href="'+final_url.replace('&','&amp;').replace('"','&quot;')+'">'+snapshot_html)
                        else:
                            response=page.goto(current,wait_until='domcontentloaded',timeout=30000);guard.response(response)
                            if response and response.status>=400:raise SafetyStop(f'官网返回HTTP {response.status}，本来源停止')
                            final_url=page.url
                            if not linked_scope(final_url,[url],ats_tenants):raise SafetyStop('页面跳转到未核实来源，停止')
                            page.wait_for_timeout(1000)
                        data=page.evaluate(script)
                        if BLOCK_TEXT.search(data['body']) or re.search(r'/login|/captcha|/security-check',final_url,re.I):guard.trip('官网要求登录或验证')
                        for row in data['jobs']:
                            if not row.get('title') or not row.get('jd'):continue
                            row['url']=canonical(row.get('url') or final_url)
                            if not linked_scope(row['url'],[url],ats_tenants):continue
                            row.update(career_entry=url,source_evidence=provenance,source_trust=source.get('trust','用户提供，主体待核实'),source_company=source.get('company',''),last_checked=datetime.now(timezone.utc).isoformat(timespec='seconds'))
                            row['listing_state']=listing_state(row);found+=1
                            if row['listing_state']=='已过截止时间' or not matches(row,args.keyword,args.city):continue
                            save([row]);captured.append(row);existing[row['url']]=row;count+=1
                            if count>=args.limit:break
                        if depth<3:
                            prioritized=[]
                            for a in data['links']:
                                link=canonical(a['url']);host=urlsplit(link).hostname or ''
                                if link in visited or not JOB_WORDS.search(a['text']+' '+link):continue
                                if known_ats(host) and linked_scope(final_url,[url],ats_tenants):ats_tenants.add(tenant(link))
                                if linked_scope(link,[url],ats_tenants):prioritized.append((link,final_url,depth+1))
                            # bounded queue; keywords in link text prioritized by extraction order only
                            keys=[x.strip().casefold() for x in re.split(r'[,，]',args.keyword) if x.strip()]
                            prioritized.sort(key=lambda item:not any(k in item[0].casefold() for k in keys))
                            if depth==0:
                                for seed in source.get('job_seeds',[]):
                                    if linked_scope(seed,[url],ats_tenants):queue.appendleft((seed,final_url,depth+1))
                            queue.extend(prioritized[:50])
                        write_status(state='running',company=source.get('company'),pages=len(visited),matched=count,reports=reports)
                    reports.append(dict(company=source.get('company'),url=url,state='stopped' if STOP.exists() else 'completed',visited=len(visited),extracted=found,matched=count,cached=cached,remaining=len(queue)))
                except Exception as e:
                    reports.append(dict(company=source.get('company'),url=url,state='protected' if isinstance(e,SafetyStop) else 'failed',message=str(e),matched=count,visited=len(visited)))
                finally:page.close()
        finally:browser.close()
    result={'state':'stopped' if STOP.exists() else 'finished','reports':reports,'jobs':captured,'search_candidates':candidates,'tested_at':datetime.now(timezone.utc).isoformat(timespec='seconds')}
    (DATA/'official-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');write_status(**result)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--sources',default=str(ROOT/'official_sources.json'));parser.add_argument('--keyword',default='数据分析,GIS,运营分析,analyst')
    parser.add_argument('--city',default='广州');parser.add_argument('--pages',type=int,default=8);parser.add_argument('--limit',type=int,default=10)
    parser.add_argument('--transport',choices=['browser','html'],default='browser');parser.add_argument('--headless',action='store_true');parser.add_argument('--refresh',action='store_true');parser.add_argument('--discover',action='store_true')
    args=parser.parse_args()
    if not 1<=args.pages<=20 or not 1<=args.limit<=20:parser.error('每来源页面及岗位上限均为1—20')
    try:print(json.dumps(run(args),ensure_ascii=False,indent=2))
    except Exception as e:write_status(state='failed',message=str(e));raise
