"""论文工坊 · 总览页

这一页只干一件事：让第一次打开的人在十秒内明白
**这套东西是什么、三层各自走到哪、数据是哪来的。**

之前首页是「上传 docx」，等于把自己摆在查重工具隔壁 —— 正好撞进维普的主场。
定位是「导学协同」，第一屏就该是这个链条，而不是一个上传框。
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from core import bootstrap, identity, qa_store, rehearsal, rehearsal_store

ROOT = Path(__file__).resolve().parent

st.set_page_config(page_title="论文工坊 · ThesisBench", layout="wide")

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


st.title("论文工坊 · ThesisBench")
st.caption(
    "管「写出来之前卡在哪、能不能过答辩」。"
    "维普那类系统管的是交上去之后合不合规 —— 两件事，不重叠。"
)

actor = identity.render_switcher()

# st.rerun 会丢掉本轮的提示消息，所以先存再显示 —— 否则点完清空什么反馈都没有
flash = st.session_state.pop("home_flash", None)
if flash:
    st.success(flash)

qa = qa_store.stats()
if qa["total"] == 0:
    st.warning(
        "答疑库现在是空的。想要演示数据，去「答疑台」→ 载入示例数据；要录真实问题，直接提问即可。"
    )

reh = rehearsal_store.stats()
risks = rehearsal.build_profile(qa_store.list_records())
high_risks = [t for t in risks if t.level == "高"]
n_files, n_issues, n_severe = sample_stat()

st.markdown("### 一条链，三层")
st.caption("不是三个并列功能：上一层的产出是下一层的输入。侧边栏可切换学生 / 老师身份。")

c1, c2, c3 = st.columns(3, gap="medium")

with c1:
    with st.container(border=True):
        st.markdown("**① 答疑台**")
        st.metric("答疑记录", qa["total"], f"{qa['待审核']} 条待处理", delta_color="inverse")
        st.caption(
            "提问时先定三件事：问题分类、问谁（导师 / 指定老师 / 公开池）、公开还是隐私。"
            "AI 起草，老师改完才入库。"
        )
        st.page_link("pages/1_答疑台.py", label="学生提问 →")
        st.page_link("pages/2_老师端.py", label="老师待办 →")

with c2:
    with st.container(border=True):
        st.markdown("**② 写作台**")
        st.metric("样本检出问题", n_issues, f"{n_severe} 项严重", delta_color="inverse")
        st.caption(
            f"4 类规则检查（文献双向引用 / 图表悬空 / 章节结构 / 标题承诺），"
            f"用仓库里 {n_files} 份真实样本跑出的数字。不调模型，结果可复现。"
        )
        st.page_link("pages/3_写作台.py", label="进入写作台 →")

with c3:
    with st.container(border=True):
        st.markdown("**③ 预演台**")
        st.metric(
            "已预演题数",
            reh["questions"],
            f"{len(high_risks)} 个高风险主题",
            delta_color="inverse",
        )
        st.caption(
            "按学生问过的问题出题 —— 这是维普拿不到的数据。"
            "只报要点覆盖，不打分；AI 只当评委追问，不当裁判。"
        )
        st.page_link("pages/4_预演台.py", label="进入预演台 →")

st.divider()

left, right = st.columns([1.5, 1], gap="large")

with left:
    st.markdown("**闭环是怎么转的**")
    st.markdown(
        "答疑入库 → 总结出问题画像 → 画像驱动预演出题 → 答完发现缺口 → 带着新问题回去问。\n\n"
        "转一圈，下一轮出题就更准一点。**系统的价值不在一屏输出，在这条线越转越细。**"
    )

with right:
    st.markdown("**不做的事**")
    st.markdown("不查重、不代写、不管流程。")
    st.markdown("**AI 的位置**")
    st.markdown("只起草，不裁决。答复草稿要导师点通过才入库。")

st.divider()

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

st.caption("环境自检（密钥与模型连通性）在左侧「环境自检」页。")
if bootstrap.is_demo():
    st.caption("当前为示例数据 · 30 条模拟答疑（虚构学生，非真实访谈）· 清空入口在上方折叠区")
