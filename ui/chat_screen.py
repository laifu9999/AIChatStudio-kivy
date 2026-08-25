# -*- coding: utf-8 -*-
"""聊天主界面（Kivy）。功能与桌面版 MainWindow 对齐：
聊天气泡、流式回复、发送、会话管理、自动执行文件/命令块、显示折叠。"""
import os
import re
import random
import threading
import time
from kivy.clock import Clock, mainthread
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.modalview import ModalView
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.utils import get_color_from_hex

from core import config
from core import settings as settings_mod
from core import session as session_mod
from core import ai_client
from core import content_feed
from modules import code_tools
from modules import command_exec
from ui import theme

KV = """
<ChatScreen>:
    orientation: 'vertical'
    canvas.before:
        Color:
            rgba: theme.RC('bg')
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:  # 顶栏：会话 / 状态 / 阅读 / 投喂 / 工具 / 设置
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
            id: btn_sessions
            text: '会话'
            size_hint_x: None
            width: dp(50)
            background_color: theme.RC('panel2')
            background_normal: ''
            color: theme.RC('text')
            font_size: fs(13)
            on_press: root.open_sessions()
        Label:
            id: lbl_status
            text: '未选择模型'
            color: theme.RC('text_dim')
            font_size: fs(12)
            halign: 'left'
            text_size: self.size
            valign: 'middle'
            size_hint_x: 1
        Button:
            text: '阅读'
            size_hint_x: None
            width: dp(50)
            background_color: theme.RC('panel2')
            background_normal: ''
            color: theme.RC('text')
            font_size: fs(13)
            on_press: root.open_reader()
        Button:
            text: '投喂'
            size_hint_x: None
            width: dp(50)
            background_color: theme.RC('panel2')
            background_normal: ''
            color: theme.RC('text')
            font_size: fs(13)
            on_press: root.open_feed()
        Button:
            text: '工具'
            size_hint_x: None
            width: dp(50)
            background_color: theme.RC('panel2')
            background_normal: ''
            color: theme.RC('text')
            font_size: fs(13)
            on_press: root.open_tools()
        Button:
            text: '设置'
            size_hint_x: None
            width: dp(50)
            background_color: theme.RC('panel2')
            background_normal: ''
            color: theme.RC('text')
            font_size: fs(13)
            on_press: root.open_settings()
        Button:
            text: '文件'
            size_hint_x: None
            width: dp(46)
            background_color: theme.RC('panel2')
            background_normal: ''
            color: theme.RC('text')
            font_size: fs(13)
            on_press: root.open_project_files()
    BoxLayout:  # 投喂 / 续章实时状态条
        size_hint_y: None
        height: dp(20)
        padding: dp(6), 0
        canvas.before:
            Color:
                rgba: theme.RC('panel')
            Rectangle:
                pos: self.pos
                size: self.size
        Label:
            id: feed_status
            text: ''
            color: theme.RC('accent')
            font_size: fs(11)
            halign: 'left'
            text_size: self.size
            valign: 'middle'
    FloatLayout:  # 消息区 + 悬浮回顶/回底
        ScrollView:
            id: scroll
            bar_width: dp(6)
            scroll_type: ['bars', 'content']
            GridLayout:
                id: bubbles
                cols: 1
                spacing: dp(8)
                padding: dp(10)
                size_hint_y: None
                height: self.minimum_height
        BoxLayout:  # 悬浮在右下角的回顶/回底
            size_hint: None, None
            size: dp(96), dp(40)
            pos_hint: {'right': 0.99, 'bottom': 0.02}
            spacing: dp(4)
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
    BoxLayout:
        size_hint_y: None
        height: dp(110)
        padding: dp(6)
        spacing: dp(6)
        canvas.before:
            Color:
                rgba: theme.RC('panel')
            Rectangle:
                pos: self.pos
                size: self.size
        TextInput:
            id: inp
            hint_text: '输入消息，Enter 发送，Shift+Enter 换行'
            background_color: theme.RC('panel2')
            foreground_color: theme.RC('text')
            hint_text_color: theme.RC('text_dim')
            font_size: fs(15)
            padding: dp(10), dp(10)
            on_text_validate: root.do_send()
        BoxLayout:
            orientation: 'vertical'
            size_hint_x: None
            width: dp(70)
            spacing: dp(4)
            Button:
                id: btn_send
                text: '发送'
                background_color: theme.RC('accent')
                background_normal: ''
                color: (1,1,1,1)
                font_size: fs(15)
                on_press: root.do_send()
            Button:
                id: btn_stop
                text: '停止'
                size_hint_y: None
                height: dp(36)
                background_color: theme.RC('panel4')
                background_normal: ''
                color: theme.RC('text')
                font_size: fs(13)
                disabled: True
                on_press: root.stop_reply()
"""

auto_exec_langs = {"cmd", "batch", "sh", "bash", "shell", "ps", "powershell", "ps1",
                   "python", "py", "file", "replace", "append", "delete", "create_dir",
                   "savebody", "save_body", "savetext"}


class ChatBubble(BoxLayout):
    """单条聊天气泡。"""
    def __init__(self, role="ai", text="", **kw):
        super().__init__(**kw)
        self.orientation = "vertical"
        self.size_hint_y = None
        self.padding = dp(2)
        self.role = role
        # 背景圆角卡片
        with self.canvas.before:
            Color(rgba=theme.RC('user_bubble') if role == "user" else theme.RC('ai_bubble'))
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
        self.bind(pos=self._upd, size=self._upd)
        inner = BoxLayout(orientation="horizontal", padding=dp(10), spacing=dp(6))
        self.label = Label(
            text=text, color=theme.RC('text'), font_size=theme.fs(16),
            size_hint_y=None, text_size=(Window.width - dp(80), None),
            valign="top", halign="left", markup=False,
        )
        self.label.bind(texture_size=self._upd_height)
        inner.add_widget(self.label)
        self.add_widget(inner)
        Clock.schedule_once(lambda dt: self._upd_height())

    def _upd(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _upd_height(self, *a):
        self.label.height = self.label.texture_size[1]
        self.height = self.label.texture_size[1] + dp(20)

    def set_text(self, text, streaming=False):
        self.label.text = text + ("▌" if streaming else "")

    def append_text(self, delta):
        self.label.text += delta


def theme_font_size():
    try:
        s = settings_mod.load_settings()
        return s.get("ui", {}).get("font_size", 16)
    except Exception:
        return 16


class ChatScreen(BoxLayout):
    def __init__(self, app=None, **kw):
        super().__init__(**kw)
        self.app = app
        self.current_sid = None
        self.settings = settings_mod.load_settings()
        self.auto_exec = self.settings["permissions"].get("auto_exec_cmds", True)
        self.show_thinking = False
        self._stream_text = ""
        self._stream_bubble = None
        self._running = False
        self._stop = False
        self._client = None
        self._build_done = False
        # 常驻投喂管理器：跨多次发送保留“每个会话一次投喂”的序号状态
        self.feed_mgr = content_feed.ContentFeedManager()
        # 自动续章状态
        self._auto_active = False
        self._auto_round = 0
        self._auto_total = 0
        self._auto_token = 0  # 守卫：每次新发送自增，避免等待期间重复触发

    # ---- 由 main.py 在 add_widget 后调用 ----
    def on_parent(self, *a):
        if not self._build_done:
            self._build_done = True
            self.refresh_client()
            self._new_or_last_session()

    def _new_or_last_session(self):
        sessions = session_mod.list_sessions()
        if sessions:
            self.select_session(sessions[0]["id"])
        else:
            self.new_session(silent=True)

    # ---- 客户端 ----
    def refresh_client(self):
        self.settings = settings_mod.load_settings()
        prov = self.settings.get("active_provider")
        provs = self.settings.get("providers", {})
        if not prov or prov not in provs:
            self._client = None
            return
        p = provs[prov]
        self._client = ai_client.ChatClient(
            provider_name=prov,
            api_key=p.get("api_key", ""),
            model=p.get("model", "") or ai_client.default_model_for(prov),
            base_url=p.get("base_url", ""),
            system_prompt=self.settings.get("agent_system_prompt", ""),
        )
        self.ids.lbl_status.text = f"{prov} · {p.get('model','')}"

    # ---- 会话 ----
    def new_session(self, silent=False):
        meta = session_mod.create_session(name="新会话")
        self.select_session(meta["id"])
        if not silent:
            self._add_bubble("ai", "已新建会话。告诉我你想做什么吧～")

    def select_session(self, sid):
        self.current_sid = sid
        # 切换会话：重置“每个会话一次投喂”序号，使新会话重新触发首次投喂
        self.feed_mgr.reset_text_feed()
        self._auto_active = False
        self.ids.bubbles.clear_widgets()
        msgs = session_mod.get_messages(sid)
        for m in msgs:
            self._add_bubble(m["role"], m["content"])
        # 滚动到底
        Clock.schedule_once(lambda dt: self._scroll_bottom())

    def delete_session(self, sid):
        session_mod.delete_session(sid)
        if sid == self.current_sid:
            self.current_sid = None
            self.feed_mgr.reset_text_feed()
            self._auto_active = False
            self.ids.bubbles.clear_widgets()
            self._new_or_last_session()

    def open_sessions(self):
        self.app.open_sessions_drawer()

    def open_settings(self):
        self.app.go_settings()

    def open_tools(self):
        self.app.go_tools()

    def open_feed(self):
        self.app.go_feed()

    def open_reader(self):
        self.app.go_reader()

    def open_project_files(self):
        self.app.open_project_files()

    # ---- 回顶部 / 回底部（平板/手机一键定位）----
    def scroll_to_top(self, *a):
        try:
            self.ids.scroll.scroll_y = 1
        except Exception:
            pass

    def scroll_to_bottom(self, *a):
        try:
            self.ids.scroll.scroll_y = 0
        except Exception:
            pass

    # ---- 气泡 ----
    def _add_bubble(self, role, text, streaming=False):
        b = ChatBubble(role=role, text=text)
        self.ids.bubbles.add_widget(b)
        self._scroll_bottom()
        return b

    def _scroll_bottom(self, *a):
        try:
            sv = self.ids.scroll
            sv.scroll_y = 0
        except Exception:
            pass

    # ---- 发送 ----
    def do_send(self):
        text = self.ids.inp.text.strip()
        if not text:
            return
        self.ids.inp.text = ""
        if not self.current_sid:
            self.new_session(silent=True)
        # 读取自动续章开关
        feed_cfg = settings_mod.load_settings().get("feed", {})
        auto_on = bool(feed_cfg.get("auto_continue", False))
        self._auto_active = auto_on
        self._auto_round = 1
        self._auto_token += 1
        try:
            self._auto_total = max(1, min(int(feed_cfg.get("max_rounds", 1)), 300)) if auto_on else 1
        except Exception:
            self._auto_total = 1
        self._add_bubble("user", text)
        session_mod.append_message(self.current_sid, "user", text)
        if auto_on:
            self.set_feed_status(f"自动续章已开启：共 {self._auto_total} 章")
        self._run_chat(text, auto=auto_on)

    def stop_reply(self):
        self._stop = True
        self._auto_active = False
        self.set_feed_status("已停止")

    def set_feed_status(self, text):
        try:
            self.ids.feed_status.text = text
        except Exception:
            pass

    def _run_chat(self, user_text, auto=False):
        if not self._client:
            self._add_bubble("ai", "尚未配置 AI。请点右上角 设置 填写提供商 API Key 与模型。")
            return
        # 组装消息
        msgs = self._build_messages(user_text)
        msgs = self._inject_feed(msgs)
        self._running = True
        self._stop = False
        self.ids.btn_stop.disabled = False
        self._stream_text = ""
        self._stream_bubble = self._add_bubble("ai", "", streaming=True)

        def on_token(delta):
            if self._stop:
                return
            self._stream_text += delta
            Clock.schedule_once(lambda dt: self._stream_bubble.append_text(delta))

        def worker():
            try:
                full = self._client.chat(msgs, on_token=on_token)
            except Exception as e:
                full = f"[!] 调用出错：{e}"
            Clock.schedule_once(lambda dt: self._on_reply_done(full))

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _inject_feed(self, msgs):
        """若投喂已开启，把投喂上下文作为 system 消息前置注入，并实时回报状态。"""
        try:
            s = settings_mod.load_settings()
            if not s.get("feed", {}).get("enabled"):
                self.set_feed_status("投喂：关闭")
                return msgs
            # 复用常驻管理器，仅刷新开关/文件（保留“每个会话一次”的序号）
            self.feed_mgr.apply_settings(s.get("feed", {}))
            ctx, has, status = self.feed_mgr.build_context_with_status(purpose="chat")
            # 实时显示投喂成功/失败
            ok_items = [f"{lbl}成功" for lbl, ok, _ in status if ok]
            fail_items = [f"{lbl}失败({d})" for lbl, ok, d in status if not ok]
            if ok_items or fail_items:
                parts = []
                if ok_items:
                    parts.append("投喂成功:" + "/".join(ok_items))
                if fail_items:
                    parts.append("投喂失败:" + "/".join(fail_items))
                self.set_feed_status(" | ".join(parts))
            if has:
                msgs = [{"role": "system", "content": ctx}] + msgs
        except Exception as e:
            self.set_feed_status(f"投喂异常：{e}")
        return msgs

    # ---- 自动续章 ----
    def _maybe_auto_continue(self):
        """一轮回复完成后，判断是否继续自动续章。"""
        if not self._auto_active or self._stop:
            return
        if self._auto_round >= self._auto_total:
            self._auto_active = False
            self.set_feed_status(f"续章完成：共 {self._auto_total} 章")
            return
        wait = random.uniform(3, 6)
        self.set_feed_status(
            f"续章中 第 {self._auto_round + 1}/{self._auto_total} 章，等待 {wait:.1f} 秒…")
        tok = self._auto_token
        Clock.schedule_once(lambda dt: self._auto_next(dt, tok), wait)

    def _auto_next(self, dt, tok=None):
        if tok is not None and tok != self._auto_token:
            return  # 等待期间用户又发了新消息，放弃本次续章
        if self._stop or not self._auto_active:
            return
        self._auto_round += 1
        cont = f"（自动续章）请继续创作第 {self._auto_round} 章，保持文风与剧情连贯。"
        self._add_bubble("user", cont)
        session_mod.append_message(self.current_sid, "user", cont)
        self._run_chat(cont, auto=True)

    def _build_messages(self, user_text):
        # 历史（去掉思考与代码块，保留纯对话）
        history = session_mod.get_messages(self.current_sid)
        msgs = []
        for m in history:
            if m["role"] not in ("user", "assistant"):
                continue
            # 用户消息里可能含系统注入的 [自动保存...] 标记，去掉
            c = re.sub(r"^\[自动保存[^\]]*\]\n?", "", m["content"]).strip()
            c = re.sub(r"^\[自动执行命令的结果[^\]]*\]\n?", "", c).strip()
            if not c:
                continue
            msgs.append({"role": m["role"], "content": c})
        msgs.append({"role": "user", "content": user_text})
        return msgs

    @mainthread
    def _on_reply_done(self, full):
        self._running = False
        self.ids.btn_stop.disabled = True
        # 最终文本（清洗 + 折叠代码块）
        display = self._display_text(full)
        self._stream_bubble.set_text(display)
        # 保存完整回复到会话
        session_mod.append_message(self.current_sid, "assistant", full)
        # 自动执行文件/命令块
        if self.auto_exec and not self._stop:
            self._maybe_exec_commands(full)
        # 自动续章：本轮完成后判断是否继续
        if not self._stop:
            self._maybe_auto_continue()

    # ---- 文件/命令自动执行（跨平台核心） ----
    def _maybe_exec_commands(self, text):
        body = self._chat_body_for_exec(text)
        target = session_mod.get_session_folder(self.current_sid) if self.current_sid else None
        if not target or not os.path.isdir(target):
            return
        target = str(target)
        # 0) %%FILE: 标记
        try:
            if "%%FILE:" in body:
                markers = code_tools.extract_file_markers(body)
                if markers:
                    logs = code_tools.apply_blocks(markers, target)
                    self._add_bubble("ai", "[保存] 已自动保存正文到文件：\n" + "\n".join(logs[:20]))
                    session_mod.append_message(self.current_sid, "user",
                                               f"[自动保存 {len(markers)} 个文件到 {target}]\n" + "\n".join(logs))
        except Exception as e:
            self._add_bubble("ai", f"[!] %%FILE: 自动保存出错：{e}")
        # 1) file/replace/append/delete/create_dir/savebody 代码块
        try:
            blocks = code_tools.parse_code_blocks(text)
            if blocks:
                logs = code_tools.apply_blocks(blocks, target, body=body)
                self._add_bubble("ai", "[文件] 已自动应用文件操作：\n" + "\n".join(logs[:20]))
        except Exception as e:
            self._add_bubble("ai", f"[!] 代码块应用出错：{e}")
        # 2) python/cmd/powershell 代码块
        try:
            for lang, code in self._extract_codeblocks(text):
                if not self._is_valid_command(code):
                    continue
                ok, out, _ = command_exec.run_block(lang, code, cwd=target, body=body)
                tag = {"python": "Python", "py": "Python", "cmd": "CMD",
                       "powershell": "PS", "sh": "Shell", "bash": "Shell"}.get(lang, "CMD")
                head = f"[执行] {tag}：{code.splitlines()[0][:60]}"
                self._add_bubble("ai", head + "\n[结果]：\n" + (out[:2000] or "(无输出)"))
        except Exception as e:
            self._add_bubble("ai", f"[!] 命令执行出错：{e}")

    # ---- 文本处理工具 ----
    def _chat_body_for_exec(self, text):
        if not text:
            return ""
        t = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.S | re.I)
        t = re.sub(r"```.*?```", "", t, flags=re.S)
        return t.strip()

    def _extract_codeblocks(self, text):
        blocks = []
        pat = re.compile(r"```(\w*)\r?\n(.*?)```", re.S)
        for m in pat.finditer(text):
            lang = (m.group(1) or "").lower().strip()
            code = m.group(2).strip()
            if not code:
                continue
            if lang in ("cmd", "batch", "sh", "bash", "shell", "ps", "powershell", "ps1",
                        "python", "py", ""):
                blocks.append((lang, code))
        return blocks

    def _is_valid_command(self, code):
        if not code or not code.strip():
            return False
        for line in code.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            if re.match(r'^[A-Za-z0-9_\-\.]+[\/\\]$', line):
                continue
            if re.match(r'^[\.\/\\A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+$', line):
                continue
            return True
        return False

    def _strip_thinking(self, text):
        if not text:
            return text
        t = re.sub(r"<think(?:ing)?\b[^>]*>.*?</think(?:ing)?>", "", text, flags=re.S | re.I)
        t = re.sub(r"【思考】.*?【/思考】", "", t, flags=re.S)
        return t.strip()

    def _display_text(self, text):
        if not text:
            return text
        text = self._strip_thinking(text)
        if not self.auto_exec:
            return text
        pat = re.compile(r"```([^\n]*)\r?\n(.*?)\n```", re.S)

        def _repl(m):
            header = (m.group(1) or "").strip()
            lang = header.split()[0].lower() if header else ""
            if lang in auto_exec_langs or lang == "":
                code = m.group(2) or ""
                lines = [l for l in code.splitlines() if l.strip()]
                if not lines:
                    return ""
                if lang in ("file", "replace", "append", "delete", "create_dir"):
                    return f"\n\n[文件] 已自动应用 {len(lines)} 行文件操作\n"
                return f"\n\n[执行] 已自动执行（{len(lines)} 行）\n"
            return m.group(0)

        text = pat.sub(_repl, text)
        if "%%FILE:" in text:
            try:
                text = code_tools.strip_file_markers(text)
            except Exception:
                pass
        return text
