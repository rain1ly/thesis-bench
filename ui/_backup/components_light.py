"""可复用界面组件。

设计系统里的"原子"。页面只允许用这里的组件拼，不自己写内联样式 ——
否则第 4 个页面开始就走样，这是所有内部工具的死亡方式。

**为什么组件返回 HTML 字符串而不是 st 对象**
Streamlit 的 st.metric / st.title 排版不可控（字号、间距、徽章全被锁死）。
所以把"呈现"交给 HTML + `.tb-*` 类（样式在 ui/theme.py 一处定义），
把"交互"留给 Streamlit 原生控件（按钮、输入、表格）。
两者混用有代价：HTML 块里不能再嵌 st 组件，所以卡片里的链接要用 st.page_link 另起一行。
"""

from __future__ import annotations

import html as _html


def _esc(text: str) -> str:
    return _html.escape(str(text), quote=False)


def badge(text: str, tone: str = "neutral") -> str:
    """tone: brand / green / amber / red / neutral"""
    return f'<span class="tb-badge b-{tone}">{_esc(text)}</span>'


def risk_tone(level: str) -> str:
    return {"高": "red", "中": "amber", "低": "green"}.get(level, "neutral")


def status_tone(status: str) -> str:
    return {"已通过": "green", "待审核": "amber", "已退回": "red"}.get(status, "neutral")


def hero(eyebrow: str, title: str, subtitle: str, metas: list[tuple[str, str]] | None = None) -> None:
    """页头：小标签 + 标题 + 一句话定位 + 可选徽章行。

    每个页面都要有，因为读者第一眼需要知道"我在哪、这页解决什么"。
    只写 h1 不写副标题的页面，用户得靠猜。
    """
    import streamlit as st

    meta_html = ""
    if metas:
        meta_html = '<div class="tb-hero-meta">' + "".join(badge(t, tone) for t, tone in metas) + "</div>"
    st.markdown(
        f"""<div class="tb-hero">
  <span class="tb-eyebrow">{_esc(eyebrow)}</span>
  <h1>{title}</h1>
  <p>{subtitle}</p>
  {meta_html}
</div>""",
        unsafe_allow_html=True,
    )


def kpi(items: list[tuple[str, object, str, str]]) -> None:
    """指标行。items = [(标签, 数值, 注释, 语气)]，语气取 default/high/mid/good。

    比 st.metric 好在两点：注释可以写一句人话（"4 条隐私"），
    以及数值可以按语义着色（高风险标红），不用靠 delta 箭头猜。
    """
    import streamlit as st

    cells = []
    for label, value, note, tone in items:
        cls = {"high": " is-high", "mid": " is-mid", "good": " is-good"}.get(tone, "")
        note_html = f'<div class="k-note">{_esc(note)}</div>' if note else ""
        cells.append(
            f'<div class="tb-kpi{cls}"><div class="k-label">{_esc(label)}</div>'
            f'<div class="k-value">{_esc(value)}</div>{note_html}</div>'
        )
    st.markdown(f'<div class="tb-kpi-grid">{"".join(cells)}</div>', unsafe_allow_html=True)


def section(title: str, note: str = "") -> None:
    note_html = f'<span class="s-note">{_esc(note)}</span>' if note else ""
    import streamlit as st

    st.markdown(
        f'<div class="tb-section"><span class="s-title">{_esc(title)}</span>{note_html}</div>',
        unsafe_allow_html=True,
    )


def meta_line(parts: list[str]) -> None:
    """行内元信息：阶段 · 分类 · 时间。用圆点分隔，不用竖线（竖线太硬）。"""
    import streamlit as st

    joined = '<span class="tb-dot"></span>'.join(_esc(p) for p in parts if p)
    st.markdown(f'<div class="tb-meta">{joined}</div>', unsafe_allow_html=True)


def empty(title: str, hint: str) -> None:
    """空状态。必须给"下一步做什么"，否则用户只知道自己错了，不知道该干嘛。"""
    import streamlit as st

    st.markdown(
        f'<div class="tb-empty"><div class="e-title">{_esc(title)}</div>'
        f'<div class="e-hint">{hint}</div></div>',
        unsafe_allow_html=True,
    )


def card_head(title: str, badges: list[tuple[str, str]] | None = None, note: str = "") -> None:
    """卡片标题行：左标题 + 右徽章。在 st.container(border=True) 里第一行调用。"""
    import streamlit as st

    badge_html = "".join(badge(t, tone) for t, tone in (badges or []))
    note_html = f'<div class="tb-meta" style="margin-top:2px">{_esc(note)}</div>' if note else ""
    st.markdown(
        '<div style="display:flex;align-items:center;justify-content:space-between;gap:.5rem">'
        f'<span style="font-size:15px;font-weight:600;color:var(--tb-ink)">{_esc(title)}</span>'
        f'<span style="display:flex;gap:4px;flex-wrap:wrap">{badge_html}</span></div>{note_html}',
        unsafe_allow_html=True,
    )


def divider_gap(height: int = 18) -> None:
    import streamlit as st

    st.markdown(f'<div style="height:{height}px"></div>', unsafe_allow_html=True)
