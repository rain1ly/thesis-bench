"""单页的四个区块：答疑台 / 写作台 / 预演台。

**为什么每个区块都套 @st.fragment**
Streamlit 的控件交互默认触发整页 rerun，页面会瞬间滚回顶部。
滚动式布局里这是致命的 —— 用户滚到答疑台点一下提交，画面弹回首页。
fragment 让交互只重跑所在那一段，滚动位置不动。**没有它，单页方案不能成立。**

**为什么 rerun 都带 scope="fragment"**
fragment 里写 `st.rerun()` 仍然整页重跑。一律用 `st.rerun(scope="fragment")`，
代价是首页那几个统计数字要等下一次整页刷新才更新 —— 换来的是滚动位置永远不丢。

**为什么每段都包 try/except**
多页时代某一页炸了只影响那一页；单页之后一个异常会让后面所有区块都不渲染。
所以每段自己兜住，出错只显示一行红字。
"""

from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from core import identity, qa_store, rehearsal, rehearsal_store
from core.ai_client import STREAM_ERROR_MARK, chat_stream, load_config
from core.checker import run_all, summary
from core.parser import parse_docx
from core.qa_store import CATEGORIES, STAGES
from ui import components

QA_SYSTEM_PROMPT = """你是高校毕业论文指导助手，为导师起草答复草稿，不替导师做决定。

要求：
1. 直接回答学生的问题，不扩展到无关内容
2. 给可执行的具体建议，禁止「加强研究」「多读文献」这类空话
3. 涉及研究设计、数据可得性、结论可靠性的判断，明确写「这一点需要导师确认」
4. 200 字以内
5. 不代写论文正文，只给方向和方法
6. 如果给了论文题目和问题分类，回答要贴着这个题目来，不要泛泛而谈"""

FOLLOWUP_SYSTEM_PROMPT = """你是答辩现场的评委，正在听这名学生回答你提的问题。

规则：
1. 只针对他回答里空泛、前后不一致、没交代清楚的地方追问
2. 输出 2 条追问，每条不超过 40 字，用「1. 」「2. 」开头
3. 如果他确实答得完整，只输出四个字：暂无可追问
4. 不评价他答得好不好。评委不打分，只继续问
5. 不要复述他的答案，不要给建议"""


def _build_qa_prompt(thesis: str, student: str, stage: str, category: str, question: str, similar) -> str:
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


def _build_followup(question: str, points: tuple[str, ...], answer: str) -> str:
    return "\n".join(
        [
            f"我问的问题：{question}",
            f"我原本期待他答到这几���：{'、'.join(points)}",
            "",
            f"他的回答：{answer}",
        ]
    )


# ====================================================================== 答疑台
@st.fragment
def qa_section(actor) -> None:
    """学生看到提问表单，老师看到待办队列 —— 同一段，按身份变形。"""
    components.anchor("qa")
    with st.container(key="sec-qa"):
        try:
            _qs = qa_store.stats()
            components.section_head(
                "02 / 答疑台",
                "把问题问清楚，也把答案[[留下来]]",
                "QA System",
                "提问时先定三件事：属于哪类问题、交给哪位老师、给谁看。AI 起草，老师改完才入库。",
                meta=f"REC {_qs['total']:02d} ／ PEND {_qs['待审核']:02d}",
            )
            if actor.is_teacher:
                _teacher_view(actor)
            else:
                _student_view(actor)
        except Exception as exc:  # noqa: BLE001 - 单页里一处崩不能拖垮后面
            st.error(f"答疑台这一段出错：{type(exc).__name__} — {exc}")
        components.section_foot("02 / 答疑台", "03 写作台")


def _student_view(actor) -> None:
    profile = qa_store.get_student(actor.name)
    thesis = profile.get("thesis_title", "")
    advisor = profile.get("advisor", "")

    _pf = st.session_state.pop("prof_flash", None)
    if _pf:
        st.success(_pf)

    with st.container(border=True, key="card-profile"):
        c1, c2 = st.columns([2, 1])
        c1.markdown(f"**论文题目**　{thesis or '（还没填，老师看不到你的题目）'}")
        c2.caption(f"指导老师　{advisor or '未分配'}")

        with st.expander("修改论文题目 / 指导老师"):
            st.caption("题目改了记得更新 —— 预演台按题目出题，老师也靠它认你的论文。")
            # 控件 key 必须带上身份：无 key 的控件按位置复用 state，
            # 切到别的学生会把上一个人的题目和导师带过来
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
                    st.session_state.pop(k_title, None)
                    st.session_state.pop(k_adv, None)
                    st.session_state["prof_flash"] = "档案已保存。"
                    st.rerun(scope="fragment")

    _flash = st.session_state.pop("qa_flash", None)
    if _flash:
        st.success(_flash)

    _last = st.session_state.pop("qa_last_draft", None)
    if _last:
        with st.expander(f"刚生成的草稿：{_last['q'][:28]}", expanded=True):
            st.markdown(f"> {_last['d']}")
            st.caption("草稿已入库，状态为「待审核」。老师修改后的定稿会显示在「我的问题」里。")

    tab_ask, tab_mine, tab_open = st.tabs(["我要提问", "我的问题", "公开问答"])

    with tab_ask:
        c1, c2 = st.columns(2)
        stage = c1.selectbox("所处阶段", STAGES, key="q_stage")
        category = c2.selectbox("问题分类", CATEGORIES, key="q_cat")

        # 可见性与答疑老师并排：它们本来就是同一件事的两面（给谁看 / 谁受理），
        # 竖着排会让右侧空出 60% 宽度，一屏一区的版式下那片空白很扎眼。
        c3, c4 = st.columns([1, 1.55], gap="medium")

        visibility = c3.radio(
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
        route = c4.radio(
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
            # 92 而不是 110：整段高度 817px 比一屏(804)多 13px，
            # 尾栏会被挤出视口。压到 92 刚好收回来，三行字也够写一句问题。
            height=92,
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
                        st.markdown(
                            f"**答复**：{r.final_answer}" if r.final_answer else "这条还挂着，暂时没有答复。"
                        )
                        st.caption(f"状态：{r.status} · {r.created_at}")

        cfg = load_config()
        if not cfg.configured:
            st.caption("未配置模型密钥：提交后只做记录，导师需手动撰写答复。")

        # 按钮不做 disabled 判断：text_area 失焦前值不回写，
        # 「边打字边判断能不能提交」永远是旧值，按钮会一直灰着
        if st.button("提交问题", type="primary"):
            question_now = (st.session_state.get("q_text") or question or "").strip()
            if not question_now:
                st.warning("请先填写问题内容再提交。")
            else:
                question = question_now
                draft, warn = "", ""
                if cfg.configured:
                    prompt = _build_qa_prompt(thesis, actor.name, stage, category, question, similar)
                    # status 面板把"思考过程"显式化：读到什么、匹配到什么、正在生成什么
                    with st.status("AI 正在起草答复草稿…", expanded=True) as status:
                        st.caption(f"读取论文题目与问题分类（{category}）")
                        st.caption(
                            f"匹配到历史答疑 {len(similar)} 条，已并入上下文"
                            if similar
                            else "未匹配到历史答疑，按新问题起草"
                        )
                        st.caption("生成草稿中，逐字返回")
                        draft = st.write_stream(chat_stream(cfg, QA_SYSTEM_PROMPT, prompt))
                        if STREAM_ERROR_MARK in draft:
                            err = draft.split(STREAM_ERROR_MARK)[-1].strip("：] ")
                            warn = f"AI 起草失败：{err}（问题已记录，导师可手动答复）"
                            draft = ""
                            status.update(label="草稿生成失败，问题已记录", state="error")
                        else:
                            status.update(
                                label=f"草稿完成 · {len(draft)} 字 · 等待老师审核",
                                state="complete",
                            )

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
                if draft:
                    st.session_state["qa_last_draft"] = {"q": question, "d": draft}
                st.rerun(scope="fragment")

    with tab_mine:
        rows = qa_store.list_records(student=actor.name)
        if not rows:
            st.info("你还没有提过问题。")
            if qa_store.stats()["total"] == 0:
                st.caption("库里一条数据都没有。可以先载入一批示例，把流程跑起来。")
                if st.button("载入示例数据（30 条）", type="primary", key="load_seed_btn"):
                    from core.qa_seed import load_seed

                    n = load_seed()
                    st.session_state["qa_flash"] = f"已载入 {n} 条示例答疑记录。"
                    st.rerun(scope="fragment")
        else:
            done = sum(1 for r in rows if r.answered)
            components.kpi(
                [
                    ("提问总数", len(rows), "我的全部记录", "default"),
                    ("已答复", done, "老师已审核入库", "good" if done else "default"),
                    ("还在等", len(rows) - done, "尚未入库", "mid" if len(rows) - done else "default"),
                ]
            )
            for r in rows[:20]:
                state = "done" if r.answered else "wait"
                with st.expander(
                    f"#{r.id:03d}　{r.category}　·　{'隐私' if r.is_private else '公开'}　·　{r.question[:30]}",
                    key=f"tbx-{state}-{r.id}",
                ):
                    components.meta_line([r.stage, r.audience, r.created_at, r.status])
                    st.markdown(f"**问题**　{r.question}")
                    if r.final_answer:
                        st.markdown(f"**答复**　{r.final_answer}")
                        if r.reviewer_note:
                            st.caption(f"老师备注：{r.reviewer_note}")
                    else:
                        st.warning("还没有答复。")

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
                height=min(360, 56 + 36 * len(shown)),
            )


def _teacher_view(actor) -> None:
    records = qa_store.list_records()
    inbox = identity.inbox(records, actor.name)
    pool = identity.public_pool(records)

    components.kpi(
        [
            ("待我处理", len(inbox), f"{sum(1 for r in inbox if r.is_private)} 条隐私", "mid" if inbox else "default"),
            ("公开池", len(pool), "任何老师可接", "default"),
            ("我的学生", len(identity.my_students(actor.name, records)), "我是指导老师", "default"),
            ("已沉淀", sum(1 for r in records if r.answered and r.visibility == "公开"), "公开问答", "good"),
        ]
    )

    tab_todo, tab_students, tab_archive = st.tabs(["待办", "我的学生", "沉淀库"])

    with tab_todo:
        if not inbox:
            st.success("没有待处理的问题。")
        else:
            st.caption("排序：点名找你的在前，隐私优先于公开，同组内按提交时间倒序。")
            # 三条待办包进一个队列框：Visual 上要和首页右下角那个 PENDING QUEUE 同构
            # （一个黑框 + 内部细线分隔），否则三个独立 expander 读成"三张并列卡片"。
            todo_box = st.container(key="card-todo")
            for r in inbox:
                # 左条颜色由 key 前缀决定（tbx-priv- 红 / tbx-pub- 灰）：
                # 不用读「隐私」两个字，扫一眼左边就知道哪条得先处理
                kind = "priv" if r.is_private else "pub"
                head = f"#{r.id:03d}　{r.student}　·　{r.category}　·　{r.question[:30]}"

                with todo_box, st.expander(head, expanded=len(inbox) == 1, key=f"tbx-{kind}-{r.id}"):
                    thesis = r.thesis_title or qa_store.thesis_of(r.student)
                    components.meta_line(
                        [
                            "隐私" if r.is_private else "公开",
                            f"点名 {actor.name}" if r.assigned_to else "公开池",
                            r.stage,
                            r.created_at,
                            "AI 已起草" if r.ai_draft else "无草稿",
                        ]
                    )
                    st.markdown(f"**论文题目**　{thesis or '（学生未填写）'}")
                    st.markdown(f"**学生问题**　{r.question}")

                    if r.ai_draft:
                        st.info(f"AI 草稿（仅供参考，可直接改）：\n\n{r.ai_draft}")

                    answer = st.text_area(
                        "答复（可直接修改草稿）", value=r.final_answer, height=130, key=f"ans_{r.id}"
                    )
                    note = st.text_input("备注（学生可见，可选）", key=f"note_{r.id}")

                    checked = st.checkbox("我已核对这条答复，可以入库", key=f"ok_chk_{r.id}")

                    b1, b2, _ = st.columns([1, 1, 2])
                    if b1.button("通过并入库", key=f"ok_{r.id}", type="primary", disabled=not checked):
                        ans = (st.session_state.get(f"ans_{r.id}") or answer or "").strip()
                        if not ans:
                            st.warning("答复不能为空，写一句再通过。")
                        else:
                            qa_store.review(r.id, "已通过", answer=ans, note=note)
                            st.session_state["te_flash"] = f"#{r.id} 已通过，答复已入库。"
                            st.rerun(scope="fragment")
                    if b2.button("退回重问", key=f"back_{r.id}"):
                        qa_store.review(r.id, "已退回", answer=answer, note=note)
                        st.session_state["te_flash"] = f"#{r.id} 已退回。"
                        st.rerun(scope="fragment")

        flash = st.session_state.pop("te_flash", None)
        if flash:
            st.success(flash)

    with tab_students:
        rows = identity.my_students(actor.name, records)
        if not rows:
            st.info("名下还没有学生。示例数据里陈同学、王同学归张老师，李同学、赵同学归刘老师。")
        else:
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=min(320, 56 + 36 * len(rows)))
            st.caption("风险口径与答疑台一致：未答复 ≥3 高、≥1 中、0 低。两个地方不能给出两个答案。")

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
                    height=min(320, 56 + 36 * len(detail)),
                )

    with tab_archive:
        counts = identity.category_counts(records)
        if counts:
            components.section("问题分类分布", f"{len(counts)} 类 · 按条数排")
            # 横向条形：分类名是 4 个汉字，竖排柱子的标签会被压成竖排文字
            st.bar_chart(
                pd.DataFrame({"条数": list(counts.values())}, index=list(counts.keys())),
                height=200,
                horizontal=True,
                color="#111111",
            )
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


# ====================================================================== 写作台
@st.fragment
def writing_section(actor) -> None:
    components.anchor("writing")
    with st.container(key="sec-writing"):
        try:
            components.section_head(
                "03 / 写作台",
                "先按评委的标准[[挑一遍毛病]]",
                "Structure Check",
                "四类确定性检查：文献双向引用、图表悬空、章节结构、标题承诺。同一份文档永远得到同一份清单，不调模型。",
                meta="4 RULES ／ DOCX",
            )
            _writing_body()
        except Exception as exc:  # noqa: BLE001
            st.error(f"写作台这一段出错：{type(exc).__name__} — {exc}")
        components.section_foot("03 / 写作台", "04 预演台")


def _writing_body() -> None:
    uploaded = st.file_uploader(
        "选择论文文件", type=["docx"], help="支持 .docx，样本见 data/samples/"
    )

    if uploaded is None:
        st.info("还没有上传文件。可以先用 `data/samples/` 里那两份样本试试，它们的问题足够典型。")
        # 空状态必须"自解释"：一屏一区的版式下，如果这里只放一个上传框，
        # 剩下 600px 全是空白，看起来像页面没加载完。
        # 这四栏本身也是说明——评委不用点任何按钮就知道"它查什么"。
        components.check_grid(
            [
                ("01", "文献双向引用", "REFERENCE", "正文引了 [1] 但参考文献里没有，或者列了却没在正文引用。", "每条引用都能对上"),
                ("02", "图表悬空", "FIGURE", "写了「如图 3 所示」，但全文找不到图 3；或图片没有编号。", "图号与正文一一对应"),
                ("03", "章节结构", "STRUCTURE", "某章只有两三百字，或某一节字数占比异常，答辩时最容易被追问。", "各章篇幅不塌陷"),
                ("04", "标题承诺", "PROMISE", "标题写了「实验与分析」，下面却没有实验数据 —— 承诺没交付。", "标题与内容对得上"),
            ]
        )
        return

    uploaded.seek(0)
    try:
        profile = parse_docx(uploaded)
    except Exception as exc:  # noqa: BLE001
        st.error(f"解析失败：{type(exc).__name__} — {exc}")
        return

    issues = run_all(profile)
    stat = summary(issues)

    components.kpi(
        [
            ("字数", f"{profile.char_count:,}", "全文", "default"),
            ("章节", len(profile.sections), "识别到的小节", "default"),
            ("图片", profile.image_count, f"表格 {profile.table_count}", "default"),
            ("检出问题", stat["total"], f"{stat['severe']} 项严重", "high" if stat["severe"] else "good"),
        ]
    )

    left, right = st.columns([1.35, 1], gap="medium")

    with left:
        if issues:
            components.section("问题清单", f"{stat['total']} 项 · 其中 {stat['severe']} 项严重")
            df = pd.DataFrame(
                [
                    {
                        "级别": i.severity,
                        "类别": i.category,
                        "位置": i.location,
                        "问题": i.message,
                        "说明": i.evidence,
                    }
                    for i in issues
                ]
            )
            # 限高 + 内部滚动：问题多的时候整段会撑到两屏，这一屏一区的版式就散了
            st.dataframe(df, width="stretch", hide_index=True, height=420)
        else:
            st.success("没有发现结构性问题。")

    with right:
        if profile.sections:
            with st.expander("章节字数分布", expanded=False):
                chart_df = pd.DataFrame(
                    {"字数": [s.char_count for s in profile.sections]},
                    index=[f"{s.number} {s.title[:10]}" for s in profile.sections],
                )
                # 默认蓝色会把整套纸底黑框的调子拉散 —— 指定成墨黑
                st.bar_chart(chart_df, height=260, color="#111111")

            with st.expander("章节明细", key="tbx-sections"):
                detail = pd.DataFrame(
                    [
                        {
                            "编号": s.number,
                            "标题": s.title,
                            "字数": s.char_count,
                            "段落数": len(s.body),
                        }
                        for s in profile.sections
                    ]
                )
                st.dataframe(detail, width="stretch", hide_index=True, height=280)

    st.caption(f"文件：{profile.filename}　|　检查项：文献引用、图表悬空、章节结构、标题承诺")


# ====================================================================== 预演台
@st.fragment
def rehearsal_section(actor) -> None:
    components.anchor("rehearsal")
    with st.container(key="sec-rehearsal"):
        try:
            # 标头右上角统计跟着身份走：老师看全体预演情况，学生看自己的。
            _rs = rehearsal_store.stats(student=None if actor.is_teacher else actor.name)
            components.section_head(
                "04 / 预演台",
                "答辩前，先用自己问过的问题[[考一遍自己]]",
                "Rehearsal",
                "出题依据是答疑记录，不是通用题库。只报要点覆盖、不打分；答题前不给要点 —— 那是答案。",
                meta=f"Q {_rs['questions']:02d} ／ COVER {_rs['coverage']:.0%}" if _rs["points_total"] else f"Q {_rs['questions']:02d} ／ 未预演",
            )
            _rehearsal_body(actor)
        except Exception as exc:  # noqa: BLE001
            st.error(f"预演台这一段出错：{type(exc).__name__} — {exc}")
        components.section_foot("04 / 预演台", "")


def _rehearsal_body(actor) -> None:
    all_records = qa_store.list_records()

    if actor.is_teacher:
        # 老师视角：保留「选择学生」，可以查看任意学生的预演情况。
        students = [name for name, _score in rehearsal.student_risk(all_records)]
        if not students:
            st.info("还没有答疑记录，出不了题。先去「答疑台」录入几条，或在那边的记录页载入示例数据。")
            return
        student = st.selectbox(
            "选择学生",
            students,
            key="reh_student",
            help="按「最该练」排序：取该生风险最高的主题打分为序，不是按姓名排",
        )
    else:
        # 学生视角：没有「选择学生」——你只能预演自己的答辩。
        # 数据全部跟随右上角身份：切个身份，这四张卡和画像就换成那个人。
        student = actor.name
        if not qa_store.list_records(student=student):
            components.empty(
                "你还没有答疑记录",
                "预演台按你的答疑史出题 —— 先去上方「答疑台」提几个问题，"
                "这里才能生成你的预演题单。",
            )
            return

    records = qa_store.list_records(student=student)
    profile = rehearsal.build_profile(records)
    stat = rehearsal_store.stats(student=student)
    high = sum(1 for t in profile if t.level == "高")

    components.kpi(
        [
            ("答疑记录", len(records), "这名学生的困惑史", "default"),
            ("涉及主题", len(profile), f"{high} 个高风险", "high" if high else "default"),
            ("预演题数", stat["questions"], "已作答过的题", "default"),
            (
                "要点覆盖",
                f"{stat['coverage']:.0%}" if stat["points_total"] else "—",
                "按最近一次作答",
                "good" if stat["coverage"] >= 0.8 else "default",
            ),
        ]
    )

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
            height=min(300, 56 + 36 * len(profile)),
        )
        st.caption(
            "风险 = 次数 ×1.0 + 跨阶段数 ×1.5 + 未答复 ×1.2。"
            "从开题一路问到定稿的主题，说明中间那几次答复没真正解决问题。"
        )

    latest = rehearsal_store.latest_by_question(rehearsal_store.list_attempts(student=student))

    tab_plan, tab_log = st.tabs(["出题与作答", "预演记录"])

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
                # key 前缀决定左条颜色：未预演的题要显眼，已答过的退后
                state = "done" if prev else "todo"
                head = (
                    f"{idx:02d}　【风险 {item.priority} · {q.topic}】{q.text[:32]}"
                    f"　·　{'已预演' if prev else '未预演'}"
                )

                with st.expander(head, expanded=(not prev and idx == 1), key=f"tbx-{state}-{idx}"):
                    st.markdown(f"**{q.text}**")
                    components.meta_line([f"风险 {item.priority}", q.topic, "已预演" if prev else "未预演"])
                    st.caption(f"评委为什么问这个：{q.why}")
                    for r in item.reasons:
                        st.caption(f"· 为什么挑这道：{r}")

                    if prev:
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
                        height=100,
                        placeholder="先说结论，再说依据。别写「我认为很重要」这种话。",
                    )

                    b1, b2, _sp = st.columns([1, 1.2, 2])
                    if b1.button("提交自评", key=f"sub_{idx}", type="primary"):
                        ans = (st.session_state.get(f"ans_{plan['token']:.0f}_{idx}_{ver}") or answer or "").strip()
                        # 不用 st.stop()：那会把下面的题目一起清掉，用户以为页面坏了
                        if not ans:
                            st.warning("先写点什么再提交，哪怕只有一句结论。")
                        else:
                            g = rehearsal.grade(ans, q)
                            rehearsal_store.save(
                                student=student,
                                question=q.text,
                                answer=ans,
                                hit=g.hit,
                                total=g.total,
                                level=g.level,
                                topic=q.topic,
                                missing="、".join(g.missing),
                                source_ids=item.source_ids,
                            )
                            st.session_state[f"reh_ver_{idx}"] = ver + 1  # 换个控件，输入框清空
                            st.rerun(scope="fragment")

                    cfg = load_config()
                    if b2.button(
                        "让 AI 评委追问",
                        key=f"ai_{idx}",
                        disabled=not (prev and cfg.configured),
                        help=(
                            "提交之后才能追问"
                            if not prev
                            else ("需要先配置模型密钥" if not cfg.configured else "根据你的回答生成追问")
                        ),
                    ):
                        with st.status("评委正在读你的回答…", expanded=True) as _st:
                            st.caption(f"对照考察要点 {len(q.points)} 个，找没交代清楚的地方")
                            st.caption("组织追问中，逐字返回")
                            text = st.write_stream(
                                chat_stream(
                                    cfg,
                                    FOLLOWUP_SYSTEM_PROMPT,
                                    _build_followup(q.text, tuple(p.name for p in q.points), prev.answer),
                                    max_tokens=300,
                                    temperature=0.4,
                                )
                            )
                            if STREAM_ERROR_MARK in text:
                                err = text.split(STREAM_ERROR_MARK)[-1].strip("：] ")
                                text = ""
                                _st.update(label="追问生成失败", state="error")
                                st.error(f"追问生成失败：{err}　也可以先看下面的考察要点自查。")
                            else:
                                _st.update(label=f"追问已生成 · {len(text)} 字", state="complete")
                        if text:
                            rehearsal_store.attach_ai_note(prev.id, text)
                            st.rerun(scope="fragment")

                    # 答完再点这个 —— 顺序反了就等于抄答案
                    with st.expander("查看考察要点"):
                        st.caption("真答完再对照，才知道盲区在哪。答之前看等于抄答案。")
                        st.markdown("\n".join(f"- {p.name}" for p in q.points))
                        st.markdown(f"**可能的追问**：{q.follow_up}")

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
                height=min(320, 56 + 36 * len(rows)),
            )

            components.section("逐题轨迹", "答辩前最该看的不是分数，是这条线在不在往上走")

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
