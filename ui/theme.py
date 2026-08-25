"""主题/配色（Kivy 版）。字段名与桌面版 theme.THEMES 保持一致。
同时提供全局字号缩放 fs()，让"设置-正文字号"能联动所有界面。"""
from kivy.utils import get_color_from_hex
from kivy.metrics import dp

THEMES = {
    "dark": {
        "bg": "#0f1115", "panel": "#1a1d24", "panel2": "#222631", "panel3": "#2a2f3a",
        "panel4": "#323845", "border": "#33384a", "text": "#e6e8ee", "text_dim": "#9aa0ad",
        "accent": "#4f8cff", "accent2": "#7c5cff", "user_bubble": "#2d4a7a",
        "ai_bubble": "#232733", "danger": "#ff5b5b", "ok": "#46d18b", "warn": "#ffb547",
    },
    "light": {
        "bg": "#f4f6fb", "panel": "#ffffff", "panel2": "#eef1f7", "panel3": "#e4e9f2",
        "panel4": "#dde3ee", "border": "#cfd6e4", "text": "#1b2030", "text_dim": "#5c6577",
        "accent": "#2f6bff", "accent2": "#6a47ff", "user_bubble": "#d6e4ff",
        "ai_bubble": "#eef1f7", "danger": "#e23b3b", "ok": "#1faa5b", "warn": "#d98a00",
    },
}

_current = "dark"

# 全局字号缩放：以 16px 为基准，fs(16) 等于设置里选中的字号；
# 所有界面统一用 fs(n) 代替写死的 dp(n)，改字号时全界面联动。
FONT_SCALE = 1.0


def set_font_scale(size_px):
    global FONT_SCALE
    try:
        size_px = float(size_px)
    except Exception:
        size_px = 16
    if size_px <= 0:
        size_px = 16
    FONT_SCALE = size_px / 16.0


def fs(n):
    """按当前字号比例返回像素值，供 KV 与 Python 共用。"""
    return dp(n * FONT_SCALE)


def set_theme(name):
    global _current
    if name in THEMES:
        _current = name


def theme():
    return THEMES[_current]


def get_theme_name():
    return _current


def C(key):
    """返回 Kivy 颜色元组（RGBA 0~1）。"""
    return get_color_from_hex(theme()[key])


def H(key):
    """返回十六进制颜色字符串。"""
    return theme()[key]
