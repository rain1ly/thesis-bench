"""身份与可见性测试。

这一层最怕的不是功能不对，是**越界**：学生的隐私问题被别的老师看见，
或者被当成"公开池里没人认领"派出去。所以断言写得比功能测试狠一点。
"""
from __future__ import annotations

import sqlite3

import pytest

from core import identity, qa_seed, qa_store
from core.identity import Actor
from core.qa_store import QARecord

ADVISOR = Actor(role="老师", name="张老师")
OTHER = Actor(role="老师", name="刘老师")
STUDENT = Actor(role="学生", name="陈同学")
OTHER_STUDENT = Actor(role="学生", name="李同学")


@pytest.fixture()
def db(tmp_path):
    return tmp_path / "qa.db"


def rec(id_=1, student="陈同学", status="待审核", assigned="张老师", vis="公开", answer="") -> QARecord:
    return QARecord(
        id=id_,
        student=student,
        stage="中期",
        question="问题",
        ai_draft="",
        answer=answer,
        status=status,
        tags="数据来源",
        reviewer_note="",
        created_at="2026-10-20 10:00",
        reviewed_at="",
        category="数据分析",
        visibility=vis,
        assigned_to=assigned,
        thesis_title="智能温室监控系统",
    )


# ------------------------------------------------------------------ 迁移
def test_migration_adds_columns_to_old_table(db):
    """老库（没有 category 等四列）打开后必须能读，且默认值合理。"""
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE qa (
            id INTEGER PRIMARY KEY AUTOINCREMENT, student TEXT NOT NULL,
            stage TEXT NOT NULL DEFAULT '开题', question TEXT NOT NULL,
            ai_draft TEXT NOT NULL DEFAULT '', answer TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT '待审核', tags TEXT NOT NULL DEFAULT '',
            reviewer_note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
            reviewed_at TEXT NOT NULL DEFAULT ''
        );
        INSERT INTO qa (student, question, status, created_at)
        VALUES ('老学生', '老问题', '待审核', '2026-09-01 10:00');
        """
    )
    conn.commit()
    conn.close()

    rows = qa_store.list_records(db_path=db)
    assert len(rows) == 1
    assert rows[0].category == "论文写作"
    assert rows[0].visibility == "公开"
    assert rows[0].assigned_to == ""


def test_migration_is_idempotent(db):
    qa_store.upsert_student("陈同学", "题目A", "张老师", db_path=db)
    for _ in range(3):
        assert qa_store.all_students(db_path=db)[0]["thesis_title"] == "题目A"


# ------------------------------------------------------------------ 可见性
def test_private_question_hidden_from_other_teacher():
    assert identity.can_view(rec(vis="隐私", assigned="张老师"), ADVISOR) is True
    assert identity.can_view(rec(vis="隐私", assigned="张老师"), OTHER) is False


def test_private_without_assignee_is_hidden_from_everyone():
    """兜底：隐私但没指定老师（历史脏数据）。宁可谁都看不见，也不能越界。"""
    r = rec(vis="隐私", assigned="")
    for actor in (ADVISOR, OTHER):
        assert identity.can_view(r, actor) is False


def test_student_sees_own_questions_only():
    mine = rec(student="陈同学")
    others_public = rec(student="李同学", status="已通过", vis="公开")
    others_private = rec(student="李同学", status="已通过", vis="隐私")

    assert identity.can_view(mine, STUDENT) is True
    assert identity.can_view(others_public, STUDENT) is True
    assert identity.can_view(others_private, STUDENT) is False


def test_student_cannot_see_others_unapproved():
    """别人还没通过的问题，即使标了公开，也不该提前露出来。"""
    r = rec(student="李同学", status="待审核", vis="公开")
    assert identity.can_view(r, STUDENT) is False


def test_teacher_sees_public_pool():
    assert identity.can_view(rec(assigned="", vis="公开"), OTHER) is True


# ------------------------------------------------------------------ 待办
def test_inbox_includes_assigned_and_public_pool():
    records = [
        rec(1, assigned="张老师"),
        rec(2, student="李同学", assigned=""),          # 公开池
        rec(3, student="王同学", assigned="刘老师"),     # 别人的
    ]
    ids = [r.id for r in identity.inbox(records, "张老师")]
    assert ids == [1, 2]


def test_inbox_excludes_answered():
    records = [rec(1, status="已通过", answer="答过了")]
    assert identity.inbox(records, "张老师") == []


def test_inbox_puts_assigned_first():
    records = [
        rec(1, student="李同学", assigned=""),      # 公开池，时间更晚
        rec(2, student="陈同学", assigned="张老师"),
    ]
    records[0] = rec(1, student="李同学", assigned="")
    records[0].__dict__["created_at"] = "2026-10-25 10:00"
    assert identity.inbox(records, "张老师")[0].id == 2


def test_public_pool_excludes_private():
    records = [rec(1, assigned="", vis="隐私"), rec(2, assigned="", vis="公开")]
    assert [r.id for r in identity.public_pool(records)] == [2]


# ------------------------------------------------------------------ 学生名单
def test_my_students_shows_thesis_title_and_risk():
    records = [
        rec(1, student="陈同学", assigned="张老师"),
        rec(2, student="陈同学", assigned="张老师"),
        rec(3, student="陈同学", assigned="张老师"),
    ]
    rows = {r["学生"]: r for r in identity.my_students("张老师", records)}
    assert rows["陈同学"]["未答复"] == 3
    assert rows["陈同学"]["风险"] == "高"
    assert rows["陈同学"]["论文题目"] or rows["陈同学"]["论文题目"] == "（未填写）"


# ------------------------------------------------------------------ 入库校验
def test_add_question_rejects_unknown_category(db):
    with pytest.raises(ValueError):
        qa_store.add_question("陈同学", "q", category="随便写的", db_path=db)


def test_add_question_rejects_unknown_visibility(db):
    with pytest.raises(ValueError):
        qa_store.add_question("陈同学", "q", visibility="半公开", db_path=db)


def test_seed_private_questions_always_have_advisor(db):
    qa_seed.load_seed(db_path=db)
    private = [r for r in qa_store.list_records(db_path=db) if r.is_private]
    assert private, "示例数据里应该有隐私问题，否则演示不到这条路径"
    assert all(r.assigned_to for r in private)


def test_seed_has_public_pool_for_demo(db):
    """公开池必须非空，否则"公开给所有老师"这条路演示不出来。"""
    qa_seed.load_seed(db_path=db)
    assert identity.public_pool(qa_store.list_records(db_path=db))


def test_seed_students_have_thesis_titles(db):
    qa_seed.load_seed(db_path=db)
    rows = qa_store.all_students(db_path=db)
    assert len(rows) == 4
    assert all(r["thesis_title"] and r["advisor"] for r in rows)
