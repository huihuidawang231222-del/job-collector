"""Keyword search, bounded automatic scrolling/pagination and detail capture."""
import argparse,json,time,os
from browser_runtime import browser_config
from urllib.parse import urlencode,urlsplit
from core import ROOT,save
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
def pause(reason):
    RESUME.unlink(missing_ok=True);status(state='paused',message=reason+'；处理后在管理界面点击继续。')
    while not stopped():
        if RESUME.exists():RESUME.unlink();status(state='running',message='继续采集');return True
        time.sleep(.5)
    return False
def blocked(page):
    body=page.locator('body').inner_text(timeout=10000)
    return any(x in body for x in ['请完成安全验证','拖动滑块完成验证','访问过于频繁','验证你是真人','请先登录']) or any(x in page.url for x in ['/login','/passport','/security-check'])
def allowed(url,host):
    u=urlsplit(url);return u.scheme in ('http','https') and (u.hostname==host or (u.hostname or '').endswith('.'+host))
def next_page(page):
    for selector in ['a[rel="next"]','button[aria-label="下一页"]','.ui-icon-arrow-right','.btn-next','a:has-text("下一页")','button:has-text("下一页")']:
        for node in page.locator(selector).all():
            if node.is_visible() and node.is_enabled() and node.get_attribute('aria-disabled')!='true' and 'disabled' not in (node.get_attribute('class') or ''):
                node.click(timeout=10000);page.wait_for_timeout(2500);return True
    return False

def collect(page,cfg,keyword,limit,rounds,with_details,emit=save):
    script=(ROOT/'extract.js').read_text(encoding='utf-8'); seen=set();stale=0
    count=0;details=page.context.new_page() if with_details else None
    try:
        for turn in range(rounds):
            if stopped():return count,'用户停止'
            if blocked(page):
                if not pause('招聘平台要求登录或验证'):return count,'用户停止'
                if blocked(page):return count,'登录或验证仍未完成'
            result=page.evaluate(script);fresh=[]
            for r in result['rows']:
                if not r.get('title'):continue
                key=r.get('url') or '|'.join(str(r.get(k,'')) for k in ['title','company','location'])
                if key in seen:continue
                seen.add(key);fresh.append(r)
            stale=0 if fresh else stale+1
            for r in fresh[:max(0,limit-count)]:
                if stopped():return count,'用户停止'
                r['search_keyword']=keyword
                if details and allowed(r.get('url',''),cfg['host']):
                    try:
                        details.goto(r['url'],wait_until='domcontentloaded',timeout=30000)
                        details.wait_for_timeout(2000)
                        if blocked(details):
                            emit([r])
                            if not pause('详情页要求登录或验证'):return count,'用户停止'
                            if blocked(details):return count,'详情页验证仍未完成'
                        node=details.locator(cfg['jd']).first
                        if node.count() and node.is_visible():r['jd']=node.inner_text()
                        industry=details.locator(cfg['industry']).first
                        if industry.count() and industry.is_visible():r['industry_raw']=industry.inner_text()
                    except Exception as e:r['detail_error']=str(e)[:300]
                emit([r]);count+=1
                status(state='running',current_count=count,message=f'已保存 {count} 条，本轮 {turn+1}/{rounds}')
            if count>=limit:return count,'达到数量上限'
            if stale>=2:
                if next_page(page):stale=0
                else:return count,'页面不再出现新岗位，或未识别到下一页'
            else:
                page.evaluate('''() => {window.scrollTo(0,document.body.scrollHeight); for (const n of document.querySelectorAll('main, [class*="list"], [class*="scroll"]')) if(n.scrollHeight>n.clientHeight+200) n.scrollTop=n.scrollHeight;}''')
                page.wait_for_timeout(2500)
        return count,'达到加载轮数上限'
    finally:
        if details:details.close()

def run(args):
    from playwright.sync_api import sync_playwright
    DATA.mkdir(exist_ok=True)
    # Exclusive lock avoids multiple tasks opening the same profile/database worker.
    try:fd=os.open(DATA/'worker.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:raise RuntimeError('采集进程锁已存在；确认旧进程已关闭后删除 data/worker.lock')
    os.close(fd)
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
                    cfg=PLATFORMS[name];page=ctx.new_page();status(platform=name,current_count=0)
                    try:
                        query={cfg['keyword']:args.keyword,cfg['city_key']:args.city_code or cfg['city']}
                        page.goto(cfg['url']+urlencode(query),wait_until='domcontentloaded',timeout=45000)
                        page.wait_for_timeout(3000)
                        n,reason=collect(page,cfg,args.keyword,args.limit,args.rounds,not args.no_details)
                        reports.append(dict(platform=name,count=n,reason=reason))
                    except Exception as e:reports.append(dict(platform=name,count=0,reason=str(e)))
                    finally:page.close()
                    status(results=reports)
            finally:ctx.close()
        status(state='stopped' if stopped() else 'finished',message='任务结束，查看各平台采集结果',results=reports)
    except Exception as e:status(state='failed',message=str(e));raise
    finally:(DATA/'worker.lock').unlink(missing_ok=True)
if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--keyword',required=True);parser.add_argument('--platforms',nargs='+',choices=list(PLATFORMS),default=list(PLATFORMS))
    parser.add_argument('--limit',type=int,default=100);parser.add_argument('--rounds',type=int,default=30)
    parser.add_argument('--city-code',default='',help='单平台城市代码；默认各平台广州代码')
    parser.add_argument('--no-details',action='store_true');args=parser.parse_args()
    if not args.keyword.strip() or not 1<=args.limit<=1000 or not 1<=args.rounds<=300:parser.error('关键词不能为空；数量1-1000，轮数1-300')
    if args.city_code and len(args.platforms)!=1:parser.error('自定义城市代码只允许单平台任务')
    run(args)
