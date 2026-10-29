"""设计系统的回归测试 —— 守的不是功能，是三个已经踩过的坑。

视觉 bug 用 AppTest 抓不到（它只渲染结构，不算样式），所以把它们变成
可执行的断言。这三条都真实发生过：

1. `[class*="st-"]` 通配覆盖了图标字体，箭头显示成 "keyboard_double_arrow_right"；
2. `.streamlit/config.toml` 的 primaryColor 和 CSS 不同步，同一页出现两种蓝；
3. 弱化文字贪图"看起来淡"，对比度掉到 AA 以下。
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

from ui.theme import COLORS, CSS

ROOT = Path(__file__).resolve().parent.parent


def _lum(hex_color: str) -> float:
    """WCAG 相对亮度。"""
    h = hex_color.lstrip("#")
    channels = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]

    def f(v: float) -> float:
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (f(c) for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def test_no_wildcard_font_selector():
    """字体规则里不许出现 [class*="st-"]：它会连图标 span 一起覆盖。"""
    violations = [
        line
        for line in CSS.splitlines()
        if '[class*="st-"]' in line and not line.strip().startswith(("/*", "*", "//"))
    ]
    assert not violations, f"通配字体选择器会破坏图标连字：{violations}"


def test_icon_font_is_protected():
    """图标字体必须显式保护，字体名要与 Streamlit 打包的一致。"""
    assert "Material Symbols Rounded" in CSS
    assert '[data-testid="stIconMaterial"]' in CSS
    assert 'font-feature-settings: "liga" 1 !important' in CSS


def test_config_theme_matches_css_tokens():
    """.streamlit/config.toml 与 ui/theme.py 必须是同一套色。

    Streamlit 内置组件（滑块、单选、进度）吃 config 的主题色，
    自定义组件吃 CSS 的色。不同步就是同一页两种蓝。
    """
    raw = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    cfg = tomllib.loads(raw)["theme"]
    assert cfg["primaryColor"].lower() == COLORS["brand"].lower()
    assert cfg["backgroundColor"].lower() == COLORS["bg"].lower()
    assert cfg["textColor"].lower() == COLORS["ink"].lower()


def test_text_contrast_meets_aa():
    """正文和弱化文字都要 ≥4.5:1（WCAG AA 正常字号）。"""
    bg = COLORS["bg"]
    for key in ("ink", "ink_2", "ink_3"):
        ratio = contrast(COLORS[key], bg)
        assert ratio >= 4.5, f"{key} 对背景只有 {ratio:.2f}:1，低于 AA"


def test_primary_button_contrast():
    """主按钮：白字压在墨蓝上，也要 ≥4.5:1。"""
    assert contrast("#FFFFFF", COLORS["brand"]) >= 4.5


def test_component_classes_are_defined():
    """组件里用到的 .tb-* 类必须在 CSS 里有定义，否则是拼错或漏写。

    用负向后行断言排除 `--tb-ink` 这类 CSS 变量 —— 它们长得像类名，但不是。
    """
    from ui import components

    source = Path(components.__file__).read_text(encoding="utf-8")
    used = set(re.findall(r"(?<!-)tb-[a-z-]+", source))
    defined = set(re.findall(r"\.(tb-[a-z-]+)", CSS))
    missing = used - defined
    assert not missing, f"组件用了未定义的类：{sorted(missing)}"
