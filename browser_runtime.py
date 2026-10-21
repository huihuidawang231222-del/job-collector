"""Choose an available Chromium browser with a separate collector profile."""
import os
from pathlib import Path


def browser_config(chromium):
    if Path(chromium.executable_path).is_file():
        return 'Chromium', {}, 'browser'
    roots = [os.environ.get(name) for name in ['PROGRAMFILES(X86)', 'PROGRAMFILES', 'LOCALAPPDATA']]
    for name, channel, relative in [
        ('Microsoft Edge', 'msedge', 'Microsoft/Edge/Application/msedge.exe'),
        ('Google Chrome', 'chrome', 'Google/Chrome/Application/chrome.exe'),
    ]:
        if any(root and (Path(root) / relative).is_file() for root in roots):
            return name, {'channel': channel}, 'browser-' + channel
    raise RuntimeError('未找到采集浏览器。请先双击项目中的安装.bat，完成浏览器下载后重新开始采集。')


if __name__ == '__main__':
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        try:
            name, _, _ = browser_config(playwright.chromium)
            print('Available collector browser:', name)
        except RuntimeError:
            print('No collector browser found; bundled Chromium must be installed.')
            raise SystemExit(1)
