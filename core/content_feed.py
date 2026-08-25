"""自定义内容投喂模块（Feed）。

功能概览：
1. 文字投喂：用户手动输入一段文字，作为"投喂内容"提交给 AI。
2. 文件投喂：用户选取文档文件（txt/md/py/json/csv 等纯文本类），把内容投喂给 AI。
3. 实时监测多文件：后台线程周期性轮询被监控文件的「大小 + 内容哈希」，
   一旦检测到内容「增多」或「减少」（即发生变化），就自动把最新内容投喂给 AI。
4. 上下文注入策略：
   - 前置上下文（prepend）：在每次 AI 对话前，把指定文件/投喂内容"先读"一遍（放在 system 之后、user 之前）。
   - 思考前读取（thinking_read_first）：在 AI 思考/回复每个内容前，先读取某些文件或先看投喂内容
     （实现上等价于把这部分作为最高优先级上下文注入到本轮消息里）。
5. 投喂状态/内容实时可见：通过 Qt 信号把"投喂事件"回传给主线程，主窗口负责展示。

设计说明：
- FeedItem 描述单个投喂源（文字 or 文件）。
- FileMonitorThread 只负责"检测变化 + 发信号"，不碰 UI、不碰会话文件，线程安全。
- ContentFeedManager 维护配置与当前投喂项，并提供 build_context() 供主窗口注入消息。
"""
import os
import time
import hashlib
import threading
import json
from pathlib import Path

# 支持直接读取为文本的扩展名（避免把二进制文件当文本读导致乱码/崩溃）
TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".py", ".js", ".ts", ".jsx", ".tsx", ".java",
    ".go", ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".sh", ".bash",
    ".html", ".htm", ".css", ".scss", ".less", ".json", ".yaml", ".yml",
    ".toml", ".xml", ".ini", ".cfg", ".conf", ".csv", ".log", ".rst", ".tex",
    ".sql", ".r", ".lua", ".rs", ".swift", ".kt", ".scala", ".dart", ".vue",
    ".gitignore", ".dockerfile", ".env", ".bat", ".ps1",
}


def _read_text_file(path, max_chars=200_000):
    """安全读取文本文件，超长截断并提示。返回 (text, truncated:bool)。"""
    try:
        # 优先用 utf-8，失败回退到 errors="ignore"
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            data = f.read()
        if len(data) > max_chars:
            return data[:max_chars] + f"\n\n…（内容过长，已截断至前 {max_chars} 字符）", True
        return data, False
    except Exception:
        # 再试一次二进制忽略
        try:
            with open(path, "rb") as f:
                raw = f.read(max_chars * 4)
            return raw.decode("utf-8", "ignore"), True
        except Exception:
            return "", False


def _file_sig(path):
    """返回文件的 (size, mtime, sha1_head) 签名，用于快速判断内容变化。

    只取前 64KB 计算哈希，既兼顾"内容增减"检测，又避免大文件频繁全量哈希拖慢。
    """
    try:
        if not os.path.isfile(path):
            return None
        st = os.stat(path)
        size = st.st_size
        mtime = st.st_mtime
        # 头 + 尾 采样哈希：能捕捉"内容增多/减少/修改"
        with open(path, "rb") as f:
            head = f.read(32_768)
            f.seek(max(0, size - 32_768), os.SEEK_SET)
            tail = f.read(32_768) if size > 0 else b""
        h = hashlib.sha1(head + tail + str(size).encode("utf-8")).hexdigest()
        return (size, mtime, h)
    except Exception:
        return None


class FeedItem:
    """单个投喂源。

    kind: "text" | "file"
    - text 模式：content 为用户输入的文字。
    - file 模式：path 为文件路径；monitor=True 表示开启实时监测，
      content 缓存最近一次读取内容。
    """

    def __init__(self, kind, content="", path="", monitor=False, name="", enabled=True):
        self.kind = kind  # "text" / "file"
        self.content = content
        self.path = path
        self.monitor = monitor  # 是否实时监测文件变化（仅 file 有效）
        self.name = name or (os.path.basename(path) if path else ("文字投喂" if kind == "text" else "文件投喂"))
        self.enabled = enabled
        self.last_sig = _file_sig(path) if kind == "file" and path else None
        self.last_fed_size = (self.last_sig[0] if self.last_sig else 0)

    def to_dict(self):
        return {
            "kind": self.kind,
            "content": self.content,
            "path": self.path,
            "monitor": self.monitor,
            "name": self.name,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            kind=d.get("kind", "text"),
            content=d.get("content", ""),
            path=d.get("path", ""),
            monitor=d.get("monitor", False),
            name=d.get("name", ""),
            enabled=d.get("enabled", True),
        )

    def read_content(self):
        """返回当前应投喂的内容字符串。"""
        if self.kind == "text":
            return self.content or ""
        # file
        if not self.path or not os.path.isfile(self.path):
            return ""
        text, _ = _read_text_file(self.path)
        self.content = text
        return text

    def current_size(self):
        if self.kind == "file" and self.path and os.path.isfile(self.path):
            try:
                return os.path.getsize(self.path)
            except Exception:
                return 0
        return len(self.content or "")

    def changed(self):
        """检测文件是否发生变化（仅 file + monitor 有意义）。返回 (changed:bool, direction:str)。"""
        if self.kind != "file" or not self.monitor or not self.path:
            return False, ""
        new_sig = _file_sig(self.path)
        if new_sig is None:
            # 文件可能被删除
            if self.last_sig is not None:
                self.last_sig = None
                return True, "deleted"
            return False, ""
        if self.last_sig is None:
            self.last_sig = new_sig
            return True, "created"
        if new_sig != self.last_sig:
            old_size = self.last_sig[0]
            new_size = new_sig[0]
            direction = "increased" if new_size > old_size else ("decreased" if new_size < old_size else "modified")
            self.last_sig = new_sig
            return True, direction
        return False, ""


class FileMonitorThread(threading.Thread):
    """后台线程：周期性检测所有 monitor 文件的签名变化。

    一旦某文件变化（增多/减少/修改/创建/删除），通过 callback 把 FeedItem 回传主线程。
    callback 签名：on_change(feed_item, direction, content)
    """

    def __init__(self, manager, interval=2.0, on_change=None, on_error=None):
        super().__init__(daemon=True)
        self.manager = manager
        self.interval = interval
        self.on_change = on_change
        self.on_error = on_error
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.is_set():
            try:
                for item in self.manager.items:
                    if not item.enabled or item.kind != "file" or not item.monitor:
                        continue
                    changed, direction = item.changed()
                    if changed:
                        content = item.read_content()
                        if self.on_change:
                            try:
                                self.on_change(item, direction, content)
                            except Exception as e:
                                if self.on_error:
                                    self.on_error(f"投喂回调异常：{e}")
            except Exception as e:
                if self.on_error:
                    try:
                        self.on_error(f"文件监测异常：{e}")
                    except Exception:
                        pass
            # 分段 sleep，避免 stop 后要等满一个 interval
            for _ in range(int(self.interval * 10)):
                if self._stop.is_set():
                    break
                time.sleep(0.1)


class ContentFeedManager:
    """投喂管理器：内存中维护投喂项与开关，提供上下文构建与持久化。

    配置存储位置：data/feed.json（与 settings.json 同目录）。
    另有一部分开关（enabled 总开关、prepend_files、thinking_read_first、show_feed）
    合并进 settings.json 的 "feed" 字段，方便统一读写。
    """

    def __init__(self, items=None, settings_patch=None):
        self.items = items or []  # List[FeedItem]
        self.enabled = True  # 投喂总开关
        self.prepend_files = []  # 每次对话前"先读"的文件路径列表（前置上下文）
        self.thinking_read_first = True  # 思考/回复每个内容前，先看投喂内容/指定文件
        self.show_feed = True  # 投喂内容实时显示
        self.show_status = True  # 投喂状态显示
        self.monitor_interval = 2.0  # 文件监测间隔（秒）
        # 双文字投喂：first_text 仅每个会话首次注入一次；repeat_text 之后每次都注入
        self.first_text = ""
        self.repeat_text = ""
        # 指定文件投喂（无限次，每轮都注入）：文件绝对路径列表
        self.feed_files = []
        self._text_feed_idx = 0  # 0=尚未使用，>=1 表示首条已用
        # 连续自动回复：开启后 AI 自动续回最多 max_rounds 次（1-300），每次先注入投喂内容
        self.auto_continue = False
        self.max_rounds = 10
        self._lock = threading.Lock()
        self._monitor = None
        if settings_patch:
            self.apply_settings(settings_patch)

    # ---------------- 持久化 ----------------
    def apply_settings(self, s):
        """从 settings["feed"] 字典同步开关。"""
        if not s:
            return
        self.enabled = s.get("enabled", True)
        self.prepend_files = s.get("prepend_files", []) or []
        self.thinking_read_first = s.get("thinking_read_first", True)
        self.show_feed = s.get("show_feed", True)
        self.show_status = s.get("show_status", True)
        self.monitor_interval = s.get("monitor_interval", 2.0)
        self.first_text = s.get("first_text", "") or ""
        self.repeat_text = s.get("repeat_text", "") or ""
        self.feed_files = s.get("feed_files", []) or []
        self.auto_continue = bool(s.get("auto_continue", False))
        try:
            self.max_rounds = max(1, min(int(s.get("max_rounds", 10)), 300))
        except Exception:
            self.max_rounds = 10

    def to_settings_dict(self):
        return {
            "enabled": self.enabled,
            "prepend_files": self.prepend_files,
            "thinking_read_first": self.thinking_read_first,
            "show_feed": self.show_feed,
            "show_status": self.show_status,
            "monitor_interval": self.monitor_interval,
            "first_text": self.first_text,
            "repeat_text": self.repeat_text,
            "feed_files": self.feed_files,
            "auto_continue": self.auto_continue,
            "max_rounds": self.max_rounds,
        }

    def to_items_dict(self):
        with self._lock:
            return [it.to_dict() for it in self.items]

    def load_items(self, items_dict):
        with self._lock:
            self.items = [FeedItem.from_dict(d) for d in (items_dict or [])]

    # ---------------- 增删改 ----------------
    def add_text(self, content, name=""):
        with self._lock:
            it = FeedItem(kind="text", content=content, name=name or "文字投喂")
            self.items.append(it)
        return it

    def add_file(self, path, monitor=False, name=""):
        with self._lock:
            it = FeedItem(kind="file", path=path, monitor=monitor, name=name)
            self.items.append(it)
        return it

    def remove_item(self, idx):
        with self._lock:
            if 0 <= idx < len(self.items):
                return self.items.pop(idx)
        return None

    def set_item_enabled(self, idx, enabled):
        with self._lock:
            if 0 <= idx < len(self.items):
                self.items[idx].enabled = enabled

    def set_monitor(self, idx, monitor):
        with self._lock:
            if 0 <= idx < len(self.items):
                it = self.items[idx]
                it.monitor = monitor
                if monitor:
                    it.last_sig = _file_sig(it.path)

    def add_prepend_file(self, path):
        if path and path not in self.prepend_files:
            self.prepend_files.append(path)

    def remove_prepend_file(self, path):
        if path in self.prepend_files:
            self.prepend_files.remove(path)

    # ---------------- 上下文构建 ----------------
    def _read_prepend_files(self):
        """读取前置上下文文件内容。返回拼接后的文本块（或空串）。"""
        blocks = []
        for p in self.prepend_files:
            if p and os.path.isfile(p):
                text, trunc = _read_text_file(p)
                if text.strip():
                    tag = f"（已截断）" if trunc else ""
                    blocks.append(f"=== 参考文件：{os.path.basename(p)} ==={tag}\n{text}")
        return "\n\n".join(blocks)

    def _consume_text_feed(self):
        """双文字投喂消费：首次返回 first_text 并标记已用，之后返回 repeat_text。

        线程安全。每次调用（对应一次注入）推进一次序号。
        """
        with self._lock:
            if self._text_feed_idx == 0 and self.first_text.strip():
                self._text_feed_idx = 1
                return self.first_text
            return self.repeat_text

    def _consume_text_feed_status(self):
        """同 _consume_text_feed，但返回 (label, text) 以便上报状态。"""
        with self._lock:
            if self._text_feed_idx == 0 and self.first_text.strip():
                self._text_feed_idx = 1
                return "每个会话一次投喂", self.first_text
            return "重复投喂(无限次)", self.repeat_text

    def reset_text_feed(self):
        """重置双文字投喂序号（新会话开始时调用），
        使 first_text 在每个会话只触发一次。"""
        with self._lock:
            self._text_feed_idx = 0

    def _read_feed_items_status(self):
        """读取所有 enabled 投喂项 + 指定文件，返回 (blocks_text, status_list)。

        status_list: [(label, ok:bool, detail:str), ...] 供 UI 实时显示投喂成功/失败。
        """
        blocks = []
        status = []
        with self._lock:
            items = list(self.items)
        for it in items:
            if not it.enabled:
                continue
            label = ("文字投喂" if it.kind == "text" else "文件:" + os.path.basename(it.path or ""))
            if it.kind == "text":
                c = it.content or ""
                if c.strip():
                    blocks.append(f"=== 投喂文字 ===\n{c}")
                    status.append((label, True, f"{len(c)}字"))
                else:
                    status.append((label, False, "内容为空"))
            else:
                if it.path and os.path.isfile(it.path):
                    c, _ = _read_text_file(it.path)
                    if c.strip():
                        blocks.append(f"=== 投喂文件：{os.path.basename(it.path)} ===\n{c}")
                        status.append((label, True, f"{len(c)}字"))
                    else:
                        status.append((label, False, "文件为空/读取失败"))
                else:
                    status.append((label, False, "文件不存在"))
        # 指定文件投喂（无限次，每轮都注入）
        for p in (self.feed_files or []):
            label = "投喂文件:" + os.path.basename(p or "")
            if p and os.path.isfile(p):
                c, _ = _read_text_file(p)
                if c.strip():
                    blocks.append(f"=== 投喂文件：{os.path.basename(p)} ===\n{c}")
                    status.append((label, True, f"{len(c)}字"))
                else:
                    status.append((label, False, "文件为空"))
            else:
                status.append((label, False, "文件不存在"))
        # 双文字投喂（消耗一次序号）
        tf_label, tf = self._consume_text_feed_status()
        if tf.strip():
            blocks.append(f"=== 投喂文字（指令）===\n{tf}")
            status.append((tf_label, True, f"{len(tf)}字"))
        return "\n\n".join(blocks), status

    def build_context(self, purpose="chat"):
        """构建应注入到 AI 消息中的上下文文本（兼容旧调用）。"""
        ctx, has, _ = self.build_context_with_status(purpose)
        return ctx, has

    def build_context_with_status(self, purpose="chat"):
        """构建上下文，并返回 (context_text, has_content, status_list)。

        status_list: [(label, ok:bool, detail:str), ...] 供 UI 实时显示投喂成功/失败。
        """
        status = []
        if not self.enabled:
            status.append(("投喂总开关", False, "已关闭"))
            return "", False, status
        prepend = self._read_prepend_files()
        feed, feed_status = self._read_feed_items_status()
        status.extend(feed_status)
        has = bool(prepend.strip() or feed.strip())
        if not has:
            status.append(("投喂内容", False, "无可投喂内容"))
            return "", False, status

        if self.thinking_read_first:
            # 思考前先读：最高优先级 system 前置块
            parts = []
            if feed.strip():
                parts.append("[投喂内容-请先阅读后再思考与回复]\n" + feed)
            if prepend.strip():
                parts.append("[参考文件-请先阅读后再思考与回复]\n" + prepend)
            status.append(("上下文构建", True, "已注入"))
            return "\n\n".join(parts), True, status

        # chat 前置上下文（不强制先读，但投喂内容仍自动注入）
        parts = []
        if feed.strip():
            parts.append("[投喂内容-前置上下文]\n" + feed)
        if prepend.strip():
            parts.append("[参考文件-前置上下文]\n" + prepend)
        status.append(("上下文构建", True, "已注入"))
        return "\n\n".join(parts), True, status

    # ---------------- 监测线程控制 ----------------
    def start_monitor(self, on_change=None, on_error=None):
        """启动文件监测线程（若已有则先停再起）。"""
        self.stop_monitor()
        if not any(it.kind == "file" and it.monitor and it.enabled for it in self.items):
            return  # 没有需要监测的文件
        self._monitor = FileMonitorThread(
            self, interval=self.monitor_interval,
            on_change=on_change, on_error=on_error,
        )
        self._monitor.start()

    def stop_monitor(self):
        if self._monitor is not None:
            try:
                self._monitor.stop()
            except Exception:
                pass
            self._monitor = None

    def has_monitored_files(self):
        return any(it.kind == "file" and it.monitor and it.enabled for it in self.items)
