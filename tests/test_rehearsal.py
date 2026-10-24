"""预演台内核测试 —— 不碰 data/ 里的演示数据，全部用内存/临时库。

这里断言的重点不是"能跑"，而是三个设计承诺有没有被写死：
1. 跨阶段重复提问的风险必须高于单次提问（否则出题依据就散了）；
2. 题目必须能追回它来自哪几条答疑（否则"用你自己的困惑出题"是空话）；
3. 空答不能算 0 分（"没答"和"答错"是两回事）。
"""
from __future__ import annotations

from core import rehearsal, rehearsal_store
from core.qa_store import QARecord


def rec(id_, student="陈同学", stage="开题", tag="数据来源", answer="已答", question="数据怎么办？") -> QARecord:
    return QARecord(
        id=id_,
        student=student,
        stage=stage,
        question=question,
        ai_draft="",
        answer=answer,
        status="已通过" if answer else "待审核",
        tags=tag,
        reviewer_note="",
        created_at="2026-10-01 10:00",
        reviewed_at="",
    )


# ------------------------------------------------------------------ 风险画像
def test_profile_groups_by_tag():
    recs = [rec(1, tag="数据来源"), rec(2, tag="数据来源"), rec(3, tag="图表规范")]
    profile = {t.topic: t for t in rehearsal.build_profile(recs)}
    assert profile["数据来源"].count == 2
    assert profile["图表规范"].count == 1


def test_cross_stage_outranks_single_mention():
    """同一主题问 2 次、跨 2 个阶段，必须比问 2 次挤在同阶段更危险。"""
    spread = [rec(1, stage="开题"), rec(2, stage="定稿")]
    dense = [rec(3, stage="开题"), rec(4, stage="开题")]
    p_spread = rehearsal.build_profile(spread)[0]
    p_dense = rehearsal.build_profile(dense)[0]
    assert p_spread.score > p_dense.score
    assert p_spread.spread == 2 and p_dense.spread == 1


def test_unanswered_lifts_risk():
    answered = [rec(1, answer="已答")]
    pending = [rec(2, answer="")]
    assert rehearsal.build_profile(pending)[0].score > rehearsal.build_profile(answered)[0].score


def test_profile_sorted_by_score_desc():
    recs = [rec(1, tag="查重"), rec(2, tag="数据来源"), rec(3, tag="数据来源"), rec(4, tag="数据来源")]
    scores = [t.score for t in rehearsal.build_profile(recs)]
    assert scores == sorted(scores, reverse=True)
    assert rehearsal.build_profile(recs)[0].topic == "数据来源"


def test_untagged_falls_into_unclassified_not_dropped():
    recs = [rec(1, tag="")]
    profile = rehearsal.build_profile(recs)
    assert len(profile) == 1 and profile[0].topic == "未分类"


def test_profile_empty_input():
    assert rehearsal.build_profile([]) == []


def test_student_risk_puts_most_stuck_first():
    """默认打开的学生必须是最该练的那个，不能按姓名编码排。"""
    recs = [
        rec(1, student="赵同学", tag="图表规范"),
        rec(2, student="陈同学", tag="数据来源", stage="开题"),
        rec(3, student="陈同学", tag="数据来源", stage="中期"),
        rec(4, student="陈同学", tag="数据来源", stage="定稿"),
    ]
    order = [name for name, _ in rehearsal.student_risk(recs)]
    assert order[0] == "陈同学"


# ------------------------------------------------------------------ 出题
def test_draft_is_traceable_to_records():
    """题单必须带答疑记录 id —— 这是「用他自己的困惑出题」的唯一证据。"""
    recs = [rec(11, tag="数据来源"), rec(12, tag="数据来源", stage="定稿")]
    plan = rehearsal.draft(recs, limit=3)
    assert plan
    first = plan[0]
    assert first.question.topic == "数据来源"
    assert set(first.source_ids.split(",")) == {"11", "12"}


def test_draft_respects_limit():
    recs = [rec(i, tag=tag) for i, tag in enumerate(["数据来源", "图表规范", "实验设计", "问卷方法"], start=1)]
    assert len(rehearsal.draft(recs, limit=3)) == 3
    assert len(rehearsal.draft(recs, limit=0)) == 0


def test_draft_caps_two_questions_per_topic():
    """同一主题连出三道意义不大，会挤掉别的考点。"""
    recs = [rec(i, tag="数据来源") for i in range(1, 8)]
    plan = rehearsal.draft(recs, limit=4)
    topics = [p.question.topic for p in plan]
    assert topics.count("数据来源") == 2


def test_draft_fills_with_essentials():
    """题库里没有的主题不能硬凑题，要用通用必答题补齐。

    补齐后如果还不够 limit，就让它短着 —— 题库只有 3 道通用题，
    硬凑第 4 道意味着要编题，学生一眼能看出来。
    """
    recs = [rec(1, tag="完全不存在的主题")]
    plan = rehearsal.draft(recs, limit=5)
    assert [p.question.topic for p in plan] == ["通用"] * len(rehearsal.ESSENTIALS)


def test_draft_covers_seed_tags():
    """题库要覆盖答疑数据里出现过的标签，否则真实数据会大量走兜底。"""
    from core.qa_seed import SEED

    tags = {row[5] for row in SEED}
    assert tags <= set(rehearsal.BANK), f"题库缺标签：{tags - set(rehearsal.BANK)}"


def test_every_question_has_points_followup_why():
    pool = [q for qs in rehearsal.BANK.values() for q in qs] + list(rehearsal.ESSENTIALS)
    for q in pool:
        assert q.points, q.text
        assert q.follow_up, q.text
        assert q.why, q.text
        for p in q.points:
            assert p.keywords, f"{q.topic}/{p.name} 没有关键词，永远判不中"


# ------------------------------------------------------------------ 判分
def _q() -> rehearsal.Question:
    return rehearsal.BANK["数据来源"][0]


def test_grade_empty_is_not_zero_score():
    g = rehearsal.grade("   ", _q())
    assert g.level == "未作答"
    assert g.hit == 0
    assert len(g.missing) == g.total


def test_grade_full_coverage():
    answer = "数据来自公开数据集，但局限是传感器型号不同，我做了量纲映射和字段对齐。"
    g = rehearsal.grade(answer, _q())
    assert g.hit == g.total
    assert g.level == "扎实"
    assert g.missing == ()


def test_grade_partial_reports_missing_names():
    g = rehearsal.grade("数据来自公开数据集。", _q())
    assert 0 < g.hit < g.total
    assert "说清数据边界" in g.missing
    assert g.level in ("有缺口", "基本")


def test_grade_no_hit_is_gap():
    g = rehearsal.grade("我觉得还可以吧，老师说没问题。", _q())
    assert g.hit == 0
    assert g.level == "有缺口"


def test_grade_ignores_case():
    q = rehearsal.BANK["问卷方法"][0]
    upper = rehearsal.grade("信度用 CRONBACH 的 ALPHA，效度看 KMO。", q)
    lower = rehearsal.grade("信度用 cronbach 的 alpha，效度看 kmo。", q)
    assert upper.hit == lower.hit


# ------------------------------------------------------------------ 存储
def test_store_save_and_latest(tmp_path):
    db = tmp_path / "reh.db"
    rehearsal_store.save("陈同学", "数据从哪来", "第一版", 1, 3, "有缺口", db_path=db)
    rehearsal_store.save("陈同学", "数据从哪来", "第二版", 3, 3, "扎实", db_path=db)

    rows = rehearsal_store.list_attempts("陈同学", db_path=db)
    assert len(rows) == 2  # 重答留痕，不覆盖
    latest = rehearsal_store.latest_by_question(rows)
    assert latest["数据从哪来"].hit == 3
    assert latest["数据从哪来"].passed


def test_store_stats_counts_latest_only(tmp_path):
    db = tmp_path / "reh.db"
    rehearsal_store.save("陈同学", "q1", "a", 1, 3, "有缺口", db_path=db)
    rehearsal_store.save("陈同学", "q1", "a", 3, 3, "扎实", db_path=db)
    rehearsal_store.save("陈同学", "q2", "", 0, 3, "未作答", db_path=db)

    s = rehearsal_store.stats("陈同学", db_path=db)
    assert s["attempts"] == 3
    assert s["questions"] == 2
    assert s["passed"] == 1
    assert s["points_hit"] == 3
    assert s["points_total"] == 6
    assert s["coverage"] == 0.5


def test_store_attaches_ai_note_without_touching_score(tmp_path):
    db = tmp_path / "reh.db"
    rid = rehearsal_store.save("陈同学", "q", "a", 2, 3, "基本", db_path=db)
    rehearsal_store.attach_ai_note(rid, "1. 那 300 条里剔除过异常吗？", db_path=db)

    a = rehearsal_store.list_attempts("陈同学", db_path=db)[0]
    assert "剔除" in a.ai_note
    assert a.hit == 2  # AI 只加话，不改判分结果


def test_store_improvement_is_chronological(tmp_path):
    db = tmp_path / "reh.db"
    rehearsal_store.save("陈同学", "q", "v1", 0, 3, "有缺口", db_path=db)
    rehearsal_store.save("陈同学", "q", "v2", 2, 3, "基本", db_path=db)
    trail = rehearsal_store.improvement("陈同学", "q", db_path=db)
    assert [a.hit for a in trail] == [0, 2]


def test_store_stats_empty(tmp_path):
    s = rehearsal_store.stats(None, db_path=tmp_path / "empty.db")
    assert s["questions"] == 0 and s["coverage"] == 0.0
