# -*- coding: utf-8 -*-
"""投喂（Feed）界面（Kivy）。管理文字/文件投喂项与开关，纯 Python 跨平台。

功能：
- 投喂总开关
- 添加文字投喂（对话中持续作为前置上下文）
- 每个会话一次投喂（仅本会话首次注入一次，切换会话重置）
- 无限次投喂文字（每次对话都注入）
- 指定文件投喂（无限次，每轮都读取并注入，可添加多个、可删除）
- 自动续章（开启后，一次发送会触发 AI 自动续写 1~300 章，章间随机等待 3~6 秒，
  续章同时注入上述投喂内容，聊天界面实时显示投喂成功/失败状态）
"""
import os
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.modalview import ModalView
from kivy.uix.filechooser import FileChooserListView
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
        self.feed_files = list(self.settings.get("feed", {}).get("feed_files", []) or [])
        self._build_form()

    def _row(self, label_text, widget):
        box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(74), spacing=dp(4))
        lab = Label(text=label_text, color=theme.C('text_dim'), font_size=fs(12),
                    size_hint_y=None, height=dp(16), halign="left", text_size=(self.width, None))
        lab.bind(size=lambda *a: setattr(lab, 'text_size', (lab.width, None)))
        box.add_widget(lab); box.add_widget(widget)
        self.ids.form.add_widget(box)

    def _section(self, title):
        lab = Label(text=title, color=theme.C('text'), size_hint_y=None, height=dp(22),
                    halign="left", font_size=fs(14), bold=True,
                    text_size=(self.width, None))
        lab.bind(size=lambda *a: setattr(lab, 'text_size', (lab.width, None)))
        self.ids.form.add_widget(lab)

    def _build_form(self):
        f = self.settings.get("feed", {})

        # 投喂总开关
        self.enable_cb = Button(
            text="[开] 投喂已开启" if f.get("enabled") else "投喂已关闭（点击开启）",
            size_hint_y=None, height=dp(42),
            background_color=theme.C('panel2'), background_normal='', color=theme.C('text'),
            font_size=fs(14))
        self.enable_cb.bind(on_press=self._toggle)
        self.ids.form.add_widget(self.enable_cb)

        # 添加文字投喂
        self.text_in = TextInput(hint_text="输入要持续投喂的文字内容",
                                 background_color=theme.C('panel2'),
                                 foreground_color=theme.C('text'), size_hint_y=None, height=dp(60),
                                 font_size=fs(13))
        self._row("添加文字投喂（持续作为上下文）", self.text_in)
        add_txt = Button(text="添加文字", size_hint_y=None, height=dp(38),
                         background_color=theme.C('panel4'), background_normal='',
                         color=theme.C('text'), font_size=fs(14))
        add_txt.bind(on_press=self._add_text)
        self.ids.form.add_widget(add_txt)

        self._section("文字投喂指令")
        self.first_in = TextInput(hint_text="每个会话仅首次注入一次（如核心设定/世界观）",
                                  text=f.get("first_text", ""),
                                  background_color=theme.C('panel2'),
                                  foreground_color=theme.C('text'), size_hint_y=None, height=dp(42),
                                  font_size=fs(13))
        self._row("每个会话一次投喂", self.first_in)
        self.repeat_in = TextInput(hint_text="每次对话都注入（无限次，如风格要求）",
                                   text=f.get("repeat_text", ""),
                                   background_color=theme.C('panel2'),
                                   foreground_color=theme.C('text'), size_hint_y=None, height=dp(42),
                                   font_size=fs(13))
        self._row("无限次投喂文字", self.repeat_in)

        # 指定文件投喂（无限次）
        self._section("指定文件投喂（无限次）")
        pick = Button(text="＋ 选择文件注入投喂", size_hint_y=None, height=dp(40),
                      background_color=theme.C('panel4'), background_normal='',
                      color=theme.C('text'), font_size=fs(14))
        pick.bind(on_press=self._pick_file)
        self.ids.form.add_widget(pick)
        self.files_lbl = Label(text="", color=theme.C('text_dim'), size_hint_y=None,
                               height=dp(20), halign="left", font_size=fs(12),
                               text_size=(self.width, None))
        self.files_lbl.bind(size=lambda *a: setattr(self.files_lbl, 'text_size', (self.files_lbl.width, None)))
        self.ids.form.add_widget(self.files_lbl)
        self.files_box = GridLayout(cols=1, spacing=dp(4), size_hint_y=None, height=dp(10))
        self.files_box.bind(minimum_height=self.files_box.setter("height"))
        self.ids.form.add_widget(self.files_box)
        self._refresh_files()

        # 自动续章
        self._section("自动续章（AI 自动续写小说）")
        self.auto_cb = Button(
            text="[开] 自动续章已开启" if f.get("auto_continue") else "自动续章已关闭（点击开启）",
            size_hint_y=None, height=dp(42),
            background_color=theme.C('panel2'), background_normal='', color=theme.C('text'),
            font_size=fs(14))
        self.auto_cb.bind(on_press=self._toggle_auto)
        self.ids.form.add_widget(self.auto_cb)
        self.chapter_in = TextInput(hint_text="续章数 1~300",
                                    text=str(f.get("max_rounds", 10)),
                                    background_color=theme.C('panel2'),
                                    foreground_color=theme.C('text'), size_hint_y=None, height=dp(42),
                                    font_size=fs(13), input_filter="int")
        self._row("续章数（1~300 章）", self.chapter_in)

        # 保存
        save = Button(text="保存投喂设置", size_hint_y=None, height=dp(44),
                      background_color=theme.C('accent'), background_normal='',
                      color=(1, 1, 1, 1), font_size=fs(15))
        save.bind(on_press=self._save)
        self.ids.form.add_widget(save)

        self.items_lbl = Label(text="投喂项：", color=theme.C('text_dim'), size_hint_y=None,
                               height=dp(20), halign="left", font_size=fs(13),
                               text_size=(self.width, None))
        self.items_lbl.bind(size=lambda *a: setattr(self.items_lbl, 'text_size', (self.items_lbl.width, None)))
        self.ids.form.add_widget(self.items_lbl)
        self._refresh_items()

    # ---------------- 开关 ----------------
    def _toggle(self, *a):
        f = self.settings.setdefault("feed", {})
        f["enabled"] = not f.get("enabled", False)
        self.enable_cb.text = "[开] 投喂已开启" if f["enabled"] else "投喂已关闭（点击开启）"
        self.manager.apply_settings(f)
        settings_mod.update_settings({"feed": f})

    def _toggle_auto(self, *a):
        f = self.settings.setdefault("feed", {})
        f["auto_continue"] = not f.get("auto_continue", False)
        self.auto_cb.text = "[开] 自动续章已开启" if f["auto_continue"] else "自动续章已关闭（点击开启）"
        self.manager.apply_settings(f)
        settings_mod.update_settings({"feed": f})

    # ---------------- 文字投喂 ----------------
    def _add_text(self, *a):
        txt = self.text_in.text.strip()
        if not txt:
            return
        self.manager.add_text(txt, name=f"text_{len(self.manager.items)+1}")
        self.text_in.text = ""
        self._refresh_items()

    # ---------------- 文件投喂 ----------------
    def _pick_file(self, *a):
        mv = ModalView(size_hint=(0.95, 0.9))
        bl = BoxLayout(orientation="vertical", padding=dp(6), spacing=dp(6))
        fc = FileChooserListView(path=os.path.expanduser("~"), size_hint=(1, 1))
        bl.add_widget(fc)

        def _choose(*args):
            if not fc.selection:
                return
            path = fc.selection[0]
            if os.path.isfile(path) and path not in self.feed_files:
                self.feed_files.append(path)
                self._refresh_files()
                self._persist()
            mv.dismiss()

        bar = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        ok = Button(text="确定", background_color=theme.C('accent'), background_normal='',
                    color=(1, 1, 1, 1), font_size=fs(14))
        ok.bind(on_press=_choose)
        cancel = Button(text="取消", background_color=theme.C('panel4'), background_normal='',
                        color=theme.C('text'), font_size=fs(14))
        cancel.bind(on_press=mv.dismiss)
        bar.add_widget(ok); bar.add_widget(cancel)
        bl.add_widget(bar)
        mv.add_widget(bl)
        mv.open()

    def _refresh_files(self):
        self.files_box.clear_widgets()
        if not self.feed_files:
            self.files_lbl.text = "（未选择文件）"
        else:
            self.files_lbl.text = f"已选 {len(self.feed_files)} 个文件："
            for i, p in enumerate(self.feed_files):
                row = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(4))
                lab = Label(text=os.path.basename(p), color=theme.C('text'),
                            halign="left", font_size=fs(12), text_size=(self.width * 0.7, None))
                del_b = Button(text="删除", size_hint_x=None, width=dp(56),
                               background_color=theme.C('danger'), background_normal='',
                               color=(1, 1, 1, 1), font_size=fs(12))

                def _del(*a, idx=i):
                    if 0 <= idx < len(self.feed_files):
                        self.feed_files.pop(idx)
                        self._refresh_files()
                        self._persist()

                del_b.bind(on_press=_del)
                row.add_widget(lab); row.add_widget(del_b)
                self.files_box.add_widget(row)

    # ---------------- 投喂项 ----------------
    def _refresh_items(self):
        items = getattr(self.manager, "items", [])
        names = [getattr(it, "name", f"item{i}") for i, it in enumerate(items)]
        self.items_lbl.text = "投喂项：" + (", ".join(names) if names else "(空)")

    # ---------------- 持久化 ----------------
    def _persist(self):
        f = self.settings.setdefault("feed", {})
        f["feed_files"] = list(self.feed_files)
        settings_mod.update_settings({"feed": f})
        if self.app:
            self.app.chat.settings = settings_mod.load_settings()

    def _save(self, *a):
        f = self.settings.setdefault("feed", {})
        f["first_text"] = self.first_in.text
        f["repeat_text"] = self.repeat_in.text
        try:
            f["max_rounds"] = max(1, min(int(self.chapter_in.text or 10), 300))
        except Exception:
            f["max_rounds"] = 10
        f["feed_files"] = list(self.feed_files)
        self.manager.apply_settings(f)
        settings_mod.update_settings({"feed": f})
        if self.app:
            self.app.chat.settings = settings_mod.load_settings()
        self.items_lbl.text = "[OK] 已保存"
