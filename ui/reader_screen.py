# -*- coding: utf-8 -*-
"""阅读窗口（Kivy）：以「阅读小说」风格呈现 txt / md 文本文件。
支持平板上下滑动、回顶部 / 回底部、多种阅读风格与独立字号调节。
打开方式：聊天顶栏「阅读」或「文件」按钮。文件可来自：
  - 项目文件列表（当前会话项目文件夹里 AI 用 %%FILE: 保存的文件）
  - 文件选择器
  - 手动输入路径
额外能力：全屏（沉浸阅读）、修改（编辑并保存回原文件）。
"""
import os

from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.modalview import ModalView
from kivy.uix.filechooser import FileChooserListView
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle
from kivy.core.window import Window

from core import config
from core import session as session_mod
from ui import theme
from ui.theme import fs, READING_STYLE_LABELS

KV = """
<ReaderScreen>:
    orientation: 'vertical'
    canvas.before:
        Color:
            rgba: theme.RC('bg')
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:  # 顶栏
        id: top_bar
        size_hint_y: None
        height: dp(48)
        padding: dp(4)
        spacing: dp(3)
        canvas.before:
            Color:
                rgba: theme.RC('panel')
            Rectangle:
                pos: self.pos
                size: self.size
        Button:
            text: '← 聊天'
            size_hint_x: None
            width: dp(70)
            background_color: theme.RC('panel2')
            background_normal: ''
            color: theme.RC('text')
            font_size: fs(14)
            on_press: root.app.go_chat()
        Label:
            id: lbl_title
            text: '阅读窗口'
            color: theme.RC('text')
            font_size: fs(14)
            halign: 'left'
            text_size: self.size
            valign: 'middle'
            size_hint_x: 1
        Spinner:
            id: style_spin
            text: '米黄纸'
            size_hint_x: None
            width: dp(86)
            background_color: theme.RC('panel2')
            background_normal: ''
            color: theme.RC('text')
            font_size: fs(12)
            on_text: root.on_style_spin(self.text)
        Button:
            text: 'A-'
            size_hint_x: None
            width: dp(44)
            background_color: theme.RC('panel4')
            background_normal: ''
            color: theme.RC('text')
            font_size: fs(14)
            on_press: root.font_dec()
        Button:
            text: 'A+'
            size_hint_x: None
            width: dp(44)
            background_color: theme.RC('panel4')
            background_normal: ''
            color: theme.RC('text')
            font_size: fs(14)
            on_press: root.font_inc()
    BoxLayout:  # 路径输入条（便于手机/平板直接填路径 + 选文件 + 项目文件）
        id: path_bar
        size_hint_y: None
        height: dp(40)
        padding: dp(4)
        spacing: dp(4)
        canvas.before:
            Color:
                rgba: theme.RC('panel')
            Rectangle:
                pos: self.pos
                size: self.size
        TextInput:
            id: path_in
            hint_text: '输入文件路径，如 /sdcard/小说/第1章.txt'
            background_color: theme.RC('panel2')
            foreground_color: theme.RC('text')
            hint_text_color: theme.RC('text_dim')
            font_size: fs(13)
            padding: dp(8), dp(4)
        Button:
            text: '打开路径'
            size_hint_x: None
            width: dp(80)
            background_color: theme.RC('accent')
            background_normal: ''
            color: (1,1,1,1)
            font_size: fs(13)
            on_press: root.open_path()
        Button:
            text: '选文件'
            size_hint_x: None
            width: dp(60)
            background_color: theme.RC('accent')
            background_normal: ''
            color: (1,1,1,1)
            font_size: fs(13)
            on_press: root.open_picker()
        Button:
            text: '项目文件'
            size_hint_x: None
            width: dp(72)
            background_color: theme.RC('panel4')
            background_normal: ''
            color: theme.RC('text')
            font_size: fs(13)
            on_press: root.open_project_files()
    FloatLayout:  # 正文（阅读 Label / 编辑 TextInput）+ 悬浮按钮
        ScrollView:
            id: read_sv
            bar_width: dp(6)
            scroll_type: ['bars', 'content']
            Label:
                id: content
                text: '点击「项目文件」查看当前会话里 AI 写出的文件，或点「选文件 / 打开路径」打开一本小说（txt / md）。\\n\\n支持平板上下滑动翻页、回顶部 / 回底部、多种阅读风格与字号调节，还可以「全屏」沉浸阅读、点「修改」直接编辑并保存。'
                color: theme.RC('text')
                font_size: fs(18)
                size_hint_y: None
                height: self.texture_size[1]
                text_size: (self.width - dp(24), None)
                halign: 'left'
                valign: 'top'
                padding: dp(12), dp(12)
        TextInput:
            id: editor
            text: ''
            background_color: theme.RC('panel2')
            foreground_color: theme.RC('text')
            font_size: fs(18)
            padding: dp(12), dp(12)
            size_hint: 1, 1
            pos_hint: {'x': 0, 'y': 0}
            opacity: 0
            disabled: True
        BoxLayout:  # 悬浮在右侧的竖排按钮：修改/保存 / 全屏 / 回顶 / 回底
            orientation: 'vertical'
            size_hint: None, None
            size: dp(50), dp(176)
            pos_hint: {'right': 0.99, 'bottom': 0.02}
            spacing: dp(4)
            Button:
                id: btn_edit
                text: '修改'
                background_color: theme.RC('accent')
                background_normal: ''
                color: (1,1,1,1)
                font_size: fs(12)
                on_press: root.toggle_edit()
            Button:
                id: btn_fs
                text: '全屏'
                background_color: theme.RC('panel4')
                background_normal: ''
                color: theme.RC('text')
                font_size: fs(12)
                on_press: root.toggle_fullscreen()
            Button:
                text: '回顶部'
                background_color: theme.RC('accent')
                background_normal: ''
                color: (1,1,1,1)
                font_size: fs(12)
                on_press: root.scroll_to_top()
            Button:
                text: '回底部'
                background_color: theme.RC('panel4')
                background_normal: ''
                color: theme.RC('text')
                font_size: fs(12)
                on_press: root.scroll_to_bottom()
"""


class ReaderScreen(BoxLayout):
    def __init__(self, app=None, **kw):
        super().__init__(**kw)
        self.app = app
        self._guard = False
        self._build_done = False
        self._file_path = None      # 当前打开的文件（用于保存）
        self._editing = False       # 是否处于编辑模式
        self._fullscreen = False    # 是否全屏

    # 由 main.py 在 add_widget 后调用
    def on_parent(self, *a):
        if self._build_done:
            return
        self._build_done = True
        # 初始化风格 Spinner / 字号（用 _guard 防止初始化赋值触发 on_style_spin 重建死循环）
        self._guard = True
        self.ids.style_spin.text = theme.reading_style_label()
        self._guard = False
        self.reader_font = getattr(self.app, "reader_font", 18)
        self.ids.content.font_size = fs(self.reader_font)
        self.ids.editor.font_size = fs(self.reader_font)
        # 文本换行随宽度自适应
        self.ids.content.bind(size=self._wrap)
        self._show_read()
        # 若之前打开过文件，重建后自动重新载入（换风格不丢书）
        path = getattr(self.app, "reader_path", None)
        if path and os.path.isfile(path):
            self.load_file(path, silent=True)

    def _wrap(self, *a):
        lab = self.ids.content
        lab.text_size = (lab.width - dp(24), None)

    # ---- 打开文件 ----
    def open_picker(self, *a):
        self.exit_fullscreen()
        mv = ModalView(size_hint=(0.96, 0.9))
        fc = FileChooserListView(path=self._start_dir(),
                                 filters=["*.txt", "*.md", "*.text", "*.markdown"])
        fc.bind(on_submit=lambda inst, sel, *x: (mv.dismiss(), self.load_file(sel[0]) if sel else None))
        mv.add_widget(fc)
        mv.open()

    def open_path(self, *a):
        p = self.ids.path_in.text.strip()
        if not p:
            return
        if os.path.isfile(p):
            self.load_file(p)
        else:
            self.ids.content.text = f"[!] 找不到文件：{p}"

    def _start_dir(self):
        if config.ANDROID:
            return str(config.DATA_DIR)
        return os.path.expanduser("~")

    def load_file(self, path, silent=False):
        try:
            # 先尝试 UTF-8，失败再退到 GBK（Windows 记事本常见编码）
            text = None
            for enc in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
                try:
                    with open(path, "r", encoding=enc) as f:
                        text = f.read()
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            if text is None:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            self._file_path = path
            self._show_read()
            self.ids.content.text = text or "（空文件）"
            self.ids.editor.text = text or ""
            self.ids.lbl_title.text = os.path.basename(path)
            self.ids.path_in.text = path
            if self.app is not None:
                self.app.reader_path = path
            if not silent:
                self.scroll_to_top()
        except Exception as e:
            self._file_path = path
            self._show_read()
            self.ids.content.text = f"[!] 打开失败：{e}"

    # ---- 项目文件（当前会话项目文件夹）----
    def open_project_files(self, *a):
        self.exit_fullscreen()
        sid = None
        if self.app is not None and getattr(self.app, "chat", None) is not None:
            sid = self.app.chat.current_sid
        if not sid:
            self.ids.content.text = "（还没有会话：请先在聊天里新建或选择一个会话，AI 写出的文件会保存在这里）"
            self.ids.lbl_title.text = "项目文件"
            self._file_path = None
            return
        folder = session_mod.get_session_folder(sid)
        files = []
        try:
            for root, _dirs, fnames in os.walk(folder):
                for fn in fnames:
                    if fn in ("messages.json", "chat.md"):
                        continue
                    full = os.path.join(root, fn)
                    rel = os.path.relpath(full, folder)
                    files.append((rel, full))
        except Exception:
            pass
        files.sort(key=lambda x: x[0])

        mv = ModalView(size_hint=(0.95, 0.9))
        bl = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        bl.add_widget(Label(
            text="项目文件（点击打开，支持阅读 / 全屏 / 修改）",
            color=theme.RC("text"), size_hint_y=None, height=dp(34), font_size=fs(14)))
        sv = ScrollView(bar_width=dp(6))
        grid = GridLayout(cols=1, spacing=dp(4), size_hint_y=None,
                          height=dp(10), padding=dp(4))
        grid.bind(minimum_height=grid.setter("height"))
        if not files:
            grid.add_widget(Label(
                text="（这个会话还没有文件，让 AI 用 %%FILE: 生成，或自己保存文件到这里）",
                color=theme.RC("text_dim"), size_hint_y=None, height=dp(48),
                font_size=fs(13), halign="left", text_size=(Window.width * 0.82, None)))
        for rel, full in files:
            b = Button(text=rel, background_color=theme.RC("panel2"),
                       background_normal="", color=theme.RC("text"),
                       halign="left", text_size=(Window.width * 0.82, None),
                       font_size=fs(14), size_hint_y=None, height=dp(40))
            b.bind(on_press=lambda inst, f=full: (mv.dismiss(), self.load_file(f)))
            grid.add_widget(b)
        sv.add_widget(grid)
        bl.add_widget(sv)
        close = Button(text="关闭", size_hint_y=None, height=dp(40),
                       background_color=theme.RC("panel4"), background_normal="",
                       color=theme.RC("text"))
        close.bind(on_press=mv.dismiss)
        bl.add_widget(close)
        mv.add_widget(bl)
        mv.open()

    # ---- 风格 / 字号 ----
    def on_style_spin(self, label):
        if getattr(self, "_guard", False):
            return
        key = None
        for k, v in READING_STYLE_LABELS.items():
            if v == label:
                key = k
                break
        if not key:
            return
        theme.set_reading_style(key)
        try:
            from core import settings as settings_mod
            settings_mod.update_settings({"ui": {"reading_style": key}})
        except Exception:
            pass
        if self.app is not None:
            self.app.apply_theme_to_all()      # 重建聊天/阅读窗口，统一换肤
            self.app.sm.current = "reader"     # 换肤后停留在本窗口看效果

    def font_inc(self, *a):
        self.reader_font = min(48, (self.reader_font or 18) + 2)
        self.ids.content.font_size = fs(self.reader_font)
        self.ids.editor.font_size = fs(self.reader_font)
        if self.app is not None:
            self.app.reader_font = self.reader_font

    def font_dec(self, *a):
        self.reader_font = max(10, (self.reader_font or 18) - 2)
        self.ids.content.font_size = fs(self.reader_font)
        self.ids.editor.font_size = fs(self.reader_font)
        if self.app is not None:
            self.app.reader_font = self.reader_font

    # ---- 编辑 / 保存 ----
    def toggle_edit(self, *a):
        if not self._editing:
            if not self._file_path:
                self.ids.lbl_title.text = "请先打开一个文件再修改"
                return
            self.exit_fullscreen()
            self._editing = True
            self.ids.editor.text = self.ids.content.text
            self.ids.read_sv.opacity = 0
            self.ids.read_sv.disabled = True
            self.ids.editor.opacity = 1
            self.ids.editor.disabled = False
            self.ids.btn_edit.text = "保存"
            Clock.schedule_once(lambda dt: self.ids.editor.focus(True), 0.1)
        else:
            self.save_edit()

    def save_edit(self, *a):
        if not self._file_path:
            self.ids.lbl_title.text = "未打开文件，无法保存"
            return
        try:
            with open(self._file_path, "w", encoding="utf-8") as f:
                f.write(self.ids.editor.text)
            self._show_read()
            self.ids.content.text = self.ids.editor.text
            self.ids.lbl_title.text = "已保存：" + os.path.basename(self._file_path)
        except Exception as e:
            self.ids.lbl_title.text = f"[!] 保存失败：{e}"

    def _show_read(self):
        self._editing = False
        self.ids.editor.opacity = 0
        self.ids.editor.disabled = True
        self.ids.read_sv.opacity = 1
        self.ids.read_sv.disabled = False
        self.ids.btn_edit.text = "修改"

    # ---- 全屏（沉浸阅读）----
    def toggle_fullscreen(self, *a):
        self._fullscreen = not self._fullscreen
        try:
            Window.fullscreen = bool(self._fullscreen)
        except Exception:
            pass
        tb = self.ids.top_bar
        pb = self.ids.path_bar
        if self._fullscreen:
            self._bar_h = (tb.height, pb.height)
            tb.height = 0; tb.opacity = 0; tb.size_hint_y = None; tb.disabled = True
            pb.height = 0; pb.opacity = 0; pb.size_hint_y = None; pb.disabled = True
            self.ids.btn_fs.text = "退出"
        else:
            if hasattr(self, "_bar_h"):
                tb.height = self._bar_h[0]
                pb.height = self._bar_h[1]
            tb.opacity = 1; tb.disabled = False
            pb.opacity = 1; pb.disabled = False
            self.ids.btn_fs.text = "全屏"

    def exit_fullscreen(self, *a):
        if getattr(self, "_fullscreen", False):
            self.toggle_fullscreen()

    # ---- 回顶部 / 回底部 ----
    def scroll_to_top(self, *a):
        try:
            if self._editing:
                self.ids.editor.scroll_y = 1
            else:
                self.ids.read_sv.scroll_y = 1
        except Exception:
            pass

    def scroll_to_bottom(self, *a):
        try:
            if self._editing:
                self.ids.editor.scroll_y = 0
            else:
                self.ids.read_sv.scroll_y = 0
        except Exception:
            pass
