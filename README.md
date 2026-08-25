# AIChatStudio（Kivy 跨平台版）

用 **Kivy** 重写的 AI Chat Studio，同一份代码在 **Windows / Linux / Android** 上运行，
功能与界面保持一致，可打包成 **APK** 在手机上使用。

核心能力（电脑与手机一致）：
- 多模型 AI 聊天（OpenAI 兼容协议：DeepSeek / 智谱 GLM / 通义 / 文心 / Claude 等）
- **按你的意思显示并保存文件**：AI 用 `%%FILE:相对路径%%正文%%` 标记，程序自动把正文保存到
  当前会话项目文件夹（父目录自动创建，UTF-8 无 BOM，正文只写一遍）
- 代码块文件操作：`file` / `replace` / `append` / `delete` / `create_dir` / `savebody`
- 跨平台命令执行：`python` 代码块用本机 Python 运行（电脑/手机同一环境）
- 会话管理、设置（API/模型/主题/字号）、工具面板（项目 / 自动化 / 爬取）、投喂（Feed）

> 说明：原桌面版的「PowerShell/CMD 命令」与「pyautogui 键鼠自动化」依赖 Windows 桌面环境，
> 在手机上无对应能力，因此统一改为 **Python 执行 / Python 脚本自动化**，保证两端行为一致。

## 一、在电脑上运行（Windows）

直接用 `run.bat`（首次会自动建虚拟环境并装依赖）：

```
双击 run.bat
```

或手动：

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

> 若 `pip install kivy` 很慢，可加国内镜像：
> `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

## 二、打包成 Android APK

本机（Windows）没有 WSL/Linux 无法本地出包，已配好 **GitHub Actions 云端构建**：
把本仓库推送到 GitHub，Actions 会自动用 buildozer 编译出 `bin/*.apk`，到 Actions 页面下载即可安装到手机。

```bash
git init
git remote add origin <你的仓库地址>
git add -A
git commit -m "AIChatStudio kivy"
git push
```

随后在 GitHub 仓库 → Actions → "Build Android APK" → 下载产物 `AIChatStudio-apk`。

本地若有 Linux/WSL，也可直接：

```bash
pip install buildozer Cython==0.29.33
buildozer android debug
# 产物在 bin/AIChatStudio-*-debug.apk
```

### 手机上的存储位置
- 数据与会话默认保存在应用私有目录（`ANDROID_ARGUMENT`，无需任何存储权限即可读写）。
- 如需把文件保存到手机可见的「下载/文档」，可在系统设置里给应用「文件管理」权限，
  或在「工具→项目」里通过系统文件选择器导出。

## 三、目录结构

```
core/        跨平台核心：config(路径/提示词) ai_client(模型调用) session settings content_feed
modules/     code_tools(文件标记解析/应用) command_exec(跨平台执行) web_scraper(爬取) automation(脚本运行)
ui/          theme(配色) chat_screen settings_screen tools_screen feed_screen
main.py      入口（ScreenManager 组装四屏 + 会话抽屉 + 主题切换）
buildozer.spec        APK 构建配置
.github/workflows/    GitHub Actions 云端出包
```

## 四、与桌面 PyQt5 版的关系
逻辑层（`core/`、`modules/`）直接复用原 `C:/2/ai_chat_app` 的纯 Python 实现；
UI 用 Kivy 重写；文件保存统一走跨平台的 `%%FILE:` 标记 + `apply_blocks`，
因此「在手机上对文件各种操作和按你的意思显示、保存」与电脑完全一致。
