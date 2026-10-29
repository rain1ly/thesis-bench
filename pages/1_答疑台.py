"""答疑台 —— 学生视角。

导师 10-29 的反馈把这一页从"一个提问框"改成了三件事必须先说清：
**这是谁的问题、问谁、谁能看见。**

原来只有"学生名 + 阶段 + 问题"，于是老师那边看不到论文题目，
也不知道该不该自己接；学生的困惑还可能被全班看见。
现在提问前先定三样东西：问题分类、问谁、公开还是隐私。

一条安全边界写在代码里：**查重只在自己的记录里查。**
拿全班记录去比对近似问题，等于用"相似度 62%"把别人的隐私问题漏出来。
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core import bootstrap, identity, qa_store
from core.ai_client import chat, load_config
from core.qa_store import CATEGORIES, STAGES
from ui import components, theme

SYSTEM_PROMPT = """你是高校毕业论文指导助手，为导师起草答复草稿，不替导师做决定。

要求：
1. 直接回答学生的问题，不扩展到无关内容
2. 给可执行的具体建议，禁止「加强研究」「多读文献」这类空话
3. 涉及研究设计、数据可得性、结论可靠性的判断，明确写「这一点需要导师确认」
4. 200 字以内
5. 不代写论文正文，只给方向和方法
6. 如果给了论文题目和问题分类，回答要贴着这个题目来，不要泛泛而谈"""


def build_prompt(thesis: str, student: str, stage: str, category: str, question: str, similar) -> str:
    lines = []
    if thesis:
        lines.append(f"论文题目：{thesis}")
    lines += [f"学生：{student}", f"阶段：{stage}", f"问题分类：{category}", f"问题：{question}"]
    if similar:
        lines += ["", "历史相关答疑（避免重复，可在此基础上补充）："]
        for _score, r in similar:
            lines.append(f"- 问：{r.question}")
            lines.append(f"  答：{r.final_answer or '（尚未答复）'}")
    return "\n".join(lines)


theme.inject()
bootstrap.ensure_demo()
actor = identity.render_switcher()

components.hero(
    "① 答疑台 · 学生端",
    "把问题问清楚，也把答案留下来",
    "提问时先定三件事：属于哪类问题、问哪位老师、给谁看。老师改完你才看到定稿 —— 不是系统不给你答案，是答案需要有人负责。",
    metas=[(f"当前身份　{actor.label}", "brand")],
)

if actor.is_teacher:
    st.info("当前是老师身份。老师端的待办、学生名单和沉淀库在「老师端」页。")
    st.page_link("pages/2_老师端.py", label="去老师端 →")
    st.stop()

profile = qa_store.get_student(actor.name)
thesis = profile.get("thesis_title", "")
advisor = profile.get("advisor", "")

_pf = st.session_state.pop("prof_flash", None)
if _pf:
    st.success(_pf)

with st.container(border=True):
    c1, c2 = st.columns([2, 1])
    c1.markdown(f"**论文题目**　{thesis or '（还没填，老师看不到你的题目）'}")
    c2.caption(f"指导老师　{advisor or '未分配'}")

    with st.expander("修改论文题目 / 指导老师"):
        st.caption("题目改了记得更新 —— 预演台按题目出题，老师也靠它认你的论文。")
        # 控件 key 必须带上身份。无 key 时控件状态按位置复用，
        # 切到别的学生会把上一个人的题目和导师带过来 —— 于是顶部只读值和下拉值
        # 在同一屏给出两个答案，用户第一反应是"系统自相矛盾"。
        teachers = identity.teacher_names()
        k_title = f"prof_title_{actor.name}"
        k_adv = f"prof_adv_{actor.name}"
        if st.session_state.get(k_adv) not in teachers:
            st.session_state[k_adv] = advisor if advisor in teachers else teachers[0]
        if k_title not in st.session_state:
            st.session_state[k_title] = thesis

        with st.form("profile_form"):
            new_title = st.text_input("论文题目", key=k_title)
            new_adv = st.selectbox("指导老师", teachers, key=k_adv)
            if st.form_submit_button("保存档案", type="primary"):
                qa_store.upsert_student(actor.name, new_title, new_adv, profile.get("major", ""))
                # 保存后把这个学生的编辑态丢掉，下轮从库里重建，避免"改完还显示旧值"
                st.session_state.pop(k_title, None)
                st.session_state.pop(k_adv, None)
                st.session_state["prof_flash"] = "档案已保存。"
                st.rerun()

tab_ask, tab_mine, tab_open = st.tabs(["我要提问", "我的问题", "公开问答"])

# ------------------------------------------------------------------ 提问
with tab_ask:
    c1, c2 = st.columns(2)
    stage = c1.selectbox("所处阶段", STAGES, key="q_stage")
    category = c2.selectbox("问题分类", CATEGORIES, key="q_cat")

    visibility = st.radio(
        "可见性",
        ["公开", "隐私"],
        horizontal=True,
        key="q_vis",
        help="隐私问题仅你与受理老师可见，不会进入公开问答区，也不会被其他同学看到。",
    )

    route_options = []
    if advisor:
        route_options.append(f"我的指导老师（{advisor}）")
    route_options.append("指定其他老师")
    if visibility == "公开":
        route_options.append("公开给所有老师")
    route = st.radio(
        "答疑老师",
        route_options,
        key=f"q_route_{visibility}",
        help="指定老师只交给这一位；公开则所有老师都能看到。",
    )

    target_teacher = ""
    if route.startswith("我的指导老师"):
        target_teacher = advisor
    elif route == "指定其他老师":
        others = [t for t in identity.teacher_names() if t != advisor] or identity.teacher_names()
        target_teacher = st.selectbox("选择老师", others, key="q_teacher_pick")

    question = st.text_area(
        "你的问题",
        key="q_text",
        height=120,
        placeholder="例如：我的问卷只回收了 62 份，够不够做因子分析？",
    )

    # 查重只在自己问过的问题里找 —— 不能拿别人的隐私记录当参照物
    similar: list = []
    if question.strip():
        mine = qa_store.list_records(student=actor.name)
        similar = qa_store.find_similar(question, mine)
        if similar:
            st.warning(f"这个问题你自己问过 {len(similar)} 次，先看有没有现成答案：")
            for score, r in similar:
                with st.expander(f"{r.stage} · {r.question[:34]}（相似 {score:.0%}）"):
                    st.markdown(f"**答复**：{r.final_answer}" if r.final_answer else "这条还挂着，暂时没有答复。")
                    st.caption(f"状态：{r.status} · {r.created_at}")

    cfg = load_config()
    if not cfg.configured:
        st.caption("未配置模型密钥：提交后只做记录，导师需手动撰写答复。")

    if st.button("提交问题", type="primary", disabled=not question.strip()):
        draft, warn = "", ""
        if cfg.configured:
            with st.spinner("正在起草答复草稿…"):
                ok, text = chat(
                    cfg,
                    SYSTEM_PROMPT,
                    build_prompt(thesis, actor.name, stage, category, question, similar),
                )
            if ok:
                draft = text
            else:
                warn = f"AI 起草失败：{text}（问题已记录，导师可手动答复）"

        rid = qa_store.add_question(
            student=actor.name,
            question=question,
            stage=stage,
            ai_draft=draft,
            tags="、".join(sorted({r.tags for _s, r in similar if r.tags})[:2]),
            category=category,
            visibility=visibility,
            assigned_to=target_teacher,
            thesis_title=thesis,
        )
        where = f"已派给 {target_teacher}" if target_teacher else "已放进公开池，任何老师都能接"
        msg = f"已提交，编号 #{rid}，{where}。" + ("已生成草稿，等待老师审核。" if draft else "")
        if warn:
            msg += f" {warn}"
        st.session_state["qa_flash"] = msg
        st.rerun()

# ------------------------------------------------------------------ 我的问题
with tab_mine:
    flash = st.session_state.pop("qa_flash", None)
    if flash:
        st.success(flash)

    rows = qa_store.list_records(student=actor.name)
    if not rows:
        st.info("你还没有提过问题。")
        if qa_store.stats()["total"] == 0:
            st.caption("库里一条数据都没有。可以先载入一批示例，把流程跑起来。")
            if st.button("载入示例数据（30 条）", type="primary", key="load_seed_btn"):
                from core.qa_seed import load_seed

                n = load_seed()
                st.session_state["qa_flash"] = f"已载入 {n} 条示例答疑记录。"
                st.rerun()
    else:
        done = sum(1 for r in rows if r.answered)
        m1, m2, m3 = st.columns(3)
        m1.metric("提问总数", len(rows))
        m2.metric("已答复", done)
        m3.metric("还在等", len(rows) - done)

        for r in rows[:20]:
            icon = "隐私" if r.is_private else "公开"
            with st.expander(f"#{r.id} · {r.category} · {icon} · {r.question[:30]}"):
                st.markdown(f"**问题**　{r.question}")
                st.caption(f"{r.stage} · {r.audience} · 提交于 {r.created_at}")
                if r.final_answer:
                    st.markdown(f"**答复**　{r.final_answer}")
                    if r.reviewer_note:
                        st.caption(f"老师备注：{r.reviewer_note}")
                else:
                    st.warning("还没有答复。")
                st.caption(f"状态：{r.status}")

# ------------------------------------------------------------------ 公开问答
with tab_open:
    st.caption("全班已通过的公开问答。隐私问题不会出现在这里。")
    pool = [r for r in qa_store.list_records(status="已通过") if r.visibility == "公开"]
    if not pool:
        st.info("还没有公开的问答沉淀。")
    else:
        cats = ["全部"] + sorted({r.category for r in pool})
        pick = st.selectbox("按分类筛选", cats, key="open_cat")
        shown = [r for r in pool if pick == "全部" or r.category == pick]
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "分类": r.category,
                        "问题": r.question[:46],
                        "答复": r.final_answer[:46],
                        "提问者": r.student,
                        "时间": r.created_at,
                    }
                    for r in shown
                ]
            ),
            hide_index=True,
            width="stretch",
        )
