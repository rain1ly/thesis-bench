"""论文工坊 · 总览页

这一页只干一件事：让第一次打开的人在十秒内明白
**这套东西是什么、三层各自走到哪、数据是哪来的。**

之前首页是「上传 docx」，等于把自己摆在查重工具隔壁 —— 正好撞进维普的主场。
定位是「导学协同」，第一屏就该是这个链条，而不是一个上传框。

**版式说明**：中间那条 01 → 02 → 03 不是三张并列卡片，是链条。
箭头必须在，因为产品的核心口径是「上一层的产出是下一层的输入」——
并列卡片会让版式说出相反的话。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import streamlit as st

from core import bootstrap, identity, qa_store, rehearsal, rehearsal_store
from ui import components, theme

ROOT = Path(__file__).resolve().parent

st.set_page_config(page_title="论文工坊 · ThesisBench", layout="wide", page_icon="◧")
theme.inject()

# 空库自动长出来：云端容器重启、评委刚 clone，都不该看到空页面
bootstrap.ensure_demo()


@st.cache_data(show_spinner=False)
def sample_stat() -> tuple[int, int, int]:
    """拿仓库里的两份样本跑一遍规则检查，首页显示真实数字而不是写死的文案。"""
    from core.checker import run_all, summary
    from core.parser import parse_docx

    files = total = severe = 0
    for p in sorted((ROOT / "data" / "samples").glob("*.docx")):
        try:
            stat = summary(run_all(parse_docx(str(p))))
        except Exception:  # noqa: BLE001 - 首页不该因为一份坏样本白屏
            continue
        files += 1
        total += stat["total"]
        severe += stat["severe"]
    return files, total, severe


actor = identity.render_switcher()

components.topbar(
    who=actor.label,
    page="01 / 05",
    date=date.today().strftime("%Y.%m.%d"),
)

is_demo = bootstrap.is_demo()
components.hero(
    "// THESIS BENCH ／ INTERFACE FOR ADVISING",
    "写出来之前，<br>先知道卡在哪",
    "维普那类系统管的是交上去之后合不合规。这里管的是过程：答疑沉淀、结构诊断、答辩预演。",
    metas=[
        ("示例数据" if is_demo else "自建数据", "amber" if is_demo else "green"),
        ("AI 只起草，不裁决", "neutral"),
        ("规则先于模型", "neutral"),
    ],
)

# st.rerun 会丢掉本轮的提示消息，所以先存再显示 —— 否则点完清空什么反馈都没有
flash = st.session_state.pop("home_flash", None)
if flash:
    st.success(flash)

qa = qa_store.stats()
if qa["total"] == 0:
    components.empty("答疑库是空的", "去「答疑台」载入示例数据，或直接以学生身份提第一个问题。")

all_records = qa_store.list_records()
reh = rehearsal_store.stats()
risks = rehearsal.build_profile(all_records)
high_risks = sum(1 for t in risks if t.level == "高")
n_files, n_issues, n_severe = sample_stat()

# 指标跟着身份走：学生看自己的提问，老师看自己的待办
if actor.is_teacher:
    mine = identity.inbox(all_records, actor.name)
    mine_label, mine_note, mine_value = "待我处理", "点名找我的 + 公开池", len(mine)
else:
    own = [r for r in all_records if r.student == actor.name]
    mine_label = "我的提问"
    mine_note = f"{sum(1 for r in own if not r.final_answer)} 条待答复"
    mine_value = len(own)

components.kpi(
    [
        ("答疑记录", qa["total"], f"{qa['待审核']} 待处理 ／ {len({r.student for r in all_records})} 名", "default"),
        (mine_label, mine_value, mine_note, "mid" if mine_value else "default"),
        ("样本检出问题", n_issues, f"{n_severe} 严重 ／ {n_files} 份", "high" if n_severe else "good"),
        ("已预演题数", reh["questions"], f"{high_risks} 高风险主题", "default"),
    ]
)

components.section("PIPELINE ／ 一条链，三层", "上一层的产出是下一层的输入")

components.chain(
    [
        {
            "no": "01",
            "name": "答疑台",
            "en": "QA SYSTEM",
            "nums": f"{qa['total']} REC ／ {qa['待审核']:02d} PEND",
            "desc": "分类、交给谁、公开或隐私。AI 起草，导师改完才入库。这一层沉淀下来的困惑，是下面两层的输入。",
        },
        {
            "no": "02",
            "name": "写作台",
            "en": "STRUCTURE CHECK",
            "nums": f"{n_issues} ISS ／ {n_severe:02d} SEV",
            "desc": "四类规则检查，不调模型。同一份文档永远得到同一份清单，结果可复现、可逐条核对。",
        },
        {
            "no": "03",
            "name": "预演台",
            "en": "REHEARSAL",
            "nums": f"{reh['questions']:02d} Q ／ {reh['coverage'] * 100:.0f} PCT" if reh["points_total"] else f"{reh['questions']:02d} Q",
            "desc": "用他自己的困惑出题，只报要点覆盖，不打分。漏掉的要点直接指出来。",
        },
    ]
)

l1, l2, l3 = st.columns(3, gap="small")
with l1:
    st.page_link("pages/1_答疑台.py", label="学生提问 →")
    st.page_link("pages/2_老师端.py", label="老师待办 →")
with l2:
    st.page_link("pages/3_写作台.py", label="上传论文 →")
with l3:
    st.page_link("pages/4_预演台.py", label="开始预演 →")

components.section("LOOP ／ 闭环怎么转", "系统的价值不在一屏输出，在这条线越转越细")

left, right = st.columns([1.5, 1], gap="medium")

with left:
    with st.container(border=True):
        st.markdown(
            "<div style='font-size:12.5px;line-height:2.2;font-family:var(--tb-mono,monospace);letter-spacing:0.06em'>"
            "<span class='tb-badge b-brand'>答疑入库</span>"
            "<span style='color:#B6B2A8'> → </span>"
            "<span class='tb-badge'>问题画像</span>"
            "<span style='color:#B6B2A8'> → </span>"
            "<span class='tb-badge'>预演出题</span>"
            "<span style='color:#B6B2A8'> → </span>"
            "<span class='tb-badge'>发现缺口</span>"
            "<span style='color:#B6B2A8'> → </span>"
            "<span class='tb-badge b-brand'>带着新问题回去问</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.caption("转一圈，下一轮出题就更准一点。这条线越转越细，而不是功能越堆越多。")

with right:
    with st.container(border=True):
        components.card_head("边界", no="04", en="SCOPE", badges=[("写清楚比藏起来好", "neutral")])
        st.markdown(
            "<div style='font-size:12px;line-height:2.0;color:var(--tb-ink-2)'>"
            "<b style='color:var(--tb-ink)'>不做</b>　不查重、不代写、不管流程<br>"
            "<b style='color:var(--tb-ink)'>AI 的位置</b>　只起草，不裁决<br>"
            "<b style='color:var(--tb-ink)'>数据</b>　示例数据是模拟的，页面标明"
            "</div>",
            unsafe_allow_html=True,
        )

with st.expander("数据来源与清空"):
    if bootstrap.is_demo():
        st.markdown(
            "当前库是**示例数据**：30 条模拟答疑、4 条虚构学生线，"
            "用于演示流程与冷启动。不是真实访谈记录，也不会写成真实记录。"
        )
        ok = st.checkbox("我确认要清空示例数据（答疑与预演记录会一起删）")
        if st.button("清空示例数据", disabled=not ok):
            n_qa, n_reh = bootstrap.clear_demo()
            st.session_state["home_flash"] = (
                f"已清空 {n_qa} 条答疑、{n_reh} 条预演记录。"
                "系统不会自动再灌回来 —— 想恢复去「答疑台」点「载入示例数据」。"
            )
            st.rerun()
        st.caption("清空之后，系统就把这份库当真实数据对待，不会再自动载入，也不再提供这个清空入口。")
    else:
        st.markdown("当前库**不是示例数据**，不提供一键清空。真实学生记录只能手工处理。")

# 底部状态条：把"数据从哪来、有多少"压缩成一行，比写在正文里更少占版面
_tail = (
    f"<span>BUILD 演示版</span><span>REC {qa['total']}</span>"
    f"<span>STU {len({r.student for r in all_records})}</span>"
    f"<span>TCH {len(identity.teacher_names())}</span>"
    f"<span>MODE ／ {'TEACHER' if actor.is_teacher else 'STUDENT'}</span>"
)
if is_demo:
    _tail += "<span>DATA ／ DEMO</span>"
st.markdown(
    "<div style='display:flex;justify-content:space-between;align-items:center;"
    "border-top:1px solid var(--tb-line);margin-top:22px;padding-top:7px;"
    "font-size:7px;letter-spacing:0.2em;font-family:var(--tb-mono,monospace);color:var(--tb-ink-3)'>"
    f"<div style='display:flex;gap:14px'>{_tail}</div>"
    "<div>环境自检在左侧「环境自检」页</div></div>",
    unsafe_allow_html=True,
)
