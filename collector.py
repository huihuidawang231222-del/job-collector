"""Interactive collector: owns Playwright on one thread; never auto-paginates."""
from pathlib import Path
from playwright.sync_api import sync_playwright
from core import ROOT, save
from browser_runtime import browser_config
from collection_safety import CollectionGuard, single_collector
from auto_collect import PLATFORMS, allowed, blocked
from urllib.parse import urlsplit

@single_collector(ROOT/'data')
def main():
    with sync_playwright() as p:
        name,options,profile=browser_config(p.chromium)
        print('采集浏览器：',name)
        context=p.chromium.launch_persistent_context(str(ROOT/'data'/profile),headless=False,**options)
        page=context.pages[0] if context.pages else context.new_page()
        page.goto('https://www.zhipin.com/',wait_until='domcontentloaded',timeout=60000)
        script=(ROOT/'extract.js').read_text(encoding='utf-8')
        print('在浏览器正常登录、搜索。需要采集时回到此窗口输入 c；输入 q 退出。')
        while True:
            cmd=input('c 采集当前页面 / q 退出 > ').strip().lower()
            if cmd=='q': break
            if cmd!='c': continue
            pages=[x for x in context.pages if not x.is_closed()]
            for i,x in enumerate(pages): print(i,x.url)
            try:
                index=int(input('输入需要采集的标签页编号：') or '0')
                if index<0 or index>=len(pages): raise ValueError('标签页编号超出范围')
                page=pages[index]
                body=page.locator('body').inner_text()
                if blocked(page):
                    print('页面处于验证或访问限制状态，请手动处理后再采集。'); continue
                host=next((cfg['host'] for cfg in PLATFORMS.values() if allowed(page.url,cfg['host'])),urlsplit(page.url).hostname)
                guard=CollectionGuard(host,ROOT/'data')
                guard.before('manual_capture',page.url)
                result=page.evaluate(script)
                if not result['rows']:
                    print('未识别到岗位。可能尚未加载、页面需登录，或适配规则需要更新。可改用CSV导入。'); continue
                a,u,s=save(result['rows'])
                print(f'新增 {a} 条，更新 {u} 条，跳过 {s} 条。请在管理界面点击刷新。')
            except (ValueError,IndexError) as e: print('输入错误：',e)
            except Exception as e: print('采集失败：',e)
        context.close()
if __name__=='__main__':
    try: main()
    except Exception as e: print('启动失败：',e); input('按回车退出')
