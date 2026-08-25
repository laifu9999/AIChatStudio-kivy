# -*- coding: utf-8 -*-
"""设置界面（Kivy）。字段与桌面版 settings_panel 对齐。"""
import threading
from kivy.clock import Clock, mainthread
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle

from core import settings as settings_mod
from core import ai_client
from ui import theme
from ui.theme import fs, READING_STYLE_LABELS

KV = """
<SettingsScreen>:
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
            text: '设置'
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


class SettingsScreen(BoxLayout):
    def __init__(self, app=None, **kw):
        super().__init__(**kw)
        self.app = app
        self.settings = settings_mod.load_settings()
        self._build_form()

    def _row(self, label_text, widget):
        box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(74), spacing=dp(4))
        lab = Label(text=label_text, color=theme.C('text_dim'), font_size=fs(12),
                    size_hint_y=None, height=dp(16), halign="left", text_size=(self.width, None))
        lab.bind(size=lambda *a: setattr(lab, 'text_size', (lab.width, None)))
        box.add_widget(lab)
        box.add_widget(widget)
        self.ids.form.add_widget(box)

    def _build_form(self):
        f = self.ids.form
        # 提供商
        self.provider_combo = Spinner(
            text=self.settings.get("active_provider") or "选择提供商",
            values=ai_client.list_providers(), size_hint_y=None, height=dp(42),
            background_color=theme.C('panel2'), background_normal='', color=theme.C('text'))
        self.provider_combo.bind(text=lambda inst, val: self._on_provider(val))
        self._row("AI 提供商", self.provider_combo)

        self.key_edit = TextInput(hint_text="API Key", password=True,
                                  background_color=theme.C('panel2'),
                                  foreground_color=theme.C('text'),
                                  size_hint_y=None, height=dp(42))
        self._row("API Key", self.key_edit)

        self.url_edit = TextInput(hint_text="Base URL（可留空用默认值）",
                                  background_color=theme.C('panel2'),
                                  foreground_color=theme.C('text'),
                                  size_hint_y=None, height=dp(42))
        self._row("Base URL", self.url_edit)

        self.model_combo = Spinner(text="选择模型", size_hint_y=None, height=dp(42),
                                   background_color=theme.C('panel2'), background_normal='',
                                   color=theme.C('text'))
        self._row("模型", self.model_combo)

        btn_row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        b1 = Button(text="获取模型列表", background_color=theme.C('panel4'), background_normal='',
                    color=theme.C('text'))
        b1.bind(on_press=self._fetch)
        b2 = Button(text="测试连接", background_color=theme.C('panel4'), background_normal='',
                    color=theme.C('text'))
        b2.bind(on_press=self._test)
        btn_row.add_widget(b1); btn_row.add_widget(b2)
        self.ids.form.add_widget(btn_row)
        self.status_lbl = Label(text="", color=theme.C('text_dim'), size_hint_y=None,
                                height=dp(20), halign="left", text_size=(self.width, None))
        self.status_lbl.bind(size=lambda *a: setattr(self.status_lbl, 'text_size', (self.status_lbl.width, None)))
        self.ids.form.add_widget(self.status_lbl)

        # 主题
        self.theme_combo = Spinner(text=self.settings["ui"].get("theme", "dark"),
                                   values=["dark", "light"], size_hint_y=None, height=dp(42),
                                   background_color=theme.C('panel2'), background_normal='',
                                   color=theme.C('text'))
        self.theme_combo.bind(text=lambda inst, val: self._on_theme(val))
        self._row("主题", self.theme_combo)

        # 阅读风格（聊天界面 / 阅读窗口）
        self.read_style_combo = Spinner(
            text=READING_STYLE_LABELS.get(self.settings["ui"].get("reading_style", "cream"), "米黄纸"),
            values=list(READING_STYLE_LABELS.values()), size_hint_y=None, height=dp(42),
            background_color=theme.C('panel2'), background_normal='', color=theme.C('text'))
        self.read_style_combo.bind(text=lambda inst, val: self._on_read_style(val))
        self._row("阅读风格（聊天/阅读窗口）", self.read_style_combo)

        # 字号
        self.font_spin = Spinner(text=str(self.settings["ui"].get("font_size", 16)),
                                 values=[str(x) for x in (12,14,16,18,20,22,24,28,32)],
                                 size_hint_y=None, height=dp(42),
                                 background_color=theme.C('panel2'), background_normal='',
                                 color=theme.C('text'))
        self._row("正文字号", self.font_spin)

        save = Button(text="保存设置", size_hint_y=None, height=dp(46),
                      background_color=theme.C('accent'), background_normal='',
                      color=(1,1,1,1), font_size=fs(16))
        save.bind(on_press=self._save)
        self.ids.form.add_widget(save)

        # 初始化填充
        if self.settings.get("active_provider"):
            self._on_provider(self.settings["active_provider"])

    def _on_provider(self, name):
        self.provider_combo.text = name
        provs = self.settings.get("providers", {})
        p = provs.get(name, {})
        self.key_edit.text = p.get("api_key", "")
        self.url_edit.text = p.get("base_url", "")
        fixed = ai_client.fixed_models_for(name)
        if fixed:
            self.model_combo.values = fixed
            self.model_combo.text = p.get("model") or fixed[0]
        else:
            self.model_combo.text = p.get("model") or ai_client.default_model_for(name) or "选择模型"
            self.model_combo.values = [self.model_combo.text] if self.model_combo.text != "选择模型" else []

    def _on_theme(self, name):
        theme.set_theme(name)

    def _on_read_style(self, label):
        key = None
        for k, v in READING_STYLE_LABELS.items():
            if v == label:
                key = k
                break
        if key:
            theme.set_reading_style(key)

    def _fetch(self, *a):
        name = self.provider_combo.text
        if name in ("选择提供商",) or name not in ai_client.list_providers():
            self.status_lbl.text = "请先选择提供商"
            return
        api_key = self.key_edit.text.strip()
        base_url = self.url_edit.text.strip() or None
        self.status_lbl.text = "正在获取模型列表…"
        def worker():
            try:
                models = ai_client.fetch_models(name, api_key, base_url)
                Clock.schedule_once(lambda dt: self._on_models(models))
            except Exception as e:
                Clock.schedule_once(lambda dt: setattr(self.status_lbl, "text", f"获取失败：{e}"))
        threading.Thread(target=worker, daemon=True).start()

    @mainthread
    def _on_models(self, models):
        if models:
            self.model_combo.values = models
            self.model_combo.text = models[0]
            self.status_lbl.text = f"已获取 {len(models)} 个模型"
        else:
            self.status_lbl.text = "未返回模型（可能 Key 无效）"

    def _test(self, *a):
        name = self.provider_combo.text
        if name in ("选择提供商",) or name not in ai_client.list_providers():
            self.status_lbl.text = "请先选择提供商"
            return
        api_key = self.key_edit.text.strip()
        base_url = self.url_edit.text.strip() or None
        model = self.model_combo.text if self.model_combo.text != "选择模型" else ""
        self.status_lbl.text = "正在测试连接…"
        def worker():
            try:
                c = ai_client.ChatClient(name, api_key, model, base_url,
                                        system_prompt=self.settings.get("agent_system_prompt", ""))
                ok, msg = c.test_connection()
                Clock.schedule_once(lambda dt: setattr(self.status_lbl,
                                                       "text", ("[OK] " if ok else "[X] ") + msg))
            except Exception as e:
                Clock.schedule_once(lambda dt: setattr(self.status_lbl, "text", f"测试异常：{e}"))
        threading.Thread(target=worker, daemon=True).start()

    def _save(self, *a):
        s = self.settings
        name = self.provider_combo.text
        if name and name in ai_client.list_providers():
            s.setdefault("providers", {})[name] = {
                "api_key": self.key_edit.text.strip(),
                "base_url": self.url_edit.text.strip(),
                "model": self.model_combo.text if self.model_combo.text != "选择模型" else "",
            }
            s["active_provider"] = name
            s["active_model"] = s["providers"][name]["model"]
        s.setdefault("ui", {})["theme"] = self.theme_combo.text
        s.setdefault("ui", {})["font_size"] = int(self.font_spin.text)
        # 阅读风格：label -> key
        rs_label = self.read_style_combo.text
        rs_key = None
        for k, v in READING_STYLE_LABELS.items():
            if v == rs_label:
                rs_key = k
        if rs_key:
            s.setdefault("ui", {})["reading_style"] = rs_key
        # 权限全部开启（与桌面版一致：默认最高权限、全自动）
        s["permissions"] = {
            "cmd": True, "automation": True, "browser": True,
            "danger_confirm": False, "auto_exec_cmds": True, "auto_save_on_intent": True,
        }
        settings_mod.save_settings(s)
        theme.set_theme(self.theme_combo.text)
        # 应用字号：必须在重建界面之前设置，使全界面即时联动
        try:
            theme.set_font_scale(self.font_spin.text)
        except Exception:
            pass
        self.status_lbl.text = "[OK] 已保存"
        if self.app:
            self.app.apply_theme_to_all()
            self.app.chat.refresh_client()
