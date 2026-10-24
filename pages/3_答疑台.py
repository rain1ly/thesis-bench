"""答疑台 —— 本作品的第一个核心模块。

立场先说清楚：**AI 只起草，不裁决。**
任何 AI 产出都标为「待审核」，导师点通过或退回之后才算数。
学术判断不能交给模型，这一点在设计上就锁死，不靠自觉。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core import qa_store
from core.ai_client import chat, load_config
from core.qa_store import STAGES, STATUSES

st.title("答疑台")
st.caption("把「学生问、导师答」的过程沉淀下来：重复问题不必答第二遍，薄弱点会自己浮出来")

SYSTEM_PROMPT = """你是高校毕业论文指导助手，为导师起草答复草稿，不替导师做决定。

要求：
1. 直接回答学生的问题，不扩展到无关内容
2. 给可执行的具体建议，禁止「加强研究」「多读文献」这类空话
3. 涉及研究设计、数据可得性、结论可靠性的判断，明确写「这一点需要导师确认」
4. 200 字以内
5. 不代写论文正文，只给方向和方法"""


def build_prompt(student: str, stage: str, question: str, similar) -> str:
    lines = [f"学生：{student}", f"阶段：{stage}", f"问题：{question}"]
    if similar:
        lines.append("")
        lines.append("历史相关答疑（可参考，避免重复）：")
        for _score, r in similar:
            lines.append(f"- 问：{r.question}")
            lines.append(f"  答：{r.final_answer or '（尚未答复）'}")
    return "\n".join(lines)


flash = st.session_state.pop("qa_flash", None)
if flash:
    st.success(flash)

tab_ask, tab_review, tab_records = st.tabs(["学生提问", "导师审核", "记录与画像"])

# ------------------------------------------------------------------ 学生提问
with tab_ask:
    c1, c2 = st.columns([1.4, 1])
    student = c1.text_input("学生（姓名或学号）", key="q_student", placeholder="例如：陈同学 / 20220101")
    stage = c2.selectbox("所处阶段", STAGES, key="q_stage")

    question = st.text_area(
        "你的问题",
        key="q_text",
        height=120,
        placeholder="例如：我的问卷只回收了 62 份，够不够做因子分析？",
    )

    # 边写边查：这是「重复问题不必答第二遍」的入口
    similar: list = []
    if question.strip():
        similar = qa_store.find_similar(question, qa_store.list_records())
        if similar:
            st.warning(f"这个问题历史上问过 {len(similar)} 次，先看有没有现成答案：")
            for score, r in similar:
                head = f"{r.student} · {r.stage} · {r.question[:34]}（相似 {score:.0%}）"
                with st.expander(head):
                    if r.final_answer:
                        st.markdown(f"**答复**：{r.final_answer}")
                        st.caption(f"状态：{r.status} · {r.created_at}")
                    else:
                        st.info("这条还挂着，暂时没有答复。")

    cfg = load_config()
    if not cfg.configured:
        st.caption("未配置模型密钥：提交后只做记录，导师需手动撰写答复。")

    if st.button("提交问题", type="primary", disabled=not (student.strip() and question.strip())):
        draft, warn = "", ""
        if cfg.configured:
            with st.spinner("正在起草答复草稿…"):
                ok, text = chat(cfg, SYSTEM_PROMPT, build_prompt(student, stage, question, similar))
            if ok:
                draft = text
            else:
                warn = f"AI 起草失败：{text}（问题已记录，导师可手动答复）"

        rid = qa_store.add_question(
            student=student,
            question=question,
            stage=stage,
            ai_draft=draft,
            tags="、".join(sorted({r.tags for _s, r in similar if r.tags})[:2]),
        )
        msg = f"已提交，编号 #{rid}。" + ("已生成草稿，等待导师审核。" if draft else "已进入待审核队列。")
        if warn:
            msg += f" {warn}"
        st.session_state["qa_flash"] = msg
        st.rerun()

# ------------------------------------------------------------------ 导师审核
with tab_review:
    pending = qa_store.list_records(status="待审核")
    if not pending:
        st.info("没有待审核的问题。学生提交后会出现在这里。")

    for r in pending:
        title = f"#{r.id} · {r.student} · {r.stage} · {r.question[:30]}"
        with st.expander(title, expanded=len(pending) == 1):
            st.markdown(f"**学生提问**　{r.question}")
            st.caption(f"提交于 {r.created_at}" + (f"　·　AI 已起草" if r.ai_draft else "　·　无 AI 草稿"))

            answer = st.text_area(
                "答复（可直接修改 AI 草稿）",
                value=r.final_answer,
                height=150,
                key=f"ans_{r.id}",
            )
            note = st.text_input("审核备注（可选，学生可见）", key=f"note_{r.id}")

            b1, b2, _ = st.columns([1, 1, 2])
            if b1.button("通过", key=f"ok_{r.id}", type="primary"):
                qa_store.review(r.id, "已通过", answer=answer, note=note)
                st.session_state["qa_flash"] = f"#{r.id} 已通过，答复已入库。"
                st.rerun()
            if b2.button("退回重问", key=f"back_{r.id}"):
                qa_store.review(r.id, "已退回", answer=answer, note=note)
                st.session_state["qa_flash"] = f"#{r.id} 已退回。"
                st.rerun()

    done = qa_store.list_records(status="已通过")
    if done:
        with st.expander(f"已通过 {len(done)} 条（点开查看）"):
            for r in done[:20]:
                st.markdown(f"**#{r.id}** {r.student} · {r.stage}｜{r.question}")
                st.markdown(f"> {r.final_answer}")
                st.divider()

# ------------------------------------------------------------------ 记录与画像
with tab_records:
    s = qa_store.stats()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("记录总数", s["total"])
    m2.metric("学生数", s["students"])
    m3.metric("待审核", s["待审核"])
    m4.metric("已通过", s["已通过"])

    if s["total"] == 0:
        st.info("还没有任何答疑记录。可以先载入一批示例数据，把流程跑起来。")
        if st.button("载入示例数据（30 条）", type="primary"):
            from core.qa_seed import load_seed

            n = load_seed()
            st.session_state["qa_flash"] = f"已载入 {n} 条示例答疑记录。"
            st.rerun()
        st.stop()

    st.divider()
    f1, f2, f3 = st.columns(3)
    pick_student = f1.selectbox("学生", ["全部"] + qa_store.students())
    pick_status = f2.selectbox("状态", ["全部", *STATUSES])
    keyword = f3.text_input("关键词", placeholder="例如：数据 / 问卷 / 图表")

    records = qa_store.list_records(
        student=None if pick_student == "全部" else pick_student,
        status=None if pick_status == "全部" else pick_status,
        keyword=keyword.strip() or None,
    )

    if not records:
        st.info("没有符合条件的记录。")
    else:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "编号": r.id,
                        "学生": r.student,
                        "阶段": r.stage,
                        "问题": r.question[:46],
                        "状态": r.status,
                        "答复": (r.final_answer or "")[:46] or "—",
                        "提交时间": r.created_at,
                    }
                    for r in records
                ]
            ),
            hide_index=True,
            width="stretch",
        )

    st.divider()
    st.subheader("学生问题画像")
    st.caption("论文里看不出谁卡住了，但提问记录可以。这张表就是「预演台」的出题依据。")

    rows = []
    for name in qa_store.students():
        rs = qa_store.list_records(student=name)
        solved = sum(1 for r in rs if r.answered)
        unanswered = sum(1 for r in rs if not r.final_answer)
        rows.append(
            {
                "学生": name,
                "提问数": len(rs),
                "已答复": solved,
                "未答复": unanswered,
                "最近提问": rs[0].created_at if rs else "",
                "风险": "高" if unanswered >= 3 else ("中" if unanswered >= 1 else "低"),
            }
        )
    st.dataframe(pd.DataFrame(rows).sort_values("未答复", ascending=False), hide_index=True, width="stretch")
