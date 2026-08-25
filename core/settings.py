"""设置读写：线程安全的 JSON 持久化。"""
import json
import threading
from core.config import SETTINGS_FILE, DEFAULT_SETTINGS

_lock = threading.Lock()


def load_settings():
    """读取设置，合并默认值，保证字段完整。"""
    if not SETTINGS_FILE.exists():
        save_settings(DEFAULT_SETTINGS)
        return dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return dict(DEFAULT_SETTINGS)
    # 深合并默认值，防止缺字段
    merged = dict(DEFAULT_SETTINGS)
    merged.update(data)
    for k, v in DEFAULT_SETTINGS.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            base = dict(v)
            base.update(merged[k])
            merged[k] = base
    return merged


def save_settings(settings):
    """写入设置文件。"""
    with _lock:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)


def update_settings(patch):
    """局部更新并保存。patch 可为嵌套 dict（仅一层）。"""
    cur = load_settings()
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(cur.get(k), dict):
            cur[k].update(v)
        else:
            cur[k] = v
    save_settings(cur)
    return cur
