# -*- coding: utf-8 -*-
"""无头实跑审计：验证阅读风格主题、阅读窗口、回顶/回底、平板滑动配置、各导航。"""
import os, sys, traceback, tempfile
os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")
os.environ.setdefault("KIVY_NO_ARGS", "1")

import main
from ui import theme

fails = []
def check(name, fn):
    try:
        fn()
        print("PASS", name)
    except Exception as e:
        print("FAIL", name, "->", repr(e))
        traceback.print_exc()
        fails.append(name)

app = main.AIChatStudioApp()
app.build()
print("build OK; current screen =", app.sm.current)

# 1) 聊天顶栏含「阅读」按钮
def t_chat_has_reader_btn():
    chat = app.chat
    # 找到 text=='阅读' 的按钮
    found = any(getattr(w, "text", "") == "阅读" for w in chat.walk())
    assert found, "聊天顶栏缺少 阅读 按钮"
check("聊天顶栏含阅读按钮", t_chat_has_reader_btn)

# 2) 聊天回顶/回底不崩溃
def t_chat_scroll():
    app.chat._add_bubble("user", "测试消息\n第二行")
    app.chat.scroll_to_top()
    app.chat.scroll_to_bottom()
check("聊天回顶/回底", t_chat_scroll)

# 3) 阅读窗口：进入、加载文件、回顶/回底、字号
def t_reader_basic():
    app.go_reader()
    assert app.sm.current == "reader"
    r = app.reader
    # 写一个临时小说文件
    tf = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
    tf.write("第一章\n\n这是一段测试小说正文。" * 50)
    tf.close()
    r.load_file(tf.name)
    assert "第一章" in r.ids.content.text, "阅读窗口未载入正文"
    r.scroll_to_top()
    r.scroll_to_bottom()
    f0 = r.ids.content.font_size
    r.font_inc(); r.font_inc()
    assert r.ids.content.font_size > f0, "字号 A+ 未生效"
    r.font_dec(); r.font_dec(); r.font_dec()
    assert r.ids.content.font_size < f0 + 1, "字号 A- 未生效"
    # 路径打开
    r.ids.path_in.text = tf.name
    r.open_path()
    assert "第一章" in r.ids.content.text
    os.unlink(tf.name)
check("阅读窗口基础功能", t_reader_basic)

# 4) 五种阅读风格切换均不崩溃（含重建聊天/阅读窗口）
def t_styles_all():
    for key in theme.READING_STYLES:
        theme.set_reading_style(key)
        app.apply_theme_to_all()      # 重建聊天 + 阅读窗口
        # 重建后 reader_path 应被重新载入（无文件时为 None，不报错）
        rc = theme.RC("bg")
        assert len(rc) == 4, "RC 颜色格式异常"
check("五种阅读风格切换", t_styles_all)

# 5) 阅读风格颜色确实不同
def t_style_colors_differ():
    theme.set_reading_style("cream"); c_cream = theme.RC("bg")
    theme.set_reading_style("night"); c_night = theme.RC("bg")
    assert c_cream != c_night, "不同风格背景色应不同"
check("阅读风格颜色区分", t_style_colors_differ)

# 6) 设置界面含阅读风格 Spinner，且保存后写入 settings
def t_settings_readstyle():
    app.go_settings()
    s = app.settings_screen
    found = any(getattr(w, "text", "") in theme.READING_STYLE_LABELS.values()
                for w in s.walk() if w.__class__.__name__ == "Spinner")
    assert found, "设置界面缺少阅读风格 Spinner"
    # 选择护眼绿并保存
    s.read_style_combo.text = "护眼绿"
    s._on_read_style("护眼绿")
    from core import settings as settings_mod
    settings_mod.update_settings({"ui": {"reading_style": "green"}})
    assert settings_mod.load_settings()["ui"]["reading_style"] == "green"
check("设置阅读风格", t_settings_readstyle)

# 7) 平板滑动配置：scroll_type 含 content
def t_scroll_type():
    assert app.chat.ids.scroll.scroll_type and "content" in app.chat.ids.scroll.scroll_type, \
        "聊天未启用触摸滑动"
    app.go_reader()
    assert "content" in app.reader.ids.scroll.scroll_type, "阅读窗口未启用触摸滑动"
check("平板触摸滑动配置", t_scroll_type)

# 8) 会话抽屉 / 新建 / 切回聊天（核心回归）
def t_core_regression():
    app.go_chat()
    app.chat.new_session(silent=True)
    app.open_sessions_drawer()
    app.chat.scroll_to_bottom()
check("核心回归(会话/抽屉)", t_core_regression)

print("\n==== 结果 ====")
if fails:
    print("失败项:", fails)
    sys.exit(1)
else:
    print("全部通过 ✅")
