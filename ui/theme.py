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
        "ai_bubble": "#eef1f7",         "danger": "#e23b3b", "ok": "#1faa5b", "warn": "#d98a00",
    },
}

# ---- 阅读小说风格（用于聊天界面与阅读窗口）----
# 每种风格模拟一种实体书／护眼屏的观感：米黄纸、护眼绿、夜间、羊皮卷、简约白。
READING_STYLES = {
    "cream": {  # 米黄纸（暖色书页，最像纸质小说）
        "bg": "#f3ead3", "panel": "#e9dcbd", "panel2": "#efe3c8", "panel3": "#e2d2ad",
        "panel4": "#d8c39a", "border": "#cdb78f", "text": "#43361f", "text_dim": "#84714a",
        "accent": "#9c6b3f", "user_bubble": "#e4cfa0", "ai_bubble": "#f7f0df",
        "danger": "#b5472f", "ok": "#4f7a3a", "warn": "#b07b1e",
    },
    "green": {  # 护眼绿（豆绿底，长时间阅读不刺眼）
        "bg": "#c9e6cc", "panel": "#bcdcbf", "panel2": "#c4e2c7", "panel3": "#b3d6b7",
        "panel4": "#a6cbaa", "border": "#9bc0a0", "text": "#1f3d24", "text_dim": "#4f6b53",
        "accent": "#2e7d46", "user_bubble": "#aedcb1", "ai_bubble": "#e0f1e2",
        "danger": "#b5472f", "ok": "#2e7d46", "warn": "#b07b1e",
    },
    "night": {  # 夜间（近黑底浅字，暗光环境）
        "bg": "#14161b", "panel": "#1c1f27", "panel2": "#22262f", "panel3": "#282d38",
        "panel4": "#303642", "border": "#2c313c", "text": "#c9cdd8", "text_dim": "#7b8290",
        "accent": "#5b8def", "user_bubble": "#2a3550", "ai_bubble": "#1e222b",
        "danger": "#ff5b5b", "ok": "#46d18b", "warn": "#ffb547",
    },
    "parch": {  # 羊皮卷（棕黄做旧，复古阅读）
        "bg": "#e7d8b8", "panel": "#ddcaa3", "panel2": "#e3d4b6", "panel3": "#d4bf95",
        "panel4": "#c9b186", "border": "#bda77b", "text": "#4a3a24", "text_dim": "#806844",
        "accent": "#8a5a2f", "user_bubble": "#d8c096", "ai_bubble": "#f1e6cf",
        "danger": "#b5472f", "ok": "#4f7a3a", "warn": "#b07b1e",
    },
    "white": {  # 简约白（白底黑字，干净文档感）
        "bg": "#ffffff", "panel": "#f4f4f5", "panel2": "#eeeff1", "panel3": "#e6e8ec",
        "panel4": "#dde0e6", "border": "#d8dbe2", "text": "#202225", "text_dim": "#5c6577",
        "accent": "#2f6bff", "user_bubble": "#d8e4ff", "ai_bubble": "#f4f4f4",
        "danger": "#e23b3b", "ok": "#1faa5b", "warn": "#d98a00",
    },
}
READING_STYLE_LABELS = {
    "cream": "米黄纸", "green": "护眼绿", "night": "夜间", "parch": "羊皮卷", "white": "简约白",
}

_current = "dark"
_read = "cream"

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


# ---- 阅读风格（RC/RH 与 C/H 对应，但取 READING_STYLES）----
def set_reading_style(name):
    global _read
    if name in READING_STYLES:
        _read = name


def get_reading_style_name():
    return _read


def reading_style():
    return READING_STYLES[_read]


def RC(key):
    """阅读风格颜色元组（RGBA 0~1）。"""
    return get_color_from_hex(reading_style()[key])


def RH(key):
    """阅读风格十六进制颜色字符串。"""
    return reading_style()[key]


def reading_style_label(name=None):
    return READING_STYLE_LABELS.get(name or _read, name or _read)
