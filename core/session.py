"""会话管理：每个会话对应一个项目文件夹。

项目文件夹可以是默认的 data/sessions/<project_id>/，也可以是用户指定的任意目录。
聊天记录自动保存为项目文件夹里的 messages.json 与 chat.md，重启/重开应用不丢失。
meta.json 始终保留在 data/sessions/<project_id>/ 作为会话索引，里面记录真实项目路径 path。
"""
import json
import shutil
import time
import uuid
from pathlib import Path
from core.config import SESSIONS_DIR


def _safe_name(name):
    return "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip() or "session"


def _meta_path(sid):
    """会话索引文件路径，固定放在 data/sessions/<sid>/meta.json。"""
    return SESSIONS_DIR / sid / "meta.json"


def _load_meta(sid):
    mp = _meta_path(sid)
    if not mp.exists():
        return None
    try:
        return json.loads(mp.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_meta(sid, meta):
    mp = _meta_path(sid)
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve_folder(sid, ensure=True):
    """返回会话真正使用的项目文件夹 Path。

    优先读取 meta.json 里的 path 字段；若未指定或目录不存在，则回退到
    data/sessions/<sid>/。
    """
    meta = _load_meta(sid)
    if meta and meta.get("path"):
        p = Path(meta["path"]).expanduser().resolve()
        if p.exists() and p.is_dir():
            return p
    folder = SESSIONS_DIR / sid
    if ensure:
        folder.mkdir(parents=True, exist_ok=True)
    return folder


def list_sessions():
    """返回会话元信息列表：[{id, name, created, updated, path}]"""
    sessions = []
    if not SESSIONS_DIR.exists():
        return sessions
    for p in SESSIONS_DIR.iterdir():
        meta_file = p / "meta.json"
        if p.is_dir() and meta_file.exists():
            try:
                m = json.loads(meta_file.read_text(encoding="utf-8"))
                # path 使用真实项目文件夹
                m["path"] = str(_resolve_folder(m["id"], ensure=False))
                sessions.append(m)
            except Exception:
                continue
    sessions.sort(key=lambda x: x.get("updated", 0), reverse=True)
    return sessions


def create_session(name=None, folder_path=None):
    """新建会话，自动创建项目文件夹。

    folder_path: 若提供，则作为真实项目文件夹（可在外部任意位置）。
                 会话索引 meta.json 仍保存在 data/sessions/<sid>/ 里。
    """
    sid = uuid.uuid4().hex[:12]
    if folder_path:
        folder = Path(folder_path).expanduser().resolve()
        folder.mkdir(parents=True, exist_ok=True)
    else:
        folder = SESSIONS_DIR / sid
        folder.mkdir(parents=True, exist_ok=True)
    meta = {
        "id": sid,
        "name": name or f"会话 {_safe_name(sid)}",
        "created": time.time(),
        "updated": time.time(),
        "path": str(folder),
    }
    _save_meta(sid, meta)
    (folder / "messages.json").write_text("[]", encoding="utf-8")
    (folder / "chat.md").write_text(f"# {meta['name']}\n\n", encoding="utf-8")
    return meta


def get_messages(sid):
    folder = _resolve_folder(sid)
    mp = folder / "messages.json"
    if not mp.exists():
        return []
    try:
        return json.loads(mp.read_text(encoding="utf-8"))
    except Exception:
        return []


def append_message(sid, role, content):
    """追加一条消息并同步写入项目文件夹里的 md/json，更新 updated 时间。"""
    folder = _resolve_folder(sid)
    msgs = get_messages(sid)
    msg = {"role": role, "content": content, "ts": time.time()}
    msgs.append(msg)
    (folder / "messages.json").write_text(json.dumps(msgs, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(folder / "chat.md", "a", encoding="utf-8") as f:
        prefix = "**用户**" if role == "user" else "**AI**"
        f.write(f"\n{prefix}：\n\n{content}\n")
    # 更新 meta
    meta = _load_meta(sid)
    if meta:
        meta["updated"] = time.time()
        _save_meta(sid, meta)
    return msg


def rename_session(sid, new_name):
    meta = _load_meta(sid)
    if meta:
        meta["name"] = new_name
        _save_meta(sid, meta)


def change_session_folder(sid, new_path):
    """更改会话的项目文件夹到 new_path。

    会把原项目文件夹里的 messages.json / chat.md 等数据复制到新位置。
    若新位置已有同名文件，先备份为 *.bak 再覆盖，避免误丢数据。
    返回 (ok, msg)。
    """
    try:
        old_folder = _resolve_folder(sid, ensure=False)
        new_folder = Path(new_path).expanduser().resolve()
        if old_folder == new_folder:
            return True, "新路径与当前路径相同，无需更改"
        new_folder.mkdir(parents=True, exist_ok=True)

        # 迁移数据文件（只迁移已知数据文件，不动用户其他文件）
        files = ["messages.json", "chat.md"]
        for fname in files:
            src = old_folder / fname
            if not src.exists():
                continue
            dst = new_folder / fname
            if dst.exists():
                shutil.copy2(str(dst), str(dst) + ".bak")
            shutil.copy2(str(src), str(dst))

        # 更新 meta 的 path
        meta = _load_meta(sid)
        if meta:
            meta["path"] = str(new_folder)
            meta["updated"] = time.time()
            _save_meta(sid, meta)
        return True, f"项目文件夹已迁移到：{new_folder}"
    except Exception as e:
        return False, f"迁移失败：{e}"


def delete_session(sid):
    """删除会话索引（data/sessions/<sid>/）。

    注意：为安全起见，只删除内部索引目录，不会删除用户自定义的外部项目文件夹。
    """
    folder = SESSIONS_DIR / sid
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)


def get_session_folder(sid):
    """返回会话当前使用的项目文件夹 Path。"""
    return _resolve_folder(sid)
