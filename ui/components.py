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
    """顶栏黑条：左侧标识 + 日期。

    右端**故意不画方框**：那个方框必须是真控件（点开能切身份），
    纯 HTML 画出来的"亮描边 + 箭头"会让用户以为能点，点了却没反应。
    右端的身份方框由 identity_chip() 用 st.popover 浮上去，
    参数 who / page 保留只为调用方兼容，实际渲染在 identity_chip 里。
    """
    import streamlit as st

    st.markdown(
        f"""<div class="tb-topbar">
  <div class="left">
    <span class="brand">THESIS BENCH</span>
    <span class="sep"></span>
    <span class="dim">论文工坊</span>
    <span class="faint">{_esc(date)}</span>
  </div>
</div>""",
        unsafe_allow_html=True,
    )


def nav() -> None:
    """章节导航条。单页之后没有"页面"可跳，位置感全靠这一条。

    锚点是普通 `<a href="#xxx">`：只改 URL hash，浏览器自己滚，不触发 rerun。
    用 st.page_link 或 st.button 都会走一次服务端往返，滚动式体验就断了。
    """
    import streamlit as st

    items = [
        ("home", "01", "首页", "HOME"),
        ("qa", "02", "答疑台", "QA"),
        ("writing", "03", "写作台", "CHECK"),
        ("rehearsal", "04", "预演台", "REHEARSE"),
    ]
    links = "".join(
        f'<a href="#{key}"><span class="no">{no}</span><span>{name}</span>'
        f'<span class="en">{en}</span></a>'
        for key, no, name, en in items
    )
    st.markdown(f'<div class="tb-nav">{links}</div>', unsafe_allow_html=True)


def anchor(key: str) -> None:
    """区块锚点。高度 0，只承担"滚到这里"和"避开固定头"两件事。"""
    import streamlit as st

    st.markdown(f'<span id="{_esc(key)}" class="tb-anchor"></span>', unsafe_allow_html=True)


def _highlight(text: str) -> str:
    """把 `[[关键词]]` 转成荧光笔标记，其余部分转义。

    为什么用标记而不是传 HTML：section_head 是"内容函数"，
    允许调用方塞原始 HTML 就等于把转义责任推出去，
    迟早有人把学生原话（可能带尖括号）直接拼进来。
    这里只认一种标记，解析完统一转义，安全边界是清楚的。
    """
    out: list[str] = []
    for i, seg in enumerate(str(text).split("[[")):
        if i == 0:
            out.append(_esc(seg))
            continue
        head, sep, tail = seg.partition("]]")
        if sep:
            out.append(f'<em class="sh-hl">{_esc(head)}</em>{_esc(tail)}')
        else:
            # 只有左括号没有右括号：原样显示，不要让排版吃掉用户的字
            out.append(_esc("[[" + seg))
    return "".join(out)


def section_head(no: str, title: str, en: str, desc: str, meta: str = "") -> None:
    """区块标头：竖切一刀的"章节扉页"。

    与首页主卡同一套语言：顶部 2px 黑线 → 红编号 + 宽字距英文 + 右上天元数据
    → 超粗大标题（可带荧光笔）→ 1px 细线 → 说明。

    **为什么不是卡片**：卡片会把下面的表单挤成"卡片外的东西"；
    这条扉页是一条横切的带，天然是章节开头，往后接什么都成立。

    `no` 允许写成 "02 / 答疑台"，会拆成编号与中文名 —— 调用方只传一个字符串，
    不用为了排版把业务标签拆开传。
    """
    import streamlit as st

    num, _, name = str(no).partition(" / ")
    name = name or num
    meta_html = f'<span class="sh-meta">{_esc(meta)}</span>' if meta else ""
    st.markdown(
        f"""<div class="tb-sechead">
  <div class="sh-top">
    <span class="sh-no">{_esc(num)}</span>
    <span class="sh-name">{_esc(name)}</span>
    <span class="sh-en">{_esc(en)}</span>
    {meta_html}
  </div>
  <h2 class="sh-title">{_highlight(title)}</h2>
  <div class="sh-rule"></div>
  <p class="sh-desc">{_esc(desc)}</p>
</div>""",
        unsafe_allow_html=True,
    )


def identity_chip(actor=None, page: str = "") -> None:
    """顶栏右端的身份方框 —— 真的能点，点开就是切换器。

    为什么单独一个函数：Streamlit 的控件不能塞进 HTML 块，
    所以它只能用 fixed 定位浮在黑条右端（见 theme.py）。

    **两个必须记住的坑：**
    1. 不能在渲染时比较"控件值 ≠ 当前身份"然后自动切换 ——
       popover 里的控件即使关着也会每轮执行，于是侧边栏切了人之后，
       这里发现 popover 还停在旧名字，就把身份又改回去，形成互相打架。
       所以只用 on_change 回调。
    2. 控件 key 必须带上当前身份（`pop_name_学生_陈同学`）。
       key 一旦写死，切人之后控件仍持有旧值，同样会把身份拉回去；
       带上身份之后，人一变 key 就变，控件自然用新身份重新初始化。
    """
    import streamlit as st

    from core import identity as identity_mod

    # 没传 actor 的页面（写作台等不涉及身份的页）也能显示，取当前会话身份
    actor = actor or identity_mod.current()
    label = f"{actor.label}　{page}".strip()

    role_k = f"pop_role_{actor.role}"
    name_k = f"pop_name_{actor.role}_{actor.name}"

    def _on_role() -> None:
        # 只切角色，名字留空 —— 由 identity.ensure() 兜底成新名单的第一个
        st.session_state["_actor_pending"] = (st.session_state.get(role_k, actor.role), "")
        # 必须再 rerun 一次：本轮开头 ensure() 已经跑过了，标记要到下一轮才被消费。
        # 不补这一次，用户切完看不到任何变化，得手动再点一下才生效。
        st.rerun()

    def _on_name() -> None:
        st.session_state["_actor_pending"] = (
            st.session_state.get(role_k, actor.role),
            st.session_state.get(name_k, actor.name),
        )
        st.rerun()

    # 不加 icon：`:material/` 图标在 popover 按钮里可能被渲染成图标名字面量
    # （Material Symbols 靠连字，一旦字体没加载完就会露出 swap_horiz 这种原文）。
    with st.popover(label, key="identity_pop"):
        st.caption("演示版用身份切换代替登录；生产环境接学校统一认证。")
        role = st.radio(
            "角色",
            identity_mod.ROLES,
            index=identity_mod.ROLES.index(actor.role),
            horizontal=True,
            label_visibility="collapsed",
            key=role_k,
            on_change=_on_role,
        )
        pool = (
            identity_mod.student_names()
            if role == "学生"
            else identity_mod.teacher_names()
        )
        st.selectbox(
            "姓名",
            pool,
            index=pool.index(actor.name) if actor.name in pool else 0,
            key=name_k,
            label_visibility="collapsed",
            on_change=_on_name,
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


def check_grid(items: list[tuple[str, str, str, str, str]]) -> None:
    """四栏规则说明卡：编号 + 中文名 + 英文 + 查什么 + 交付什么。

    用途是填"空状态"：写作台没上传文件时，这一屏不能只有上传框。
    但它同时承担说明职责 —— 读者看完这四栏就知道点下去会得到什么，
    不需要先试一遍。

    items = [(编号, 中文名, 英文, 查什么, 产出)]。四栏是设计稿的固定列数，
    多传或少于 4 条都会让版面塌掉，所以这里不做好看的自适应。
    """
    import streamlit as st

    cells = []
    for no, name, en, what, deliver in items:
        cells.append(
            f"""<div class="tb-check">
  <div class="c-top"><span class="c-no">{_esc(no)}</span><span class="c-en">{_esc(en)}</span></div>
  <div class="c-name">{_esc(name)}</div>
  <div class="c-what">{_esc(what)}</div>
  <div class="c-deliver">{_esc(deliver)}</div>
</div>"""
        )
    st.markdown(f'<div class="tb-checkgrid">{"".join(cells)}</div>', unsafe_allow_html=True)


def section_foot(no: str, nxt: str = "") -> None:
    """区块尾栏：一条黑线 + 编号 + 下一段指引，压在这一屏的底部。

    作用是把"一屏一区"的底部留白收掉 —— 内容少的区块（比如写作台空状态）
    底下会空出两三百像素，看起来像没加载完；有了这条线，空白变成"留白"。

    同时它承担滚动引导：写完一段明确告诉你下一段是什么，
    比让人自己猜"下面还有没有东西"好。
    """
    import streamlit as st

    nxt_html = f'<span class="sf-next">↓ {_esc(nxt)}</span>' if nxt else ""
    st.markdown(
        f'<div class="tb-secfoot"><span class="sf-no">{_esc(no)}</span>{nxt_html}</div>',
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
