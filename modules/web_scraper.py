"""网页爬取 + 正则提取模块。
支持 requests(静态) 与 playwright(动态/浏览器自动化)。权限由 settings.permissions.browser 控制。
正则提取结果可返回文本（输出到会话）或保存为文档。
"""
import re
import threading

try:
    import requests
    _HAS_REQUESTS = True
except Exception:
    _HAS_REQUESTS = False

try:
    from playwright.sync_api import sync_playwright
    _HAS_PLAYWRIGHT = True
except Exception:
    _HAS_PLAYWRIGHT = False


def available():
    return _HAS_REQUESTS


def fetch_html(url, use_browser=False, headless=True, user_agent=""):
    """获取页面 HTML。use_browser=True 走 playwright（可渲染 JS）。"""
    if use_browser:
        if not _HAS_PLAYWRIGHT:
            raise RuntimeError("未安装 playwright（pip install playwright && playwright install chromium）")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page(user_agent=user_agent or None)
            page.goto(url, timeout=30000)
            html = page.content()
            browser.close()
        return html
    if not _HAS_REQUESTS:
        raise RuntimeError("未安装 requests（pip install requests）")
    headers = {"User-Agent": user_agent or "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def extract(html, pattern, flags=0, group=0):
    """正则提取。返回匹配列表。"""
    try:
        compiled = re.compile(pattern, flags)
    except re.error as e:
        return [], f"正则错误: {e}"
    matches = compiled.findall(html)
    result = []
    for m in matches:
        if isinstance(m, tuple):
            result.append(m[group] if group < len(m) else m[0])
        else:
            result.append(m)
    return result, ""


def crawl_and_extract(url, pattern=None, use_browser=False, headless=True, user_agent="", flags=0):
    """爬取并（可选）正则提取。返回 {"html", "matches", "error"}。"""
    try:
        html = fetch_html(url, use_browser, headless, user_agent)
        matches = []
        err = ""
        if pattern:
            matches, err = extract(html, pattern, flags)
        return {"html": html, "matches": matches, "error": err, "ok": True}
    except Exception as e:
        return {"html": "", "matches": [], "error": str(e), "ok": False}
