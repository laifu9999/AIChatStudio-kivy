"""跨平台命令/代码执行模块。

设计（按用户要求"在电脑与手机功能一致"）：
- 主路径是【Python 执行】：```python / ```py 代码块用本机 Python 解释器运行，
  电脑与手机用同一套 Python 环境，效果完全一致。
  - 桌面端：subprocess 调 sys.executable（独立进程、可超时强杀）。
  - Android：exec 内联执行（p4a 无可靠的可执行子进程），注入 os/shutil/phone(android_ops)，
    AI 可以操作文件、打开应用、读写剪贴板；线程运行 + 超时提示。
- 桌面端（Windows/Linux）额外兼容 ```cmd / ```powershell 代码块（直接交给系统 shell）。
- Android 端没有 cmd/powershell，这类块会被安全地跳过并提示，不会崩溃。
- 任何异常都被接住并返回结构化结果，绝不向上抛出（防止 UI 线程闪退）。
"""
import subprocess
import sys
import os
import re
import tempfile
import threading
from core.config import ANDROID

# 全局串行锁（避免并发写同一文件等冲突）
_exec_lock = threading.Lock()

# 极端指令拦截（这里按用户要求解除全部限制，恒放行）
def is_wipe(cmd):
    return False, ""

def is_destructive(cmd):
    return False, ""

# ----------------------- Python 执行（跨平台主路径） -----------------------
def _exec_env(code, body=None, cwd=None):
    """构造 Android 内联执行环境（含 phone 手机能力对象与常用库）。"""
    env = {
        "__name__": "__main__",
        "os": os, "sys": sys, "re": re, "tempfile": tempfile,
    }
    try:
        import shutil, json, time, math, random
        env.update({"shutil": shutil, "json": json, "time": time,
                    "math": math, "random": random})
    except Exception:
        pass
    if body is not None:
        env["CHAT_BODY"] = body
        code = code.replace("%%BODY%%", repr(body))
    # 注入 phone 手机能力（打开应用/文件/剪贴板/外部存储路径等）
    try:
        from modules import android_ops
        env["phone"] = android_ops
        env["android"] = android_ops
        env["__phone_summary__"] = android_ops.summary()
    except Exception:
        pass
    if cwd:
        try:
            os.chdir(cwd)
        except Exception:
            pass
    return env, code


def run_python_android(code, cwd=None, timeout=120, max_lines=5000, body=None):
    """Android 上用 exec 在同一进程内执行 Python 代码。

    优点：不依赖可执行的子进程二进制（p4a 环境无稳定 subprocess），
    环境与主程序完全一致，os/shutil/phone 全部可用。
    超时：在子线程运行，超时返回提示（线程无法强杀，但不会卡死 UI）。
    """
    import io
    import contextlib
    env, code = _exec_env(code, body=body, cwd=cwd)
    out_buf, err_buf = io.StringIO(), io.StringIO()
    result = {"ok": False, "stdout": "", "stderr": "", "returncode": -1}
    done = threading.Event()

    def _run():
        try:
            with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
                exec(compile(code, "<ai>", "exec"), env)
            result["ok"] = True
            result["returncode"] = 0
        except SystemExit as e:
            result["ok"] = (e.code in (None, 0))
            result["returncode"] = e.code if isinstance(e.code, int) else 0
        except Exception as e:
            import traceback
            err_buf.write(traceback.format_exc())
            result["returncode"] = -3
        finally:
            done.set()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    done.wait(timeout=timeout)
    stdout = out_buf.getvalue()
    stderr = err_buf.getvalue()
    if not done.is_set():
        return {"ok": False, "stdout": _truncate(stdout, max_lines),
                "stderr": f"执行超时（>{timeout}s）", "returncode": -2}
    result["stdout"] = _truncate(stdout, max_lines)
    result["stderr"] = stderr
    out = stdout + ("\n" + stderr if stderr else "")
    result["stdout"] = _truncate(out, max_lines)
    return result


def run_python(code, cwd=None, timeout=120, max_lines=5000, body=None):
    """用本机 Python 解释器执行一段代码，返回 {"ok","stdout","stderr","returncode"}。

    body：提供时把「本条消息正文」以变量 CHAT_BODY 注入，并把 %%BODY%% 占位符替换掉。
    这样 AI 只需在正文写一次内容，代码块是固定模板即可操作该正文（如保存处理）。
    Android：走 exec 内联（见 run_python_android）。
    """
    if ANDROID:
        return run_python_android(code, cwd=cwd, timeout=timeout,
                                  max_lines=max_lines, body=body)
    try:
        if body is not None:
            code = code.replace("%%BODY%%", repr(body))
        env = os.environ.copy()
        if body is not None:
            env["CHAT_BODY"] = body
        with _exec_lock:
            proc = subprocess.run(
                [sys.executable, "-c", code],
                cwd=cwd or None, capture_output=True,
                timeout=timeout, env=env,
            )
        stdout = _decode(proc.stdout)
        stderr = _decode(proc.stderr)
        out = stdout + ("\n" + stderr if stderr else "")
        return {"ok": proc.returncode == 0, "stdout": _truncate(out, max_lines),
                "stderr": stderr, "returncode": proc.returncode}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": f"执行超时（>{timeout}s）", "returncode": -2}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": f"执行异常：{e}", "returncode": -3}

# ----------------------- 系统 shell（仅桌面端） -----------------------
def run_command(cmd, cwd=None, timeout=120, max_lines=5000, body=None, shell="cmd"):
    """在桌面端执行 cmd / powershell / bash。Android 上直接返回提示。"""
    if ANDROID:
        return {"ok": False, "stdout": "",
                "stderr": "当前为 Android 环境，不支持系统 shell 命令；请改用 ```python 代码块。",
                "returncode": -1}
    try:
        if body is not None:
            code = cmd.replace("%%BODY%%", body)
        else:
            code = cmd
        env = os.environ.copy()
        if body is not None:
            env["CHAT_BODY"] = body
        with _exec_lock:
            proc = subprocess.run(
                code, shell=True, cwd=cwd or None, capture_output=True,
                timeout=timeout, env=env,
            )
        stdout = _decode(proc.stdout)
        stderr = _decode(proc.stderr)
        out = stdout + ("\n" + stderr if stderr else "")
        return {"ok": proc.returncode == 0, "stdout": _truncate(out, max_lines),
                "stderr": stderr, "returncode": proc.returncode}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": f"命令超时（>{timeout}s）", "returncode": -2}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": f"执行异常：{e}", "returncode": -3}

def powershell(cmd, cwd=None, timeout=120, max_lines=5000, body=None):
    """桌面端 PowerShell。Android 上返回提示。"""
    if ANDROID:
        return {"ok": False, "stdout": "",
                "stderr": "当前为 Android 环境，不支持 PowerShell；请改用 ```python 代码块。",
                "returncode": -1}
    # 用 -Command 直接跑；这里简单包一层 powershell.exe
    return run_command(f'powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "{cmd}"',
                       cwd=cwd, timeout=timeout, max_lines=max_lines, body=body)

# ----------------------- 统一分发 -----------------------
def run_block(lang, code, cwd=None, body=None):
    """根据语言分发到对应执行器。返回 (ok, out_text)。"""
    lang = (lang or "").lower().strip()
    if lang in ("python", "py", "py3"):
        res = run_python(code, cwd=cwd, body=body)
    elif lang in ("cmd", "batch", "sh", "bash", "shell"):
        res = run_command(code, cwd=cwd, body=body)
    elif lang in ("ps", "powershell", "ps1"):
        res = powershell(code, cwd=cwd, body=body)
    else:
        # 默认当 Python 跑（最安全、跨平台一致）
        res = run_python(code, cwd=cwd, body=body)
    out = res.get("stdout") or res.get("stderr") or "(无输出)"
    return res.get("ok", False), out, res

# ----------------------- 工具 -----------------------
def _decode(data: bytes) -> str:
    if not data:
        return ""
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk", "cp936"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")

def _truncate(out, max_lines):
    lines = out.splitlines()
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + f"\n... (输出过长，仅显示前 {max_lines} 行)"
    return out

def list_dir(path="."):
    try:
        p = os.path.expanduser(path)
        if not os.path.exists(p):
            return {"ok": False, "entries": [], "error": "路径不存在"}
        entries = []
        for c in sorted(os.listdir(p)):
            fp = os.path.join(p, c)
            entries.append({"name": c, "is_dir": os.path.isdir(fp),
                            "size": os.path.getsize(fp) if os.path.isfile(fp) else 0})
        return {"ok": True, "entries": entries, "error": ""}
    except Exception as e:
        return {"ok": False, "entries": [], "error": str(e)}

def write_file(path, content):
    try:
        p = os.path.expanduser(path)
        os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return {"ok": True, "error": ""}
    except Exception as e:
        return {"ok": False, "error": str(e)}
