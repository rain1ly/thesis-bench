"""答疑存储层测试 —— 全部用临时数据库，不碰 data/qa.db 里的演示数据。"""
from __future__ import annotations

import pytest

from core import qa_store


@pytest.fixture()
def db(tmp_path):
    return tmp_path / "test_qa.db"


def test_add_and_list(db):
    rid = qa_store.add_question("张三", "数据不够怎么办？", stage="开题", db_path=db)
    assert rid > 0
    recs = qa_store.list_records(db_path=db)
    assert len(recs) == 1
    assert recs[0].student == "张三"
    assert recs[0].stage == "开题"
    assert recs[0].status == "待审核"


def test_review_flow(db):
    rid = qa_store.add_question("张三", "数据不够怎么办？", db_path=db)
    qa_store.review(rid, "已通过", answer="补充说明数据边界。", db_path=db)

    r = qa_store.list_records(db_path=db)[0]
    assert r.status == "已通过"
    assert r.final_answer == "补充说明数据边界。"
    assert r.answered
    assert r.reviewed_at  # 审核时间要落库，否则无法追溯


def test_review_rejects_unknown_status(db):
    rid = qa_store.add_question("张三", "问题", db_path=db)
    with pytest.raises(ValueError):
        qa_store.review(rid, "随便写的状态", db_path=db)


def test_reviewer_answer_overrides_ai_draft(db):
    """导师改过的答案必须盖过 AI 草稿 —— 这是「AI 只起草」的落地点。"""
    rid = qa_store.add_question("张三", "问题", ai_draft="AI 的草稿", db_path=db)
    assert qa_store.list_records(db_path=db)[0].final_answer == "AI 的草稿"

    qa_store.review(rid, "已通过", answer="导师修订后的答复", db_path=db)
    assert qa_store.list_records(db_path=db)[0].final_answer == "导师修订后的答复"


def test_find_similar_hits(db):
    qa_store.add_question("张三", "样本量只有300条，做回归够吗？", db_path=db)
    hits = qa_store.find_similar("我的数据只有200条，做回归够吗", qa_store.list_records(db_path=db))
    assert hits
    assert hits[0][0] >= 0.3
    assert "回归" in hits[0][1].question


def test_find_similar_misses_unrelated(db):
    qa_store.add_question("张三", "样本量只有300条，做回归够吗？", db_path=db)
    hits = qa_store.find_similar("致谢要写多长", qa_store.list_records(db_path=db))
    assert hits == []


def test_find_similar_empty_input(db):
    qa_store.add_question("张三", "问题", db_path=db)
    assert qa_store.find_similar("   ", qa_store.list_records(db_path=db)) == []


def test_stats(db):
    qa_store.add_question("张三", "q1", db_path=db)
    qa_store.add_question("李四", "q2", db_path=db)
    rid = qa_store.add_question("张三", "q3", db_path=db)
    qa_store.review(rid, "已通过", answer="a", db_path=db)

    s = qa_store.stats(db_path=db)
    assert s["total"] == 3
    assert s["students"] == 2
    assert s["已通过"] == 1
    assert s["待审核"] == 2


def test_seed_is_idempotent(tmp_path):
    """重复点「载入示例数据」不能把数据灌两倍。"""
    from core.qa_seed import load_seed

    db = tmp_path / "seed.db"
    first = load_seed(db_path=db)
    second = load_seed(db_path=db)
    assert first > 0
    assert second == 0
    assert qa_store.stats(db_path=db)["total"] == first
