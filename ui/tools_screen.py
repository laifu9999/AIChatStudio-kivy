# -*- coding: utf-8 -*-
"""工具面板（Kivy）：项目 / 自动化 / 爬取 三个标签页。"""
import os
import re
import threading
from kivy.clock import Clock, mainthread
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.modalview import ModalView
from kivy.uix.gridlayout import GridLayout
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle, RoundedRectangle

from core import session as session_mod
from core import settings as settings_mod
from modules import automation
from modules import web_scraper
from ui import theme
from ui.theme import fs

KV = """
<ToolsScreen>:
    orientation: 'vertical'
    canvas.before:
        Color:
            rgba: theme.C('bg')
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        size_hint_y: None
        height: dp(48)
        canvas.before:
            Color:
                rgba: theme.C('panel')
            Rectangle:
                pos: self.pos
                size: self.size
        Button:
            text: '← 返回'
            size_hint_x: None
            width: dp(90)
            background_color: theme.C('panel2')
            background_normal: ''
            color: theme.C('text')
            font_size: fs(15)
            on_press: root.app.go_chat()
        Label:
            text: '工具'
            color: theme.C('text')
            font_size: fs(16)
    BoxLayout:
        id: tabs
        size_hint_y: None
        height: dp(42)
        spacing: dp(4)
        padding: dp(4)
        Button:
            id: t0
            text: '项目'
            background_color: theme.C('panel2')
            background_normal: ''
            color: theme.C('text')
            font_size: fs(14)
            on_press: root.switch_tab(0)
        Button:
            id: t1
            text: '自动化'
            background_color: theme.C('panel2')
            background_normal: ''
            color: theme.C('text')
            font_size: fs(14)
            on_press: root.switch_tab(1)
        Button:
            id: t2
            text: '爬取'
            background_color: theme.C('panel2')
            background_normal: ''
            color: theme.C('text')
            font_size: fs(14)
            on_press: root.switch_tab(2)
    BoxLayout:
        id: body
"""


class ToolsScreen(BoxLayout):
    def __init__(self, app=None, **kw):
        super().__init__(**kw)
        self.app = app
        self.tab = 0
        self._last_crawl = None  # 抓取结果缓存，防止未抓取就点"保存到文件"崩溃
        self._build_body()

    def switch_tab(self, idx):
        self.tab = idx
        self._build_body()

    def _build_body(self):
        self.ids.body.clear_widgets()
        if self.tab == 0:
            self._build_project()
        elif self.tab == 1:
            self._build_auto()
        else:
            self._build_crawl()

    # ---------------- 项目 ----------------
    def _build_project(self):
        root = self._cur_folder()
        box = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        info = Label(text=f"项目目录：\n{root or '(无会话)'}", color=theme.C('text_dim'),
                     size_hint_y=None, height=dp(40), halign="left", font_size=fs(13),
                     text_size=(self.width, None))
        info.bind(size=lambda *a: setattr(info, 'text_size', (info.width, None)))
        box.add_widget(info)
        sv = ScrollView(bar_width=dp(6))
        grid = GridLayout(cols=1, spacing=dp(3), size_hint_y=None, height=dp(10), padding=dp(4))
        grid.bind(minimum_height=grid.setter("height"))
        if root and os.path.isdir(root):
            for path in self._walk(root):
                rel = os.path.relpath(path, root)
                b = Button(text=rel, size_hint_y=None, height=dp(38),
                           halign="left", text_size=(self.width - dp(20), None),
                           background_color=theme.C('panel2'), background_normal='',
                           color=theme.C('text'), font_size=fs(13))
                b.bind(on_press=lambda inst, p=path: self._view_file(p))
                grid.add_widget(b)
        sv.add_widget(grid)
        box.add_widget(sv)
        self.ids.body.add_widget(box)

    def _walk(self, root):
        out = []
        for dp_, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
            for fn in sorted(files):
                out.append(os.path.join(dp_, fn))
        return sorted(out)

    def _view_file(self, path):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(40000)
        except Exception as e:
            content = f"无法读取：{e}"
        mv = ModalView(size_hint=(0.92, 0.85))
        bl = BoxLayout(orientation="vertical")
        bl.add_widget(Label(text=os.path.basename(path), color=theme.C('text'),
                           size_hint_y=None, height=dp(36)))
        ta = TextInput(text=content, readonly=True, background_color=theme.C('panel'),
                       foreground_color=theme.C('text'), font_size=fs(13))
        bl.add_widget(ta)
        mv.add_widget(bl)
        mv.open()

    def _cur_folder(self):
        if self.app and self.app.chat.current_sid:
            return str(session_mod.get_session_folder(self.app.chat.current_sid))
        return None

    # ---------------- 自动化（Python 脚本运行器） ----------------
    def _build_auto(self):
        box = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        box.add_widget(Label(text="Python 自动化脚本（电脑/手机通用，点运行在后台执行）",
                             color=theme.C('text_dim'), size_hint_y=None, height=dp(24),
                             halign="left", font_size=fs(13), text_size=(self.width, None)))
        self.auto_in = TextInput(hint_text="在此写 Python 代码，例如：\nimport os\nprint(os.listdir('.'))",
                                 background_color=theme.C('panel2'), foreground_color=theme.C('text'),
                                 font_size=fs(13))
        box.add_widget(self.auto_in)
        run = Button(text="运行", size_hint_y=None, height=dp(42),
                     background_color=theme.C('accent'), background_normal='',
                     color=(1,1,1,1), font_size=fs(14))
        run.bind(on_press=self._run_auto)
        box.add_widget(run)
        self.auto_out = Label(text="", color=theme.C('text'), size_hint_y=None,
                              halign="left", valign="top", font_size=fs(13),
                              text_size=(self.width, None))
        self.auto_out.bind(size=lambda *a: setattr(self.auto_out, 'text_size', (self.auto_out.width, None)))
        sv = ScrollView(bar_width=dp(6))
        sv.add_widget(self.auto_out)
        box.add_widget(sv)
        self.ids.body.add_widget(box)

    def _run_auto(self, *a):
        code = self.auto_in.text
        if not code.strip():
            return
        self.auto_out.text = "运行中…"
        cwd = self._cur_folder()
        cfg = settings_mod.load_settings().get("automation", {})
        def on_log(line):
            pass
        logs = []
        def worker():
            res = automation.run_script(code, cfg=cfg, cwd=cwd, on_log=lambda l: logs.append(l))
            Clock.schedule_once(lambda dt: setattr(self.auto_out, "text", "\n".join(logs)))
        threading.Thread(target=worker, daemon=True).start()

    # ---------------- 爬取 ----------------
    def _build_crawl(self):
        box = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        self.url_in = TextInput(hint_text="输入网址 URL", background_color=theme.C('panel2'),
                                foreground_color=theme.C('text'), size_hint_y=None, height=dp(40))
        box.add_widget(self.url_in)
        self.re_in = TextInput(hint_text="正则（可选，用于提取内容）", background_color=theme.C('panel2'),
                               foreground_color=theme.C('text'), size_hint_y=None, height=dp(40))
        box.add_widget(self.re_in)
        row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        run = Button(text="抓取并提取", background_color=theme.C('accent'), background_normal='',
                     color=(1,1,1,1), font_size=fs(14))
        run.bind(on_press=self._crawl)
        self.save_cb = Button(text="保存到文件", background_color=theme.C('panel4'), background_normal='',
                              color=theme.C('text'), font_size=fs(14))
        self.save_cb.bind(on_press=self._save_crawl)
        row.add_widget(run); row.add_widget(self.save_cb)
        box.add_widget(row)
        self.crawl_out = Label(text="", color=theme.C('text'), size_hint_y=None,
                               halign="left", valign="top", font_size=fs(13),
                               text_size=(self.width, None))
        self.crawl_out.bind(size=lambda *a: setattr(self.crawl_out, 'text_size', (self.crawl_out.width, None)))
        sv = ScrollView(bar_width=dp(6))
        sv.add_widget(self.crawl_out)
        box.add_widget(sv)
        self.ids.body.add_widget(box)

    def _crawl(self, *a):
        url = self.url_in.text.strip()
        if not url:
            self.crawl_out.text = "请填写 URL"
            return
        pattern = self.re_in.text.strip()
        self.crawl_out.text = "抓取中…"
        self._last_crawl = (url, None)
        use_browser = False  # 移动端用纯 requests，避免 Chromium 体积
        def worker():
            try:
                html = web_scraper.fetch_html(url, use_browser=use_browser,
                                              headless=True, user_agent="")
                if pattern:
                    matches, err = web_scraper.extract(html, pattern, re.S | re.I)
                    if err:
                        result = f"正则错误：{err}"
                    else:
                        result = "\n".join(str(m) for m in matches[:200]) or "无匹配"
                else:
                    result = html[:4000]
                self._last_crawl = (url, result)
                Clock.schedule_once(lambda dt: setattr(self.crawl_out, "text", result))
            except Exception as e:
                Clock.schedule_once(lambda dt: setattr(self.crawl_out, "text", f"抓取失败：{e}"))
        threading.Thread(target=worker, daemon=True).start()

    def _save_crawl(self, *a):
        if not self._last_crawl or not self._last_crawl[1]:
            self.save_cb.text = "先抓取"
            return
        url, result = self._last_crawl
        if self.app and self.app.chat.current_sid:
            try:
                folder = str(session_mod.get_session_folder(self.app.chat.current_sid))
                with open(os.path.join(folder, "crawl_result.txt"), "w", encoding="utf-8") as f:
                    f.write(f"# {url}\n\n{result}\n")
                session_mod.append_message(self.app.chat.current_sid, "user", f"[爬取] {url}")
                self.save_cb.text = "[OK] 已保存"
            except Exception as e:
                self.save_cb.text = f"失败：{e}"
        else:
            self.save_cb.text = "无会话"
