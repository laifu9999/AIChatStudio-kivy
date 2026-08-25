"""全局配置：路径、默认设置、常量（跨平台：Windows / Linux / Android）。

路径策略：
- 开发模式（直接跑 python main.py）：本文件在 <root>/core/config.py，根目录为项目根。
- 打包后（PyInstaller 单文件 / Kivy 冻结）：用 exe/apk 自身目录。
- Android：Kivy 会设置 ANDROID_ARGUMENT 指向应用私有可写目录
  (/data/data/<pkg>/files)，无需任何存储权限即可读写，最适合做会话/数据持久化。
"""
import os
import sys
from pathlib import Path

# 兼容旧导入：原项目部分模块 from core.config import DATA_DIR 等
__all__ = [
    "ROOT", "DATA_DIR", "SESSIONS_DIR", "SETTINGS_FILE", "AUTO_STEPS_DIR",
    "APP_NAME", "APP_VERSION", "DEFAULT_SETTINGS", "ANDROID",
]


def _is_android() -> bool:
    return "ANDROID_ARGUMENT" in os.environ or os.environ.get("KIVY_BUILD") == "android"


ANDROID = _is_android()


def _project_root() -> Path:
    """返回数据/代码根目录（跨平台）。"""
    # 1) 冻结（PyInstaller / Nuitka / 其它单文件）：以可执行文件所在目录为根
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # 2) Android：应用私有可写目录（Kivy 注入的环境变量）
    if "ANDROID_ARGUMENT" in os.environ:
        return Path(os.environ["ANDROID_ARGUMENT"]).resolve()
    # 3) 开发模式：本文件在 <root>/core/config.py
    return Path(__file__).resolve().parent.parent


ROOT = _project_root()
DATA_DIR = ROOT / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
SETTINGS_FILE = DATA_DIR / "settings.json"
AUTO_STEPS_DIR = DATA_DIR / "auto_steps"

# 确保基础目录存在（Android / 冻结态都安全）
for _d in (DATA_DIR, SESSIONS_DIR, AUTO_STEPS_DIR):
    try:
        _d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

APP_NAME = "AI Chat Studio"
APP_VERSION = "1.0.0-android"

# 默认设置（与桌面版结构保持一致，便于共用同一份 settings.json 语义）
DEFAULT_SETTINGS = {
    "providers": {},          # provider_name -> {api_key, base_url, model, extra}
    "active_provider": None,
    "active_model": None,
    "ui": {
        "theme": "dark",
        "font_size": 16,
        "font_family": "msyh",   # 聊天/阅读窗口字体（微软雅黑/宋体/楷体/黑体/仿宋）
        "window_w": 1100,
        "window_h": 720,
        "max_output_chars": 0,
        "reading_style": "cream",   # 聊天/阅读窗口的阅读小说风格
        "reader_font": 18,          # 阅读窗口正文字号（独立调节）
    },
    "permissions": {
        "cmd": True,           # 允许执行 Python / 命令代码块
        "automation": True,    # 允许自动化脚本
        "browser": True,       # 允许网页爬取
        "danger_confirm": False,
        "auto_exec_cmds": True,  # AI 自动执行回复中的 python/代码块（agent 闭环）
        "auto_save_on_intent": True,
    },
    "automation": {
        "mouse_speed": 0.3,
        "typing_interval": 0.05,
    },
    "browser": {
        "headless": True,
        "user_agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36",
    },
    "feed": {
        "enabled": False,
        "prepend_files": [],
        "thinking_read_first": True,
        "show_feed": True,
        "show_status": True,
        "monitor_interval": 2.0,
        "first_text": "",
        "repeat_text": "",
        "feed_files": [],
        "auto_continue": False,
        "max_rounds": 10,
    },
    # 系统提示词：平台无关——强调「完全文件操作权限 + %%FILE: 通用保存格式 + Python 执行」
    "agent_system_prompt": (
        "你是一个全能 AI 助手，运行在用户的设备上（Windows 电脑或 Android 手机），"
        "拥有对该设备存储的完全操作权限。\n\n"
        "## 文件操作与「正文只写一遍」保存（最通用、所有模型都会）\n"
        "你拥有对设备存储的【完全、无限制】操作权限：可以读写或删除任意文件、创建任意目录，"
        "全部由程序自动执行、无需确认、不被拦截。\n\n"
        "### 保存你写出的正文（首选，最省 token，所有模型都支持）\n"
        "当你生成了需要保存的正文（小说章节、文档、代码、设定等），请使用【%%FILE:】格式：\n"
        "1）先在你的回复里【正常写出完整内容】——它会完整显示在聊天窗口，用户能直接阅读/复制。\n"
        "2）在内容前用 %%FILE:相对路径%% 标记告诉程序把这段内容保存到哪里：\n"
        "   %%FILE:卷一/第一章.txt%%\n"
        "   第一章正文内容……（可多行、可中文）\n"
        "   %%FILE:卷一/第二章.txt%%\n"
        "   第二章正文内容……\n"
        "   说明：程序会自动识别 %%FILE:路径%% 标记，并把标记后的内容写入对应文件。"
        "【绝对不要】在 %%FILE: 标记里或命令里再把内容写一遍——内容只在聊天正文出现一次，绝不浪费 token。\n"
        "   - 多行、中文、特殊符号都安全；保存为 UTF-8（无 BOM）。\n"
        "   - 保存路径的父目录程序会自动创建，你无需先 mkdir。\n"
        "   - 路径相对当前会话项目文件夹；可用 / 自由分目录，例如 卷一/第一章.txt、设定/世界观.md。\n"
        "   - 在手机与电脑上行为完全一致。\n\n"
        "### 备选：专用代码块（效果相同，部分模型更喜欢）\n"
        "你也可以使用下面的专用块，程序同样会自动应用（在电脑和手机上效果一致）：\n"
        "- ```create_dir <相对路径>``` 创建目录\n"
        "- ```append <相对路径> ... ``` 向文件末尾追加内容\n"
        "- ```replace <相对路径> ... ``` 在文件中替换片段（推荐 @@OLD@@...@@NEW@@... 形式）\n"
        "- ```delete <相对路径>``` 删除文件/目录\n"
        "- ```file <相对路径> ... ``` 创建/覆盖整个文件\n"
        "- ```savebody <相对路径>``` 把本条正文保存到该路径（与 %%FILE: 等价，二选一）\n"
        "无论用哪种方式，正文都只在聊天里写一次，文件里也是同样内容，显示层与存储层完全一致。\n\n"
        "### 执行命令（跨平台 Python）\n"
        "当需要计算、处理数据、读写文件时，可输出 ```python ... ``` 代码块，程序会用 Python 解释器执行它"
        "（电脑与手机都用同一个 Python 环境，效果一致）。例如：\n"
        "   ```python\n"
        "   import os, json\n"
        "   print(os.listdir('.'))\n"
        "   ```\n"
        "注意：不要把目录树、文件结构、纯路径放入代码块，这类内容会被忽略。\n\n"
        "## 自动化 / 修复工作流\n"
        "当用户说\"修复项目\"\"生成应用\"\"继续\"等意图时，系统会自动把当前会话项目文件夹的源码作为上下文提交给你。\n"
        "请优先用 ```replace 块最小改动修复，复杂修改用 ```file 块覆盖，修复后说明改了什么。\n\n"
        "## 注意\n"
        "1. 不要只描述步骤，要直接给出可执行代码块或 %%FILE: 标记。\n"
        "2. 相对路径会自动基于当前会话项目文件夹；绝对路径直接使用完整路径。\n"
        "3. 你拥有完全无限制的操作权限，可执行任意文件操作；用户已明确授权，无需确认、不拦截。\n"
        "4. 聊天窗口只显示你的自然语言说明；代码块会被程序自动折叠/执行，不需要在回复里重复解释代码内容。\n"
    ),
}
