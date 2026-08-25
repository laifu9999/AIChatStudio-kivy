# -*- coding: utf-8 -*-
"""投喂（Feed）界面（Kivy）。管理文字/文件投喂项与开关，纯 Python 跨平台。"""
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.metrics import dp
from core import settings as settings_mod
from core import content_feed
from ui import theme
from ui.theme import fs

KV = """
<FeedScreen>:
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
            text: '投喂'
            color: theme.C('text')
            font_size: fs(16)
    ScrollView:
        GridLayout:
            id: form
            cols: 1
            padding: dp(14)
            spacing: dp(10)
            size_hint_y: None
            height: self.minimum_height
"""


class FeedScreen(BoxLayout):
    def __init__(self, app=None, **kw):
        super().__init__(**kw)
        self.app = app
        self.settings = settings_mod.load_settings()
        self.manager = content_feed.ContentFeedManager()
        self.manager.apply_settings(self.settings.get("feed", {}))
        self._build_form()

    def _row(self, label_text, widget):
        box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(74), spacing=dp(4))
        lab = Label(text=label_text, color=theme.C('text_dim'), font_size=fs(12),
                    size_hint_y=None, height=dp(16), halign="left", text_size=(self.width, None))
        lab.bind(size=lambda *a: setattr(lab, 'text_size', (lab.width, None)))
        box.add_widget(lab); box.add_widget(widget)
        self.ids.form.add_widget(box)

    def _build_form(self):
        f = self.settings.get("feed", {})
        self.enable_cb = Button(
            text="[开] 投喂已开启" if f.get("enabled") else "投喂已关闭（点击开启）",
            size_hint_y=None, height=dp(42),
            background_color=theme.C('panel2'), background_normal='', color=theme.C('text'),
            font_size=fs(14))
        self.enable_cb.bind(on_press=self._toggle)
        self.ids.form.add_widget(self.enable_cb)

        self.text_in = TextInput(hint_text="输入要持续投喂的文字内容",
                                 background_color=theme.C('panel2'),
                                 foreground_color=theme.C('text'), size_hint_y=None, height=dp(60),
                                 font_size=fs(13))
        self._row("添加文字投喂", self.text_in)
        add_txt = Button(text="添加文字", size_hint_y=None, height=dp(38),
                         background_color=theme.C('panel4'), background_normal='',
                         color=theme.C('text'), font_size=fs(14))
        add_txt.bind(on_press=self._add_text)
        self.ids.form.add_widget(add_txt)

        self.first_in = TextInput(hint_text="首次注入文字（仅一次）",
                                  text=f.get("first_text", ""),
                                  background_color=theme.C('panel2'),
                                  foreground_color=theme.C('text'), size_hint_y=None, height=dp(42),
                                  font_size=fs(13))
        self._row("首次文字", self.first_in)
        self.repeat_in = TextInput(hint_text="每次重复注入文字",
                                   text=f.get("repeat_text", ""),
                                   background_color=theme.C('panel2'),
                                   foreground_color=theme.C('text'), size_hint_y=None, height=dp(42),
                                   font_size=fs(13))
        self._row("重复文字", self.repeat_in)

        save = Button(text="保存投喂设置", size_hint_y=None, height=dp(44),
                      background_color=theme.C('accent'), background_normal='',
                      color=(1,1,1,1), font_size=fs(15))
        save.bind(on_press=self._save)
        self.ids.form.add_widget(save)

        self.items_lbl = Label(text="投喂项：", color=theme.C('text_dim'), size_hint_y=None,
                               height=dp(20), halign="left", font_size=fs(13),
                               text_size=(self.width, None))
        self.items_lbl.bind(size=lambda *a: setattr(self.items_lbl, 'text_size', (self.items_lbl.width, None)))
        self.ids.form.add_widget(self.items_lbl)
        self._refresh_items()

    def _toggle(self, *a):
        f = self.settings.setdefault("feed", {})
        f["enabled"] = not f.get("enabled", False)
        self.enable_cb.text = "[开] 投喂已开启" if f["enabled"] else "投喂已关闭（点击开启）"
        self.manager.apply_settings(f)
        # 持久化开关状态，避免重启丢失
        settings_mod.update_settings({"feed": f})

    def _add_text(self, *a):
        txt = self.text_in.text.strip()
        if not txt:
            return
        self.manager.add_text(txt, name=f"text_{len(self.manager.items)+1}")
        self.text_in.text = ""
        self._refresh_items()

    def _refresh_items(self):
        items = getattr(self.manager, "items", [])
        names = [getattr(it, "name", f"item{i}") for i, it in enumerate(items)]
        self.items_lbl.text = "投喂项：" + (", ".join(names) if names else "(空)")

    def _save(self, *a):
        f = self.settings.setdefault("feed", {})
        f["first_text"] = self.first_in.text
        f["repeat_text"] = self.repeat_in.text
        self.manager.apply_settings(f)
        settings_mod.update_settings({"feed": f})
        if self.app:
            self.app.chat.settings = settings_mod.load_settings()
        self.items_lbl.text = "[OK] 已保存"
