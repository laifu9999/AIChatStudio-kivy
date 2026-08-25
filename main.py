# -*- coding: utf-8 -*-
"""AIChatStudio —— Kivy 跨平台版入口（Windows / Linux / Android）。

与桌面 PyQt5 版共用同一套核心逻辑（core/、modules/），UI 用 Kivy 重写，
打包 APK 后在手机上与电脑功能一致：聊天、按 %%FILE: 标记/代码块保存文件、
Python 执行、会话管理、设置、项目/自动化/爬取、投喂。
"""
import os
import threading
import platform

# ---------- 中文显示修复 ----------
# Kivy 默认字体 Roboto 不含中文字形，会导致界面中文显示成方块/乱码。
# 这里在应用启动前注入一个中文字体并设为全局默认字体（电脑 / 手机一致）。
def _setup_cjk_font():
    try:
        from kivy.core.text import LabelBase
        from kivy.config import Config
    except Exception:
        return None
    here = os.path.dirname(os.path.abspath(__file__))
    sysroot = os.environ.get("SystemRoot", r"C:\Windows")
    # 优先用内嵌字体（便携版 / Android 通用），其次用系统字体（Windows 渲染最佳）
    candidates = [
        os.path.join(here, "assets", "msyh.ttc"),
        os.path.join(here, "assets", "NotoSansSC.ttf"),
        os.path.join(sysroot, "Fonts", "msyh.ttc"),
        os.path.join(sysroot, "Fonts", "simsun.ttc"),
        os.path.join(sysroot, "Fonts", "simhei.ttf"),
    ]
    for p in candidates:
        if p and os.path.exists(p):
            try:
                # 关键：注册到 Kivy 默认家族名 "Roboto" 上，覆盖默认字体，
                # 这样所有 font_name="Roboto" 的控件（Label/TextInput/Button 等）都能显示中文
                LabelBase.register("Roboto", p)
                Config.set("kivy", "default_font", ["Roboto", p])
                return p
            except Exception:
                continue
    return None

_setup_cjk_font()

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.metrics import dp

from ui.chat_screen import ChatScreen, KV as CHAT_KV
from ui.settings_screen import SettingsScreen, KV as SETTINGS_KV
from ui.tools_screen import ToolsScreen, KV as TOOLS_KV
from ui.feed_screen import FeedScreen, KV as FEED_KV
from ui.reader_screen import ReaderScreen, KV as READER_KV
from ui import theme
# fs() 既被注入到 KV 的 global_idmap（供 .kv 规则使用），这里也建一个 Python 层别名，
# 避免 main.py 自身 Python 代码里误用未定义的裸 fs() 导致崩溃（此前 会话 抽屉因此闪退）。
fs = theme.fs
from core import session as session_mod
from core import settings as settings_mod

# 让 KV 规则能引用 theme 模块与全局字号函数 fs()（KV 求值命名空间默认只含 app/dp/sp/rgba 等）
from kivy.lang import builder as _kivy_builder
_kivy_builder.global_idmap["theme"] = theme
_kivy_builder.global_idmap["fs"] = theme.fs

# 加载所有界面的 kv 规则
for kv in (CHAT_KV, SETTINGS_KV, TOOLS_KV, FEED_KV, READER_KV):
    Builder.load_string(kv)


class AIChatStudioApp(App):
    def build(self):
        self.title = "AI Chat Studio"
        # 按已保存设置应用字号与阅读风格（必须在构建界面之前，使首屏即用正确样式）
        try:
            s = settings_mod.load_settings()
            ui = s.get("ui", {})
            theme.set_font_scale(ui.get("font_size", 16))
            theme.set_reading_style(ui.get("reading_style", "cream"))
            self.reader_font = ui.get("reader_font", 18)
        except Exception:
            self.reader_font = 18
        self.reader_path = None
        self._apply_window_bg()
        self.sm = ScreenManager()
        self._build_screens()
        return self.sm

    def _apply_window_bg(self):
        try:
            Window.clearcolor = theme.C("bg")
        except Exception:
            pass

    def _build_screens(self):
        # 移除旧屏
        self.sm.clear_widgets()
        self.chat = ChatScreen(app=self)
        self.settings_screen = SettingsScreen(app=self)
        self.tools = ToolsScreen(app=self)
        self.feed = FeedScreen(app=self)
        self.reader = ReaderScreen(app=self)
        for name, scr in (("chat", self.chat), ("settings", self.settings_screen),
                          ("tools", self.tools), ("feed", self.feed), ("reader", self.reader)):
            s = Screen(name=name)
            s.add_widget(scr)
            self.sm.add_widget(s)
        self.sm.current = "chat"

    # ---- 跳转 ----
    def go_chat(self):
        self.sm.current = "chat"

    def go_settings(self):
        self.settings_screen.settings = settings_mod.load_settings()
        self.sm.current = "settings"

    def go_tools(self):
        self.sm.current = "tools"

    def go_feed(self):
        self.sm.current = "feed"

    def go_reader(self):
        self.sm.current = "reader"

    def open_project_files(self):
        """跳到阅读窗口并弹出当前会话的项目文件列表。"""
        self.go_reader()
        Clock.schedule_once(lambda dt: self.reader.open_project_files(), 0.05)

    # ---- 主题切换：重建各屏（会话内容会从磁盘重新载入，不丢失）----
    def apply_theme_to_all(self):
        self._apply_window_bg()
        sid = self.chat.current_sid
        self._build_screens()
        if sid:
            self.chat.select_session(sid)
        self.sm.current = "chat"

    # ---- 会话抽屉 ----
    def open_sessions_drawer(self):
        mv = ModalView(size_hint=(0.85, 0.8))
        bl = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        bl.add_widget(Label(text="会话", color=theme.C("text"), size_hint_y=None,
                           height=dp(34), font_size=fs(16)))
        sv = ScrollView(bar_width=dp(6))
        grid = GridLayout(cols=1, spacing=dp(4), size_hint_y=None, height=dp(10), padding=dp(4))
        grid.bind(minimum_height=grid.setter("height"))

        def _new(*a):
            self.chat.new_session()
            mv.dismiss()

        new_b = Button(text="+ 新建会话", size_hint_y=None, height=dp(40),
                       background_color=theme.C("accent"), background_normal="",
                       color=(1, 1, 1, 1))
        new_b.bind(on_press=_new)
        grid.add_widget(new_b)

        sessions = session_mod.list_sessions()
        for s in sessions:
            row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(4))
            b = Button(text=s.get("name", s["id"]),
                       background_color=theme.C("panel2"), background_normal="",
                       color=theme.C("text"),
                       halign="left", text_size=(Window.width * 0.6, None))
            sid = s["id"]

            def _sel(*a, sid=sid):
                self.chat.select_session(sid)
                mv.dismiss()

            b.bind(on_press=_sel)
            del_b = Button(text="删", size_hint_x=None, width=dp(40),
                           background_color=theme.C("danger"), background_normal="",
                           color=(1, 1, 1, 1))

            def _del(*a, sid=sid):
                self.chat.delete_session(sid)

            del_b.bind(on_press=_del)
            row.add_widget(b); row.add_widget(del_b)
            grid.add_widget(row)

        sv.add_widget(grid)
        bl.add_widget(sv)
        close = Button(text="关闭", size_hint_y=None, height=dp(40),
                       background_color=theme.C("panel4"), background_normal="",
                       color=theme.C("text"))
        close.bind(on_press=mv.dismiss)
        bl.add_widget(close)
        mv.add_widget(bl)
        mv.open()


if __name__ == "__main__":
    AIChatStudioApp().run()
