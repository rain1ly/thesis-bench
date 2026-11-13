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
    """tone: brand / red / amber / green / neutral"""
    cls = {"brand": "b-brand", "red": "b-red", "amber": "b-amber", "green": "b-green"}.get(
        tone, ""
    )
    return f'<span class="tb-badge {cls}">{_esc(text)}</span>'


def risk_tone(level: str) -> str:
    return {"高": "red", "中": "amber", "低": "green"}.get(level, "neutral")


def status_tone(status: str) -> str:
    return {"已通过": "green", "待审核": "amber", "已退回": "red"}.get(status, "neutral")


def topbar(who: str = "", page: str = "", date: str = "") -> None:
    """顶栏黑条：左标识 + 右身份页码。

    身份那块是可交互记号（亮描边 + 底色 + 箭头）。落地时必须真绑动作，
    否则就是假按钮 —— 点一下没反应，比不做成按钮更伤。
    """
    import streamlit as st

    right = ""
    if who or page:
        right = (
            '<div class="tb-chip">'
            f'<span class="who">{_esc(who)}</span>'
            f'<span class="page">{_esc(page)}</span>'
            '<span class="go">↗</span>'
            "</div>"
        )
    st.markdown(
        f"""<div class="tb-topbar">
  <div class="left">
    <span class="brand">THESIS BENCH</span>
    <span class="sep"></span>
    <span class="dim">论文工坊</span>
    <span class="faint">{_esc(date)}</span>
  </div>
  {right}
</div>""",
        unsafe_allow_html=True,
    )


def hero(
    eyebrow: str,
    title: str,
    subtitle: str,
    metas: list[tuple[str, str]] | None = None,
) -> None:
    """页头：英文小标签 + 超粗标题 + 说明 + 2px 黑线。

    每个页面都要有，因为读者第一眼需要知道"我在哪、这页解决什么"。
    只写 h1 不写副标题的页面，用户得靠猜。
    """
    import streamlit as st

    meta_html = ""
    if metas:
        meta_html = (
            '<div class="tb-hero-meta">'
            + "".join(badge(t, tone) for t, tone in metas)
            + "</div>"
        )
    st.markdown(
        f"""<div class="tb-hero">
  <div class="eyebrow">{_esc(eyebrow)}</div>
  <h1>{title}</h1>
  <div class="lead"><div class="sub">{_esc(subtitle)}</div></div>
  <div class="rule"></div>
  {meta_html}
</div>""",
        unsafe_allow_html=True,
    )


def chain(nodes: list[dict]) -> None:
    """三段链条：01 → 02 → 03。

    nodes = [{"no": "01", "name": "答疑台", "en": "QA SYSTEM",
              "nums": "30 REC ／ 03 PEND", "desc": "……"}, ...]

    **为什么是链条不是并列卡片**：这个产品的核心口径是"上一层的产出是下一层的输入"。
    四张并排卡片会让版式说出相反的话。箭头必须存在。
    """
    import streamlit as st

    parts: list[str] = []
    for i, node in enumerate(nodes):
        if i:
            parts.append('<div class="arrow">→</div>')
        parts.append(
            f"""<div class="node">
  <div style="display:flex;justify-content:space-between;align-items:baseline">
    <span class="no">{_esc(node.get("no", ""))}</span>
    <span class="en">{_esc(node.get("en", ""))}</span>
  </div>
  <div class="name">{_esc(node.get("name", ""))}</div>
  <div class="nums">{_esc(node.get("nums", ""))}</div>
  <div class="desc">{_esc(node.get("desc", ""))}</div>
</div>"""
        )
    st.markdown(f'<div class="tb-chain">{"".join(parts)}</div>', unsafe_allow_html=True)


def kpi(items: list[tuple[str, object, str, str]]) -> None:
    """指标行。items = [(标签, 数值, 注释, 语气)]，语气取 default/high/mid/good。

    比 st.metric 好在三点：带编号（A-01）、注释可以写一句人话、
    数值可以按语义着色（高风险标红），不用靠 delta 箭头猜。
    """
    import streamlit as st

    cells = []
    for idx, (label, value, note, tone) in enumerate(items, 1):
        cls = {"high": " is-high", "mid": " is-mid", "good": " is-good"}.get(tone, "")
        note_html = f'<div class="k-note">{_esc(note)}</div>' if note else ""
        cells.append(
            f'<div class="tb-kpi{cls}">'
            f'<div class="k-top"><span class="k-label">{_esc(label)}</span>'
            f'<span class="k-no">A-{idx:02d}</span></div>'
            f'<div class="k-value">{_esc(value)}</div>{note_html}</div>'
        )
    st.markdown(f'<div class="tb-kpi-grid">{"".join(cells)}</div>', unsafe_allow_html=True)


def section(title: str, note: str = "") -> None:
    import streamlit as st

    note_html = f'<span class="s-note">{_esc(note)}</span>' if note else ""
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


def card_head(
    name: str,
    no: str = "",
    en: str = "",
    badges: list[tuple[str, str]] | None = None,
) -> None:
    """卡片标题行：编号 + 中文 + 英文 + 右侧徽章。在容器第一行调用。"""
    import streamlit as st

    left = '<div class="ch-left">'
    if no:
        left += f'<span class="ch-no">{_esc(no)}</span>'
    left += f'<span class="ch-name">{_esc(name)}</span>'
    if en:
        left += f'<span class="ch-en">{_esc(en)}</span>'
    left += "</div>"

    right = ""
    if badges:
        right = "".join(badge(t, tone) for t, tone in badges)

    st.markdown(
        f'<div class="tb-card-head">{left}<div style="display:flex;gap:4px">{right}</div></div>',
        unsafe_allow_html=True,
    )


def divider_gap(height: int = 18) -> None:
    import streamlit as st

    st.markdown(f'<div style="height:{height}px"></div>', unsafe_allow_html=True)
