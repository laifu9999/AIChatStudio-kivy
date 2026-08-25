"""跨平台自动化模块。

为保持「电脑与手机功能一致」，自动化改为【Python 脚本运行器】：
用户在工具面板「自动化」页写一段 Python 脚本（可做文件批量处理、数据整理、
调用 AI 等），点击运行后在后台执行，日志实时回显。电脑与手机用同一套 Python，效果一致。
（原桌面版的 pyautogui 键鼠模拟依赖屏幕坐标系，在手机上无对应能力，这里不再使用。）
"""
import subprocess
import sys
import os
import threading

_exec_lock = threading.Lock()


def available():
    """Python 执行器始终可用（跨平台）。"""
    return True


def run_script(code, cfg=None, cwd=None, on_log=None, timeout=300):
    """在后台执行一段 Python 脚本，实时回调 on_log(line)。

    返回日志字符串列表。任何异常都会被捕获，绝不抛出。
    """
    logs = []
    def _log(line):
        logs.append(line)
        if on_log:
            try:
                on_log(line)
            except Exception:
                pass

    try:
        env = os.environ.copy()
        if isinstance(cfg, dict):
            # 把配置以环境变量形式暴露给脚本，便于读取
            for k, v in cfg.items():
                try:
                    env["AUTO_" + str(k).upper()] = str(v)
                except Exception:
                    pass
        with _exec_lock:
            proc = subprocess.run(
                [sys.executable, "-c", code],
                cwd=cwd or None, capture_output=True,
                timeout=timeout, env=env,
            )
        out = _decode(proc.stdout)
        err = _decode(proc.stderr)
        if out:
            for line in out.splitlines():
                _log(line)
        if err:
            for line in err.splitlines():
                _log("[失败] " + line)
        if proc.returncode != 0:
            _log(f"[结束] 返回码 {proc.returncode}")
        else:
            _log("[结束] 脚本执行完成 [OK]")
        return logs
    except subprocess.TimeoutExpired:
        _log(f"[失败] 执行超时（>{timeout}s）")
        return logs
    except Exception as e:
        _log(f"[失败] 执行异常：{e}")
        return logs


def _decode(data: bytes) -> str:
    if not data:
        return ""
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")
