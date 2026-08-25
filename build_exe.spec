# -*- mode: python ; coding: utf-8 -*-
# AIChatStudio Kivy 版 —— 单文件 exe 打包配置（Windows）
# 用法：pyinstaller build_exe.spec
import os

# 规避沙箱环境对 PE 时间戳写入的拦截（PermissionError: Permission denied），
# 该步骤仅设置 PE 头的编译时间戳（用于可复现构建），跳过不影响 exe 功能。
try:
    import PyInstaller.utils.win32.winutils as _wu
    _wu.set_exe_build_timestamp = lambda *a, **k: None
except Exception:
    pass

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=[
        'kivy',
        'kivy.core.window', 'kivy.core.text', 'kivy.core.image', 'kivy.core.clipboard',
        'kivy.input.providers', 'kivy.input.providers.mouse', 'kivy.input.providers.tuio',
        'kivy.uix.filechooser',
        'core', 'core.session', 'core.settings', 'core.config', 'core.ai_client', 'core.content_feed',
        'modules', 'modules.code_tools', 'modules.command_exec', 'modules.web_scraper', 'modules.automation',
        'ui', 'ui.chat_screen', 'ui.settings_screen', 'ui.tools_screen', 'ui.feed_screen',
        'ui.reader_screen', 'ui.theme',
        'requests', 'urllib3', 'certifi',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'tkinter',
              'matplotlib', 'scipy', 'numpy', 'pandas', 'PIL.ImageQt'],
    win_no_prefetch=True,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AIChatStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    windowed=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
