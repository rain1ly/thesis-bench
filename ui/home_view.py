"""首页 —— 按设计稿一比一实现。

**为什么整页是一块 HTML 而不是拼 Streamlit 组件**
设计稿里的层级是：贴边黑条 → 大卡片（描边标题 + 黄块 + 切角 + 右上天元数据）
→ 三段链条 → 圆环 + 待办队列 → 黑条 → 状态栏。
用 st.columns / st.container 拼，列间距、边框、间距全被框架锁死，
拼出来只能"像"，做不到"是"。所以这一页的呈现整体交给 HTML，
只把身份切换（必须真能点）留给 st.popover 浮上去。

**缩放适配**
字号用 clamp(下限, 视口比例, 上限)，容器用 flex + min-width:0。
浏览器放大时视口 CSS 宽度变小，字号和间距跟着收，不会横向溢出。
之前用固定 px + max-width:1260px，一放大两侧全是白边、文字挤成一条 —— 那次就是没做这件事。
"""

from __future__ import annotations

import html as _html


def _e(v: object) -> str:
    return _html.escape(str(v), quote=True)


CSS = """
<style>
.cv {
  position: relative;
  background: #FFFFFF;
  border: 2px solid #111111;
  /* 撑满主要视线高度：内容自然高度只有 ~700px，900px 视口里下面会空一大块。
     min-height + 链条贴底，正好复刻设计稿"标题在上、链条在下、中间留白"的构图。 */
  /* 主卡吃掉一屏的主要高度：46vh 在 900 屏幕上约 414px，
     加上下方待办条和状态栏，整页正好填满一屏，不留大片空白 */
  min-height: clamp(300px, 58vh, 620px);
  display: flex;
  flex-direction: column;
  /* 右上角切角 30px。clip-path 会连 border 一起裁，所以斜线由 .cv-angle 的 svg 补 */
  clip-path: polygon(0 0, calc(100% - 30px) 0, 100% 30px, 100% 100%, 0 100%);
}
.cv-angle {
  position: absolute; top: 0; right: 0;
  width: 30px; height: 30px; pointer-events: none;
}
.cv-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: clamp(16px, 2.2vw, 32px) clamp(16px, 2.4vw, 34px) 0;
}

/* 右上天元数据：必须避开切角 —— 右边界退到 30 + 8 = 38px 之内 */
.cv-meta {
  position: absolute;
  top: clamp(14px, 1.8vw, 26px);
  right: clamp(30px, 3vw, 44px);
  text-align: right;
  font-family: __MONO__;
  font-size: clamp(7px, 0.62vw, 8.5px);
  line-height: 1.9;
  color: #6B6B6B;
  letter-spacing: 0.12em;
}
.cv-meta b { color: #111111; font-weight: 700; }

/* 标题：THESIS 实心 + -BENCH 描边，两行 */
.cv-ttl { display: flex; flex-direction: column; line-height: 0.88; }
.cv-ttl .s1, .cv-ttl .s2 {
  font-family: __HEAVY__;
  font-weight: 900;
  font-size: clamp(32px, 5.8vw, 84px);
  letter-spacing: -0.035em;
}
.cv-ttl .s2 {
  color: transparent;
  -webkit-text-stroke: clamp(1px, 0.11vw, 1.6px) #111111;
}

/* 黄块 + 副标 */
.cv-sub {
  display: flex; align-items: baseline; flex-wrap: wrap;
  gap: clamp(8px, 1.2vw, 16px);
  margin-top: clamp(10px, 1.4vw, 20px);
}
.cv-sub .hl {
  background: #F5E027;
  color: #111111;
  font-weight: 900;
  font-size: clamp(16px, 2.3vw, 33px);
  letter-spacing: 0.02em;
  padding: 0 .28em;
  line-height: 1.32;
}
.cv-sub .tag {
  font-family: __MONO__;
  font-size: clamp(7px, 0.66vw, 9px);
  letter-spacing: 0.2em;
  color: #6B6B6B;
  text-transform: uppercase;
}

/* 三段链条：margin-top:auto 把它压到卡片底部，上方留白自然撑开 ——
   这是设计稿的构图，不是"没排满" */
.cv-chain {
  display: flex;
  gap: clamp(8px, 1.4vw, 22px);
  border-top: 2px solid #111111;
  margin-top: auto;
  padding: clamp(12px, 1.5vw, 18px) 0 clamp(14px, 1.8vw, 22px);
}
/* 节点不包 <a>：`<a href>` 会让浏览器整页重新加载，点一下白屏闪一下，
   像是"跳去了另一个网站"。真正的入口是卡片下面那行 st.page_link，
   走 Streamlit 前端路由，无刷新。 */
.cv-node { flex: 1 1 0; min-width: 0; }
.n-head { display: flex; justify-content: space-between; align-items: baseline; gap: 6px; }
.n-no {
  font-family: __MONO__; font-size: clamp(8px, 0.72vw, 10px);
  color: #E30613; letter-spacing: 0.1em;
}
.n-en {
  font-family: __MONO__; font-size: clamp(6px, 0.58vw, 8px);
  color: #9A9A9A; letter-spacing: 0.16em; text-transform: uppercase;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.n-name {
  font-size: clamp(14px, 1.45vw, 21px); font-weight: 900;
  letter-spacing: -0.01em; margin-top: 6px;
}
.n-nums {
  font-family: __MONO__; font-size: clamp(7px, 0.6vw, 8.5px);
  color: #6B6B6B; letter-spacing: 0.14em; margin-top: 3px;
}
.n-desc {
  font-size: clamp(10px, 0.92vw, 12.5px); line-height: 1.85;
  color: #3D3D3D; margin-top: clamp(7px, 0.9vw, 12px);
  border-top: 1px solid #E4E2DB; padding-top: clamp(7px, 0.9vw, 11px);
}
.n-arrow {
  flex: 0 0 auto; align-self: flex-start;
  padding-top: clamp(20px, 2.4vw, 34px);
  font-size: clamp(11px, 1.1vw, 15px); color: #111111;
}

/* 下排：圆环 + 待办队列 */
.cv-row {
  display: flex; gap: clamp(8px, 1.1vw, 14px);
  margin-top: clamp(8px, 1.1vw, 14px);
  min-height: clamp(132px, 18vh, 190px);
  flex-wrap: wrap;
}
.cv-ring {
  flex: 0 0 clamp(132px, 15vw, 196px);
  background: #FFFFFF; border: 2px solid #111111;
  padding: clamp(9px, 1vw, 13px);
  display: flex; flex-direction: column;
  clip-path: polygon(0 0, calc(100% - 16px) 0, 100% 16px, 100% 100%, 0 100%);
  position: relative;
}
.cv-ring .angle { position: absolute; top: 0; right: 0; width: 16px; height: 16px; }
.r-head {
  display: flex; justify-content: space-between; align-items: baseline; gap: 4px;
  font-family: __MONO__; font-size: clamp(6px, 0.52vw, 7.5px);
  letter-spacing: 0.16em; color: #6B6B6B;
}
.r-wrap { display: flex; justify-content: center; padding: clamp(4px, 0.6vw, 8px) 0 0; }
.r-foot {
  margin-top: auto; padding-top: clamp(5px, 0.7vw, 9px);
  font-family: __MONO__; font-size: clamp(5.5px, 0.48vw, 7px);
  letter-spacing: 0.16em; color: #9A9A9A; text-align: center;
}

.cv-queue {
  flex: 1 1 clamp(280px, 46vw, 640px); min-width: 0;
  display: flex; flex-direction: column;
  background: #FFFFFF; border: 2px solid #111111;
  clip-path: polygon(0 0, calc(100% - 16px) 0, 100% 16px, 100% 100%, 0 100%);
  position: relative;
}
.cv-queue .angle { position: absolute; top: 0; right: 0; width: 16px; height: 16px; }
.q-head {
  display: flex; align-items: baseline; gap: clamp(6px, 0.9vw, 14px);
  padding: clamp(7px, 0.9vw, 11px) clamp(9px, 1.1vw, 14px);
  border-bottom: 2px solid #111111;
  font-family: __MONO__; font-size: clamp(6px, 0.55vw, 8px);
  letter-spacing: 0.16em; color: #3D3D3D; flex-wrap: wrap;
}
.q-head b { color: #111111; font-weight: 700; }
.q-head .sort { margin-left: auto; color: #9A9A9A; }
.q-row {
  display: flex; align-items: center; gap: clamp(6px, 0.8vw, 12px);
  padding: clamp(6px, 0.8vw, 10px) clamp(9px, 1.1vw, 14px);
  border-bottom: 1px solid #E4E2DB;
  font-size: clamp(9px, 0.86vw, 12px);
}
.q-row:last-child { border-bottom: none; }
/* 待办只有两三条时，行会在框底留白；让每行均分剩余高度，框子看起来才是"排满的" */
.q-row { flex: 1 1 auto; }
.q-row .t { font-family: __MONO__; font-size: clamp(7px, 0.62vw, 9px); color: #6B6B6B; letter-spacing: 0.08em; }
.q-row .w { font-family: __MONO__; font-size: clamp(7px, 0.62vw, 9px); color: #E30613; letter-spacing: 0.08em; }
.q-row .who { font-weight: 700; white-space: nowrap; }
.q-row .cat { color: #9A9A9A; white-space: nowrap; font-size: clamp(8px, 0.74vw, 10px); }
.q-row .txt { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.q-row .st {
  margin-left: auto; font-family: __MONO__;
  font-size: clamp(6px, 0.55vw, 8px); letter-spacing: 0.18em;
  padding: 2px 6px; white-space: nowrap;
}
.q-row .st.priv { background: #E30613; color: #FFFFFF; }
.q-row .st.pool { border: 1px solid #D9D7D0; color: #6B6B6B; }
.q-empty { padding: 14px; font-size: 11px; color: #9A9A9A; }

/* 底部黑条 */
.cv-strip {
  display: flex; align-items: center; gap: clamp(8px, 1.6vw, 26px);
  background: #111111; color: #F2F1EC;
  height: clamp(26px, 2.4vw, 36px);
  padding: 0 clamp(9px, 1.1vw, 14px);
  margin-top: clamp(8px, 1.1vw, 14px);
  font-family: __MONO__; font-size: clamp(5.5px, 0.52vw, 7.5px);
  letter-spacing: 0.16em; flex-wrap: nowrap; overflow: hidden;
}
.cv-strip .enter {
  margin-left: auto; background: #F2F1EC; color: #111111;
  padding: 2px 9px; font-weight: 700; text-decoration: none;
  letter-spacing: 0.18em; white-space: nowrap;
}


/* 状态栏 */
.cv-foot {
  display: flex; align-items: center; gap: clamp(8px, 1.4vw, 22px);
  margin-top: 7px; padding-top: 6px;
  border-top: 1px solid #D9D7D0;
  font-family: __MONO__; font-size: clamp(5.5px, 0.5vw, 7px);
  letter-spacing: 0.18em; color: #9A9A9A; flex-wrap: wrap;
}
.cv-foot .page { margin-left: auto; }

@media (max-width: 820px) {
  .cv-ring { flex: 1 1 100%; }
  .cv-chain { flex-wrap: wrap; }
  .cv-node { flex: 1 1 100%; }
  .n-arrow { display: none; }
}
</style>
"""


def render(
    *,
    build: str,
    date_str: str,
    chain: list[dict],
    coverage: int,
    queue: list[dict],
    foot: list[str],
    queue_title: str = "待我处理",
    page: str = "01 / 05",
    demo: bool = False,
) -> None:
    """渲染首页。chain / queue / foot 由调用方按真实数据组装。"""
    import streamlit as st

    from ui import theme

    # CSS 里的 __MONO__ / __HEAVY__ 是占位符，和 theme.py 用同一套替换机制：
    # 直接写 f-string 会被 CSS 里的花括号炸掉，这里做纯字符串替换。
    css = CSS.replace("__MONO__", theme.MONO).replace("__HEAVY__", theme.FONT)

    # 45° 斜线补切角：clip-path 把 border 一起裁掉了，这里补一条
    angle_lg = (
        '<svg class="cv-angle" viewBox="0 0 30 30" preserveAspectRatio="none">'
        '<line x1="0" y1="0" x2="30" y2="30" stroke="#111111" stroke-width="2"/></svg>'
    )
    angle_sm = (
        '<svg class="angle" viewBox="0 0 16 16" preserveAspectRatio="none">'
        '<line x1="0" y1="0" x2="16" y2="16" stroke="#111111" stroke-width="2"/></svg>'
    )

    nodes = []
    for i, n in enumerate(chain):
        if i:
            nodes.append('<div class="n-arrow">→</div>')
        nodes.append(
            f'<div class="cv-node">'
            f'<div class="n-head"><span class="n-no">{_e(n.get("no", ""))}</span>'
            f'<span class="n-en">{_e(n.get("en", ""))}</span></div>'
            f'<div class="n-name">{_e(n.get("name", ""))}</div>'
            f'<div class="n-nums">{_e(n.get("nums", ""))}</div>'
            f'<div class="n-desc">{_e(n.get("desc", ""))}</div>'
            "</div>"
        )

    rows = []
    for q in queue:
        tag_cls = "priv" if q.get("priv") else "pool"
        rows.append(
            f'<div class="q-row">'
            f'<span class="t">{_e(q.get("time", ""))}</span>'
            f'<span class="w">{_e(q.get("wait", ""))}</span>'
            f'<span class="who">{_e(q.get("who", ""))}</span>'
            f'<span class="cat">{_e(q.get("cat", ""))}</span>'
            f'<span class="txt">{_e(q.get("text", ""))}</span>'
            f'<span class="st {tag_cls}">{_e(q.get("tag", "POOL"))}</span>'
            "</div>"
        )
    if not rows:
        rows.append('<div class="q-empty">没有待处理的问题。所有提问都已答复。</div>')

    foot_html = "".join(f"<span>{_e(x)}</span>" for x in foot)
    if demo:
        foot_html += "<span style='color:#E30613'>DATA ／ DEMO</span>"

    circ = 2 * 3.14159265 * 42
    offset = circ * (1 - max(0, min(100, coverage)) / 100)

    st.markdown(
        css
        + f"""
<div class="cv">
  {angle_lg}
  <div class="cv-meta">
    NO. <b>001</b><br>
    DATE <b>{_e(date_str)}</b><br>
    BUILD <b>{_e(build)}</b>
  </div>
  <div class="cv-body">
    <div class="cv-ttl"><span class="s1">THESIS</span><span class="s2">-BENCH</span></div>
    <div class="cv-sub">
      <span class="hl">论文工坊</span>
      <span class="tag">// interface for advising ／ 写出来之前 · 先知道卡在哪</span>
    </div>
    <div class="cv-chain">{"".join(nodes)}</div>
  </div>
</div>

<div class="cv-row">
  <div class="cv-ring">
    {angle_sm}
    <div class="r-head"><span>COVERAGE</span><span>／ 要点覆盖</span></div>
    <div class="r-wrap">
      <svg width="100" height="100" viewBox="0 0 100 100" style="display:block">
        <circle cx="52" cy="52" r="42" fill="none" stroke="#E4E2DB" stroke-width="1.5"/>
        <circle cx="52" cy="52" r="42" fill="none" stroke="#E30613" stroke-width="2.5"
                stroke-dasharray="{circ:.0f}" stroke-dashoffset="{offset:.0f}"
                stroke-linecap="butt" transform="rotate(-90 52 52)"/>
        <text x="52" y="52" text-anchor="middle" dominant-baseline="central"
              font-size="26" font-weight="900" fill="#111111"
              font-family="__MONO__">{coverage}</text>
      </svg>
    </div>
    <div class="r-foot">LOWER BOUND ／ 可人工修正</div>
  </div>

  <div class="cv-queue">
    {angle_sm}
    <div class="q-head">
      <span>PENDING QUEUE</span><span>／ {_e(queue_title)} <b>{len(queue):02d}</b></span>
      <span class="sort">SORT ／ PRIVATE FIRST</span>
    </div>
    {"".join(rows)}
  </div>
</div>

<div class="cv-strip">
  <span>GRID = STRUCTURE</span><span>/</span>
  <span>CUT CORNER = CLICKABLE</span><span>/</span>
  <span>WIDE TRACKING, BOLD CHINESE</span><span>/</span>
  <span>ONE SIGNAL RED</span>
  <span class="enter">ENTER ↗</span>
</div>

<div class="cv-foot">{foot_html}<span class="page">PAGE {_e(page)}</span></div>
""",
        unsafe_allow_html=True,
    )
