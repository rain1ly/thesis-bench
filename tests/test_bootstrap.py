"""启动自愈层测试。

这层管的是「第一次打开能不能看到东西」和「能不能安全清空」，两件事都会出事故：
1. 清空按钮如果不生效（刷新又长回来），演示时点一下等于当众承认 bug；
2. 清空如果不设防，真实学生数据会被一键抹掉——这个损失没法挽回。
所以两条都要断言。
"""
from __future__ import annotations

import pytest

from core import bootstrap, qa_store, rehearsal_store


@pytest.fixture()
def db(tmp_path):
    return tmp_path / "qa.db"


@pytest.fixture()
def rdb(tmp_path):
    return tmp_path / "reh.db"


def test_ensure_demo_fills_empty_db(db):
    n = bootstrap.ensure_demo(db_path=db)
    assert n > 0
    assert qa_store.stats(db_path=db)["total"] == n


def test_ensure_demo_is_idempotent(db):
    first = bootstrap.ensure_demo(db_path=db)
    second = bootstrap.ensure_demo(db_path=db)
    assert first > 0
    assert second == 0
    assert qa_store.stats(db_path=db)["total"] == first


def test_is_demo_after_load(db):
    bootstrap.ensure_demo(db_path=db)
    assert bootstrap.is_demo(db_path=db) is True


def test_is_demo_false_on_empty(db):
    assert bootstrap.is_demo(db_path=db) is False


def test_is_demo_recognises_legacy_seed_without_flag(db):
    """加 meta 标记之前建的库没有标记，靠学生名认出来。"""
    from core.qa_seed import SEED

    qa_store.add_question(SEED[0][0], "老库里的问题", db_path=db)
    assert qa_store.get_meta("demo", db_path=db) == ""
    assert bootstrap.is_demo(db_path=db) is True


def test_is_demo_false_for_real_student(db):
    from core.qa_seed import SEED

    qa_store.add_question(SEED[0][0], "示例学生提的问题", db_path=db)
    qa_store.add_question("真实的张三", "我的问题", db_path=db)
    assert bootstrap.is_demo(db_path=db) is False


def test_clear_demo_removes_both_stores(db, rdb):
    bootstrap.ensure_demo(db_path=db)
    rehearsal_store.save("陈同学", "题目", "答案", 2, 3, "基本", db_path=rdb)

    n_qa, n_reh = bootstrap.clear_demo(db_path=db, rehearsal_db=rdb)
    assert n_qa > 0
    assert n_reh == 1
    assert qa_store.stats(db_path=db)["total"] == 0
    assert rehearsal_store.list_attempts(db_path=rdb) == []


def test_cleared_db_does_not_auto_refill(db, rdb):
    """清空后刷新又长回来，等于清空按钮是假的。"""
    bootstrap.ensure_demo(db_path=db)
    bootstrap.clear_demo(db_path=db, rehearsal_db=rdb)

    assert bootstrap.ensure_demo(db_path=db) == 0
    assert qa_store.stats(db_path=db)["total"] == 0
    assert bootstrap.is_demo(db_path=db) is False


def test_manual_reload_turns_demo_back_on(db, rdb):
    bootstrap.ensure_demo(db_path=db)
    bootstrap.clear_demo(db_path=db, rehearsal_db=rdb)

    from core.qa_seed import load_seed

    assert load_seed(db_path=db) > 0
    assert bootstrap.is_demo(db_path=db) is True
    assert bootstrap.ensure_demo(db_path=db) == 0  # 已有数据，不重复灌


def test_clear_demo_refuses_real_data(db, rdb):
    qa_store.add_question("真实的张三", "我的问题", db_path=db)
    with pytest.raises(ValueError):
        bootstrap.clear_demo(db_path=db, rehearsal_db=rdb)
    assert qa_store.stats(db_path=db)["total"] == 1  # 一条没删


def test_clear_demo_on_empty_db_refuses(db, rdb):
    with pytest.raises(ValueError):
        bootstrap.clear_demo(db_path=db, rehearsal_db=rdb)
