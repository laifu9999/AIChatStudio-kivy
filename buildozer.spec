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
# (list) 排除（避免把本地 venv/缓存/原生工程打进包）
source.exclude_dirs = env,venv,penv,pylibs,build,dist,.git,__pycache__,android-native
source.exclude_patterns = *.pyc,*.pyo,*/__pycache__/*

# (str) 主程序
source.main = main.py

# (list) 依赖（python-for-android 会交叉编译）
requirements = hostpython3==3.11.10,python3==3.11.10,kivy==2.3.0,plyer,requests

# (str) 开发版本号
version = 1.0.1

# (str) 应用图标（可选，放在 assets/ 下；没有则用默认）
# icon.filename = %(source.dir)s/assets/icon.png
# presplash.filename = %(source.dir)s/assets/presplash.png

# (str) 横竖屏：portrait / landscape / sensor
orientation = portrait

# (list) Android 权限
# INTERNET：调用 AI API；存储权限：读写手机文件（Android 6+ 运行时还会弹窗授权；
# MANAGE_EXTERNAL_STORAGE 用于 Android 11+「所有文件访问」（需用户在系统设置手动开启）；
# REQUEST_INSTALL_PACKAGES：允许安装 APK（debug 包本地安装用）。
android.permissions = INTERNET, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, \
    MANAGE_EXTERNAL_STORAGE, REQUEST_INSTALL_PACKAGES, VIBRATE, WAKE_LOCK
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

# Android 9+ 默认禁止明文 HTTP；开启后允许 http:// 接口（如本地 Ollama / 内网 API）。
# 注意：该配置项的值是【文件路径】——buildozer 会把文件内容插入 <application> 标签，
# 不能直接写属性文本（之前写成 usesCleartextTraffic=true 导致 FileNotFoundError）。
android.extra_manifest_application_arguments = android_manifest_application_args.xml

# (bool) 允许备份/恢复应用数据
android.allow_backup = True

[buildozer]

# (int) 构建超时（秒）
buildozer.bin = buildozer
log_level = 2
warn_on_root = 1
