"""预演台 —— 第三层，也是别人复制不走的一层。

维普手里有你的论文，我们有你的困惑史。
论文看不出谁虚，提问记录看得出来 —— 所以这里出题的依据是「你问过什么」，
不是从通用题库里随机抽。

三个刻意的设计：

1. **答题前不显示考察要点。** 显示了就是给答案，预演就没意义了。
   要点在提交后才展开，用来看「我漏了哪一条」。

2. **只报「命中几个要点」，不打分。** 78 分是假的精确，
   「你漏了『数据边界』」才是能照着改的东西。

3. **AI 只当评委追问，不当裁判。** 它不评价，只接着问。
   追问结果落库并标注「AI 生成，仅供参考」，导师可覆盖。
"""

from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from core import bootstrap, qa_store, rehearsal, rehearsal_store
from core.ai_client import chat, load_config
from ui import components, theme

theme.inject()
bootstrap.ensure_demo()

components.hero(
    "③ 预演台",
    "答辩前，先用自己问过的问题考一遍自己",
    "出题依据是答疑记录，不是通用题库。只报要点覆盖、不打分；答题前不给要点 —— 那是答案。",
)
bootstrap.demo_notice()

SYSTEM_FOLLOWUP = """你是答辩现场的评委，正在听这名学生回答你提的问题。

规则：
1. 只针对他回答里空泛、前后不一致、没交代清楚的地方追问
2. 输出 2 条追问，每条不超过 40 字，用「1. 」「2. 」开头
3. 如果他确实答得完整，只输出四个字：暂无可追问
4. 不评价他答得好不好。评委不打分，只继续问
5. 不要复述他的答案，不要给建议"""


def build_followup(question: str, points: tuple[str, ...], answer: str) -> str:
    return "\n".join(
        [
            f"我问的问题：{question}",
            f"我原本期待他答到这几点：{'、'.join(points)}",
            "",
            f"他的回答：{answer}",
        ]
    )


all_records = qa_store.list_records()
students = [name for name, _score in rehearsal.student_risk(all_records)]
if not students:
    st.info("还没有答疑记录，出不了题。先去「答疑台」录入几条，或在记录页载入示例数据。")
    st.stop()

student = st.selectbox(
    "选择学生",
    students,
    key="reh_student",
    help="按「最该练」排序：取该生风险最高的主题打分为序，不是按姓名排",
)

records = qa_store.list_records(student=student)
profile = rehearsal.build_profile(records)
stat = rehearsal_store.stats(student=student)
high = sum(1 for t in profile if t.level == "高")

components.kpi([
    ("答疑记录", len(records), "这名学生的困惑史", "default"),
    ("涉及主题", len(profile), f"{high} 个高风险", "high" if high else "default"),
    ("预演题数", stat["questions"], "已作答过的题", "default"),
    ("要点覆盖", f"{stat['coverage']:.0%}" if stat["points_total"] else "—", "按最近一次作答", "good" if stat["coverage"] >= 0.8 else "default"),
])

with st.expander("风险画像 · 这张表就是出题依据"):
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "主题": t.topic,
                    "提问次数": t.count,
                    "涉及阶段": "、".join(t.stages),
                    "未答复": t.unanswered,
                    "风险": t.level,
                    "最近一次提问": t.latest_question[:40],
                }
                for t in profile
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "风险 = 次数 ×1.0 + 跨阶段数 ×1.5 + 未答复 ×1.2。"
        "从开题一路问到定稿的主题，说明中间那几次答复没真正解决问题。"
    )

latest = rehearsal_store.latest_by_question(rehearsal_store.list_attempts(student=student))

tab_plan, tab_log = st.tabs(["出题与作答", "预演记录"])

# ------------------------------------------------------------------ 出题与作答
with tab_plan:
    if st.button("生成题单（按风险排序，6 题）", type="primary"):
        st.session_state["reh_plan"] = {
            "student": student,
            "items": rehearsal.draft(records, 6),
            "token": time.time(),  # 换题单就换 key，避免旧输入框残留
        }

    plan = st.session_state.get("reh_plan")
    if plan and plan["student"] != student:
        plan = None

    if not plan:
        st.info("点上面的按钮出题。题单不调模型，所以没配密钥也能用。")
    else:
        st.caption(
            "每题用三句话、60 秒内说完。组织语言本身就是预演的一部分 —— "
            "心里懂和嘴上说得清是两回事。答题前不显示考察要点，那是答案。"
        )

        for idx, item in enumerate(plan["items"], start=1):
            q = item.question
            prev = latest.get(q.text)
            badge = "已预演" if prev else "未预演"
            head = f"{idx}. 【风险 {item.priority} · {q.topic}】{q.text[:32]}　·　{badge}"

            with st.expander(head, expanded=(not prev and idx == 1)):
                st.markdown(f"**{q.text}**")
                st.caption(f"评委为什么问这个：{q.why}")
                for r in item.reasons:
                    st.caption(f"· 为什么挑这道：{r}")

                if prev:
                    st.divider()
                    c1, c2 = st.columns([1, 3])
                    c1.markdown(f"**最近一次：{prev.level}**")
                    c2.markdown(f"要点覆盖 **{prev.hit}/{prev.total}**　·　{prev.created_at}")
                    if prev.missing:
                        st.warning(f"漏掉的要点：{prev.missing}")
                    if prev.ai_note:
                        st.info(f"AI 评委追问（AI 生成，仅供参考）：\n\n{prev.ai_note}")

                ver = st.session_state.get(f"reh_ver_{idx}", 0)
                answer = st.text_area(
                    "你的回答" if not prev else "再答一遍（上一次的记录不会被覆盖）",
                    key=f"ans_{plan['token']:.0f}_{idx}_{ver}",
                    height=110,
                    placeholder="先说结论，再说依据。别写「我认为很重要」这种话。",
                )

                b1, b2, _sp = st.columns([1, 1.2, 2])
                if b1.button("提交自评", key=f"sub_{idx}", type="primary", disabled=not answer.strip()):
                    g = rehearsal.grade(answer, q)
                    rehearsal_store.save(
                        student=student,
                        question=q.text,
                        answer=answer,
                        hit=g.hit,
                        total=g.total,
                        level=g.level,
                        topic=q.topic,
                        missing="、".join(g.missing),
                        source_ids=item.source_ids,
                    )
                    st.session_state[f"reh_ver_{idx}"] = ver + 1  # 换个控件，输入框清空
                    st.rerun()

                cfg = load_config()
                if b2.button(
                    "让 AI 评委追问",
                    key=f"ai_{idx}",
                    disabled=not (prev and cfg.configured),
                    help="提交之后才能追问" if not prev else ("需要先配置模型密钥" if not cfg.configured else "根据你的回答生成追问"),
                ):
                    with st.spinner("评委正在组织下一句…"):
                        ok, text = chat(
                            cfg,
                            SYSTEM_FOLLOWUP,
                            build_followup(q.text, tuple(p.name for p in q.points), prev.answer),
                            max_tokens=300,
                            temperature=0.4,
                        )
                    if ok:
                        rehearsal_store.attach_ai_note(prev.id, text)
                        st.rerun()
                    else:
                        st.error(f"追问失败：{text}")

                # 答完再点这个 —— 顺序反了就等于抄答案
                with st.expander("查看考察要点"):
                    st.caption("真答完再对照，才知道盲区在哪。答之前看等于抄答案。")
                    st.markdown("\n".join(f"- {p.name}" for p in q.points))
                    st.markdown(f"**可能的追问**：{q.follow_up}")

# ------------------------------------------------------------------ 预演记录
with tab_log:
    rows = rehearsal_store.list_attempts(student=student)
    if not rows:
        st.info("还没有作答记录。")
    else:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "时间": a.created_at,
                        "主题": a.topic,
                        "题目": a.question[:34],
                        "覆盖": f"{a.hit}/{a.total}",
                        "评级": a.level,
                        "漏掉": a.missing or "—",
                        "AI 追问": "有" if a.ai_note else "—",
                    }
                    for a in rows
                ]
            ),
            hide_index=True,
            width="stretch",
        )

        st.subheader("逐题轨迹")
        st.caption("答辩前最该看的不是分数，是这条线在不在往上走。")

        by_q: dict[str, list] = {}
        for a in reversed(rows):  # 按时间正序
            by_q.setdefault(a.question, []).append(a)

        for question, tries in list(by_q.items())[:8]:
            trail = " → ".join(f"{t.hit}/{t.total}" for t in tries)
            st.markdown(f"- **{question[:30]}**　{trail}")
            if len(tries) > 1 and tries[-1].hit <= tries[0].hit:
                st.caption("　改了但没进步：多半是漏的那条要点还没想明白，不是表达问题。")

st.caption(
    "判分说明：要点靠关键词匹配，是保守下限。换个说法可能漏判，导师可人工修正 —— "
    "这里给的是自查清单，不是成绩单。"
)
