# -*- coding: utf-8 -*-
"""Android 手机能力层（剪贴板 / 打开文件 / 打开应用 / 权限 / 分享 / 外部存储路径）。

用途：
1. 解决「手机上不能粘贴 API Key / 文字」：提供 paste_text() / copy_text()，
   优先用 Kivy 内置 Clipboard（Android 走 pyjnius），失败再尝试原生 pyjnius。
2. 让 AI 能操作手机：在 Android 的 Python 执行环境里注入本模块为 `phone`，
   AI 可调用 phone.open_file(...) 用系统应用打开文件、phone.open_app(...) 打开应用、
   phone.share_text(...) 分享、phone.copy_text(...)/paste_text() 读写剪贴板。
3. 动态请求存储权限（Android 6+/11+ 需要运行时授权才能读写外部存储）。
4. 提供外部存储常见路径（Download / Documents / Pictures / DCIM 等），
   便于 AI 与用户在手机可见目录交换文件。

所有函数都 try/except 包裹，桌面端（Windows/Linux）导入不会报错、调用返回提示。
"""
import os
import sys

ANDROID = "ANDROID_ARGUMENT" in os.environ or os.environ.get("KIVY_BUILD") == "android"


def _clipboard():
    """返回 kivy.core.clipboard.Clipboard（Android 上自动走 pyjnius provider）。"""
    try:
        from kivy.core.clipboard import Clipboard
        return Clipboard
    except Exception:
        return None


def paste_text() -> str:
    """读取系统剪贴板文本。失败返回空串。"""
    try:
        cb = _clipboard()
        if cb is not None:
            t = cb.paste()
            if t:
                return str(t)
    except Exception:
        pass
    # 原生 pyjnius 兜底（Android）
    if ANDROID:
        try:
            from jnius import autoclass
            CM = autoclass("android.content.ClipboardManager")
            Context = autoclass("org.kivy.android.PythonActivity")
            cm = CM(Context.mActivity.getSystemService(Context.CLIPBOARD_SERVICE))
            clip = cm.getPrimaryClip()
            if clip and clip.getItemCount() > 0:
                return str(clip.getItemAt(0).coerceToText(Context.mActivity))
        except Exception:
            pass
    return ""


def copy_text(text: str) -> bool:
    """写入系统剪贴板。成功返回 True。"""
    if not text:
        return False
    try:
        cb = _clipboard()
        if cb is not None:
            cb.copy(text)
            return True
    except Exception:
        pass
    if ANDROID:
        try:
            from jnius import autoclass
            CM = autoclass("android.content.ClipboardManager")
            Context = autoclass("org.kivy.android.PythonActivity")
            cm = CM(Context.mActivity.getSystemService(Context.CLIPBOARD_SERVICE))
            cm.setPrimaryClip(CM.ClipData.newPlainText("text", text))
            return True
        except Exception:
            pass
    return False


# ---------------- Intent：打开文件 / 打开应用 / 分享 ----------------

def open_file(path: str) -> str:
    """用系统默认应用打开文件（图片/PDF/文档/视频等）。

    Android 上通过 ACTION_VIEW + file:// URI 启动系统应用。
    返回 "" 表示成功，否则返回错误信息。
    """
    if not path or not os.path.exists(path):
        return f"文件不存在：{path}"
    if not ANDROID:
        try:
            os.startfile(path)  # Windows
            return ""
        except Exception as e:
            return f"打开失败：{e}"
    try:
        from jnius import autoclass
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        File = autoclass("java.io.File")
        Context = autoclass("org.kivy.android.PythonActivity")
        intent = Intent(Intent.ACTION_VIEW)
        intent.setDataAndType(Uri.fromFile(File(path)), "*/*")
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        Context.mActivity.startActivity(intent)
        return ""
    except Exception as e:
        return f"打开失败：{e}"


def open_app(package: str) -> str:
    """打开其他应用，如 phone.open_app('com.tencent.mm')。

    package 可以是包名（走 MAIN 启动），也可以是 http(s):// 链接（走浏览器/微信等）。
    返回 "" 表示成功，否则返回错误信息。
    """
    if not package:
        return "未指定包名/链接"
    if not ANDROID:
        return f"桌面端不能打开手机应用；包名：{package}"
    try:
        from jnius import autoclass
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        Context = autoclass("org.kivy.android.PythonActivity")
        intent = Intent()
        if package.startswith(("http://", "https://")):
            intent.setAction(Intent.ACTION_VIEW)
            intent.setData(Uri.parse(package))
        else:
            intent.setAction(Intent.ACTION_MAIN)
            intent.setClassName(package, "android.app.Activity")
            intent.addCategory(Intent.CATEGORY_LAUNCHER)
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        Context.mActivity.startActivity(intent)
        return ""
    except Exception as e:
        return f"打开应用失败：{e}"


def share_text(text: str) -> str:
    """调起系统分享（发送文字到微信/QQ 等）。返回 "" 表示成功。"""
    if not text:
        return "没有可分享的内容"
    if not ANDROID:
        return f"桌面端不支持分享弹窗；内容长度：{len(text)}"
    try:
        from jnius import autoclass
        Intent = autoclass("android.content.Intent")
        Context = autoclass("org.kivy.android.PythonActivity")
        intent = Intent(Intent.ACTION_SEND)
        intent.setType("text/plain")
        intent.putExtra(Intent.EXTRA_TEXT, text)
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        chooser = Intent.createChooser(intent, "分享到…")
        chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        Context.mActivity.startActivity(chooser)
        return ""
    except Exception as e:
        return f"分享失败：{e}"


# ---------------- 权限 ----------------

def request_permissions() -> list:
    """动态请求 Android 存储权限（6+/11+ 运行时授权）。返回未授权的列表（空=已全部授权）。"""
    if not ANDROID:
        return []
    try:
        from android.permissions import request_permissions, Permission
        perms = [
            Permission.READ_EXTERNAL_STORAGE,
            Permission.WRITE_EXTERNAL_STORAGE,
            Permission.MANAGE_EXTERNAL_STORAGE,
        ]
        request_permissions(perms)
        return []
    except Exception:
        # MANAGE_EXTERNAL_STORAGE 在某些 Android 版本/模拟器上不在 Permission 枚举里，降级重试
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.READ_EXTERNAL_STORAGE,
                                 Permission.WRITE_EXTERNAL_STORAGE])
            return []
        except Exception:
            return ["storage"]


# ---------------- 外部存储路径 ----------------

def external_storage() -> str:
    """返回外部存储根目录（/storage/emulated/0），不存在则返回 app 私有目录。"""
    for p in ("/storage/emulated/0", "/sdcard", os.path.expanduser("~")):
        if os.path.isdir(p):
            return p
    return os.path.expanduser("~")


def download_dir() -> str:
    """Download 目录（手机用户可见），不存在则自动创建。"""
    d = os.path.join(external_storage(), "Download")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def documents_dir() -> str:
    """Documents 目录。"""
    d = os.path.join(external_storage(), "Documents")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def pictures_dir() -> str:
    """Pictures 目录。"""
    d = os.path.join(external_storage(), "Pictures")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def dcim_dir() -> str:
    """DCIM 目录。"""
    d = os.path.join(external_storage(), "DCIM")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def app_dir() -> str:
    """应用私有数据目录（无需权限、始终可写）。"""
    if ANDROID:
        return os.environ.get("ANDROID_ARGUMENT", os.path.expanduser("~"))
    return os.path.expanduser("~")


def summary() -> str:
    """给 AI 看的能力说明。"""
    lines = [
        "phone 能力（Android 手机）：",
        f"- phone.external_storage() 外部存储根目录：{external_storage()}",
        f"- phone.download_dir() 下载目录：{download_dir()}",
        f"- phone.app_dir() 应用私有目录：{app_dir()}",
        "- phone.open_file(path) 用系统应用打开文件（图片/PDF/文档等）",
        "- phone.open_app('包名') 打开其他应用，如 com.tencent.mm（微信）、com.android.browser；也支持传入 http(s) 链接",
        "- phone.share_text('内容') 调起系统分享（发微信/QQ）",
        "- phone.copy_text('内容') 复制到剪贴板；phone.paste_text() 读取剪贴板",
        "- 文件读写/创建目录/删除/移动：直接用 Python 的 open/os/shutil，私有目录与已授权的外部目录均可",
    ]
    return "\n".join(lines)
