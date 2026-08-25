[app]

# (str) 应用标题
title = AI Chat Studio

# (str) 包名（小写，唯一）
package.name = aichatstudio
# (str) 包域名（反向，用作 applicationId 前缀）
package.domain = com.aichatstudio

# (str) 源码目录
source.dir = .
# (list) 包含的扩展名（务必含 ttc/ttf，否则中文字体不会被打进 APK，手机端中文会变方块）
source.include_exts = py,png,jpg,kv,json,txt,md,ttc,ttf
# (list) 排除（避免把本地 venv/缓存打进包）
source.exclude_dirs = env,venv,penv,pylibs,build,dist,.git,__pycache__
source.exclude_patterns = *.pyc,*.pyo,*/__pycache__/*

# (str) 主程序
source.main = main.py

# (list) 依赖（python-for-android 会交叉编译）
requirements = python3==3.11.10,kivy==2.3.0,plyer,requests

# (str) 开发版本号
version = 1.0.0

# (str) 应用图标（可选，放在 assets/ 下；没有则用默认）
# icon.filename = %(source.dir)s/assets/icon.png
# presplash.filename = %(source.dir)s/assets/presplash.png

# (str) 横竖屏：portrait / landscape / sensor
orientation = portrait

# (list) Android 权限
# INTERNET 必需（调用 AI API）；存储权限用于把文件保存到本机可见目录
android.permissions = INTERNET, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE
android.api = 34
android.minapi = 21
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a

# (bool) 是否以调试模式构建（生成可安装的 debug apk）
android.debug = True

# (str) 使用的 p4a 分支
p4a.branch = master

# (bool) 为 SDK 工具关闭监控
android.skip_scan_for_dynamic_symbols = True

[buildozer]

# (int) 构建超时（秒）
buildozer.bin = buildozer
log_level = 2
warn_on_root = 1
