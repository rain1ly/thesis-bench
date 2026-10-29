"""老师端 —— 导师反馈直接催生的一页。

原来没有这一页。学生提问，界面里直接就是"导师审核"的 tab，
等于假装只有一个老师、所有问题都归他。导师一句"可以切换老师的页面吗？
老师那边是什么样的"就把它戳穿了。

这一页回答三件事：
1. **待办**：哪些问题在等我，为什么是我（指名的 / 公开池的）
2. **我的学生**：谁在写什么题目、卡了多久、风险多高
3. **沉淀库**：已经答过的，别再答第二遍
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core import bootstrap, identity, qa_store
from ui import components, theme

theme.inject()
bootstrap.ensure_demo()
actor = identity.render_switcher()

components.hero(
    "① 答疑台 · 老师端",
    "先看谁在等我，再看谁卡住了",
    "待办按「点名找我的 → 公开池」排序，隐私问题优先；我的学生一栏能看到每个人的论文题目和卡了几次。",
    metas=[(f"当前身份　{actor.label}", "brand")],
)

if not actor.is_teacher:
    st.info("当前是学生身份。老师端的待办与名单需要切到「老师」身份查看。")
    st.page_link("pages/1_答疑台.py", label="回答疑台 →")
    st.stop()

records = qa_store.list_records()
inbox = identity.inbox(records, actor.name)
pool = identity.public_pool(records)

components.kpi([
    ("待我处理", len(inbox), f"{sum(1 for r in inbox if r.is_private)} 条隐私", "mid" if inbox else "default"),
    ("公开池", len(pool), "任何老师可接", "default"),
    ("我的学生", len(identity.my_students(actor.name, records)), "我是指导老师", "default"),
    ("已沉淀", sum(1 for r in records if r.answered and r.visibility == "公开"), "公开问答", "good"),
])

tab_todo, tab_students, tab_archive = st.tabs(["待办", "我的学生", "沉淀库"])

# ------------------------------------------------------------------ 待办
with tab_todo:
    if not inbox:
        st.success("没有待处理的问题。")
    else:
        st.caption("排序：点名找你的在前，隐私问题优先于公开问题，同组内按提交时间倒序。")
        for r in inbox:
            tags = []
            tags.append("隐私" if r.is_private else "公开")
            tags.append(r.category)
            tags.append(f"点名 {actor.name}" if r.assigned_to else "公开池")
            head = f"#{r.id} · {r.student} · {' · '.join(tags)} · {r.question[:26]}"

            with st.expander(head, expanded=len(inbox) == 1):
                thesis = r.thesis_title or qa_store.thesis_of(r.student)
                st.markdown(f"**论文题目**　{thesis or '（学生未填写）'}")
                st.markdown(f"**学生问题**　{r.question}")
                st.caption(f"{r.stage} · 提交于 {r.created_at}" + ("　·　AI 已起草" if r.ai_draft else "　·　无草稿"))

                if r.ai_draft:
                    st.info(f"AI 草稿（仅供参考，可直接改）：\n\n{r.ai_draft}")

                answer = st.text_area(
                    "答复（可直接修改草稿）",
                    value=r.final_answer,
                    height=140,
                    key=f"ans_{r.id}",
                )
                note = st.text_input("备注（学生可见，可选）", key=f"note_{r.id}")

                b1, b2, _ = st.columns([1, 1, 2])
                if b1.button("通过并入库", key=f"ok_{r.id}", type="primary", disabled=not answer.strip()):
                    qa_store.review(r.id, "已通过", answer=answer, note=note)
                    st.session_state["te_flash"] = f"#{r.id} 已通过，答复已入库。"
                    st.rerun()
                if b2.button("退回重问", key=f"back_{r.id}"):
                    qa_store.review(r.id, "已退回", answer=answer, note=note)
                    st.session_state["te_flash"] = f"#{r.id} 已退回。"
                    st.rerun()

    flash = st.session_state.pop("te_flash", None)
    if flash:
        st.success(flash)

# ------------------------------------------------------------------ 我的学生
with tab_students:
    rows = identity.my_students(actor.name, records)
    if not rows:
        st.info("名下还没有学生。示例数据里陈同学、王同学归张老师，李同学、赵同学归刘老师。")
    else:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption("风险口径与答疑台一致：未答复 ≥3 高、≥1 中、0 低。两个页面不能给出两个答案。")

        pick = st.selectbox("查看某个学生的问题", [r["学生"] for r in rows], key="te_pick")
        detail = qa_store.list_records(student=pick)
        if detail:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "编号": d.id,
                            "分类": d.category,
                            "可见性": d.visibility,
                            "问题": d.question[:40],
                            "状态": d.status,
                            "答复": (d.final_answer[:40] or "—"),
                            "时间": d.created_at,
                        }
                        for d in detail
                    ]
                ),
                hide_index=True,
                width="stretch",
            )

# ------------------------------------------------------------------ 沉淀库
with tab_archive:
    counts = identity.category_counts(records)
    if counts:
        st.markdown("**问题分类分布**")
        st.bar_chart(pd.DataFrame({"条数": list(counts.values())}, index=list(counts.keys())), height=200)
        st.caption("分类是学生提问时自选的。哪类多，下学期的开题指导就该往那补 —— 这是导师能拿走的结论。")

    done = [r for r in records if r.answered]
    if not done:
        st.info("还没有已通过的问答。")
    else:
        cats = ["全部"] + sorted({r.category for r in done})
        pick = st.selectbox("按分类筛选", cats, key="te_arc_cat")
        shown = [r for r in done if pick == "全部" or r.category == pick]
        for r in shown[:15]:
            with st.expander(f"{r.student} · {r.category} · {r.question[:30]}"):
                st.markdown(f"> {r.final_answer}")
                st.caption(f"{r.stage} · {r.visibility} · {r.created_at}")
