"""Keyword search, bounded automatic scrolling/pagination and detail capture."""
import argparse,json,time,os
from browser_runtime import browser_config
from urllib.parse import urlencode,urlsplit
from core import ROOT,save
from collection_safety import CollectionGuard, SafetyStop, single_collector
DATA=ROOT/'data'
STATUS=DATA/'task.json'; STOP=DATA/'stop'; RESUME=DATA/'resume'
PLATFORMS={
 'BOSS直聘':{'host':'zhipin.com','url':'https://www.zhipin.com/web/geek/job?','city_key':'city','keyword':'query','city':'101280100','jd':'.job-sec-text','industry':'.company-industry'},
 '猎聘':{'host':'liepin.com','url':'https://www.liepin.com/zhaopin/?','city_key':'dq','keyword':'key','city':'050020','jd':'.job-intro-container .paragraph, .job-description','industry':'.company-industry'},
 '智联招聘':{'host':'zhaopin.com','url':'https://sou.zhaopin.com/?','city_key':'jl','keyword':'kw','city':'763','jd':'.describtion__detail-content, .job-detail','industry':'.company__industry'},
 '前程无忧':{'host':'51job.com','url':'https://we.51job.com/pc/search?','city_key':'jobArea','keyword':'keyword','city':'030200','jd':'.job_msg, .job-detail','industry':'.com_tag .industry'}
}
def status(**kw):
    DATA.mkdir(exist_ok=True)
    old={}
    if STATUS.exists():
        try:old=json.loads(STATUS.read_text(encoding='utf-8'))
        except (ValueError,OSError):pass
    old.update(kw);old['updated_at']=time.strftime('%Y-%m-%d %H:%M:%S')
    tmp=DATA/'task.tmp';tmp.write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(STATUS)
def stopped():return STOP.exists()
def pause(reason,guard=None):
    RESUME.unlink(missing_ok=True);status(state='paused',message=reason+'；处理后在管理界面点击继续。')
    while not stopped():
        if guard:guard.checkpoint()
        if RESUME.exists():RESUME.unlink();status(state='running',message='继续采集');return True
        time.sleep(.5)
    return False
def blocked(page):
    if any(x in page.url.lower() for x in ['/login','/passport','/security-check','/web/user/','captchapage','/captcha']):return True
    if any(x in page.title().lower() for x in ['滑动验证','安全中心','security verification']):return True
    body=page.locator('body').inner_text(timeout=10000)
    return any(x in body for x in ['请完成安全验证','拖动滑块完成验证','访问过于频繁','验证你是真人','请先登录','行为异常','请按住滑块','请进行安全验证','正在验证连接安全性','请勾选下方复选框','Verifying the safety of the connection'])
def allowed(url,host):
    u=urlsplit(url);return u.scheme in ('http','https') and (u.hostname==host or (u.hostname or '').endswith('.'+host))
def next_page(page,guard=None):
    for selector in ['a[rel="next"]','button[aria-label="下一页"]','.ui-icon-arrow-right','.btn-next','a:has-text("下一页")','button:has-text("下一页")']:
        for node in page.locator(selector).all():
            if node.is_visible() and node.is_enabled() and node.get_attribute('aria-disabled')!='true' and 'disabled' not in (node.get_attribute('class') or ''):
                if guard:guard.before('next_page',page.url)
                node.click(timeout=10000);page.wait_for_timeout(2500);return True
    return False

def capture_inline(page,row,with_details):
    """Read the selected public sidebar; never read login-clipped JD text."""
    page.locator('.job-list-panel .job-card').nth(int(row['list_index'])).click(timeout=10000)
    page.wait_for_function('(title) => document.querySelector(".job-detail-summary__title-text")?.innerText.trim() === title',arg=row['title'],timeout=10000)
    panel=page.locator('.job-detail-panel')
    link=panel.locator('a[href*="/jobdetail/"]').first
    if link.count():row['url']=link.get_attribute('href') or ''
    if not with_details:return
    if any(node.is_visible() for node in panel.locator('.job-description__content--guest-clamp, .job-detail-login-gate').all()):
        row['jd_access']='需登录查看完整JD'
        return
    node=panel.locator('.job-description__content').first
    if node.count() and node.is_visible():row['jd']=node.inner_text()

def collect(page,cfg,keyword,limit,rounds,with_details,emit=save,guard=None):
    script=(ROOT/'extract.js').read_text(encoding='utf-8'); seen=set();stale=0
    count=0;details=page.context.new_page() if with_details else None
    try:
        for turn in range(rounds):
            if guard:guard.checkpoint()
            if stopped():return count,'用户停止'
            if blocked(page):
                if guard:guard.challenge()
                if not pause('招聘平台要求登录或验证',guard):return count,'用户停止'
                if blocked(page):return count,'登录或验证仍未完成'
            if guard:guard.before('capture',page.url)
            result=page.evaluate(script);fresh=[]
            for r in result['rows']:
                if not r.get('title'):continue
                key=r.get('url') or '|'.join(str(r.get(k,'')) for k in ['title','company','location'])
                if key in seen:continue
                seen.add(key);fresh.append(r)
            stale=0 if fresh else stale+1
            for r in fresh[:max(0,limit-count)]:
                if stopped():return count,'用户停止'
                saved_early=False
                r['search_keyword']=keyword
                if r.get('capture_layout')=='zhaopin-split':
                    try:
                        if guard:guard.before('select_card',page.url)
                        capture_inline(page,r,with_details)
                    except SafetyStop:raise
                    except Exception as e:r['detail_error']=str(e)[:300]
                elif details and allowed(r.get('url',''),cfg['host']):
                    try:
                        if guard:guard.before('detail',r['url'])
                        response=details.goto(r['url'],wait_until='domcontentloaded',timeout=30000)
                        if guard:guard.response(response)
                        details.wait_for_timeout(2000)
                        if blocked(details):
                            r['jd_access']='需人工登录或安全验证'
                            emit([r])
                            count+=1;saved_early=True
                            status(state='running',current_count=count)
                            if guard:guard.challenge()
                            if not pause('详情页要求登录或验证',guard):return count,'用户停止'
                            if blocked(details):return count,'详情页验证仍未完成'
                            r['jd_access']='已通过人工验证'
                        node=details.locator(cfg['jd']).first
                        if node.count() and node.is_visible():r['jd']=node.inner_text()
                        industry=details.locator(cfg['industry']).first
                        if industry.count() and industry.is_visible():r['industry_raw']=industry.inner_text()
                    except SafetyStop:raise
                    except Exception as e:
                        r['detail_error']=str(e)[:300]
                        if guard:guard.trip('详情页连接或读取失败',900)
                emit([r])
                if not saved_early:count+=1
                status(state='running',current_count=count,message=f'已保存 {count} 条，本轮 {turn+1}/{rounds}')
            if count>=limit:return count,'达到数量上限'
            if stale>=2:
                if next_page(page,guard):stale=0
                else:return count,'页面不再出现新岗位，或未识别到下一页'
            else:
                if guard:guard.before('scroll',page.url)
                page.evaluate('''() => {window.scrollTo(0,document.body.scrollHeight); for (const n of document.querySelectorAll('main, [class*="list"], [class*="scroll"]')) if(n.scrollHeight>n.clientHeight+200) n.scrollTop=n.scrollHeight;}''')
                page.wait_for_timeout(2500)
        return count,'达到加载轮数上限'
    finally:
        if details:details.close()

@single_collector(DATA)
def run(args):
    from playwright.sync_api import sync_playwright
    DATA.mkdir(exist_ok=True)
    try:
        STOP.unlink(missing_ok=True);RESUME.unlink(missing_ok=True)
        status(state='running',message='启动浏览器',results=[],pid=os.getpid())
        reports=[]
        with sync_playwright() as p:
            browser_name,options,profile=browser_config(p.chromium)
            status(browser=browser_name,message='启动采集浏览器：'+browser_name)
            ctx=p.chromium.launch_persistent_context(str(DATA/profile),headless=False,**options)
            try:
                for name in args.platforms:
                    if stopped():break
                    cfg=PLATFORMS[name];guard=CollectionGuard(cfg['host'],DATA);page=ctx.new_page();status(platform=name,current_count=0)
                    ctx.on('response',guard.observe)
                    try:
                        query={cfg['keyword']:args.keyword,cfg['city_key']:args.city_code or cfg['city']}
                        target=cfg['url']+urlencode(query)
                        guard.before('search',target)
                        response=page.goto(target,wait_until='domcontentloaded',timeout=45000)
                        guard.response(response)
                        page.wait_for_timeout(3000)
                        n,reason=collect(page,cfg,args.keyword,args.limit,args.rounds,not args.no_details,guard=guard)
                        reports.append(dict(platform=name,count=n,reason=reason))
                    except Exception as e:
                        if not isinstance(e,SafetyStop):
                            try:guard.trip('页面连接或采集失败',900)
                            except SafetyStop as stopped_error:e=stopped_error
                        guard.audit('stopped',reason=str(e))
                        current=json.loads(STATUS.read_text(encoding='utf-8')).get('current_count',0)
                        reports.append(dict(platform=name,count=current,reason=str(e),protected=isinstance(e,SafetyStop)))
                    finally:
                        ctx.remove_listener('response',guard.observe)
                        page.close()
                    status(results=reports)
            finally:ctx.close()
        protected=bool(reports) and all(r.get('protected') and not r['count'] for r in reports)
        state='stopped' if stopped() else 'protected' if protected else 'finished'
        status(state=state,message='访问保护已拦截自动采集，请查看规则与原因' if protected else '任务结束，查看各平台采集结果',results=reports)
    except Exception as e:status(state='failed',message=str(e));raise
if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--keyword',required=True);parser.add_argument('--platforms',nargs='+',choices=list(PLATFORMS),default=list(PLATFORMS))
    parser.add_argument('--limit',type=int,default=10);parser.add_argument('--rounds',type=int,default=5)
    parser.add_argument('--city-code',default='',help='单平台城市代码；默认各平台广州代码')
    parser.add_argument('--no-details',action='store_true');args=parser.parse_args()
    if not args.keyword.strip() or not 1<=args.limit<=20 or not 1<=args.rounds<=10:parser.error('关键词不能为空；保护模式数量1-20，轮数1-10')
    if args.city_code and len(args.platforms)!=1:parser.error('自定义城市代码只允许单平台任务')
    run(args)
