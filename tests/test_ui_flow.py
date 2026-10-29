"""界面交互回归 —— 守两个被用户当场发现的 session_state 坑。

这两个 bug 都不是"功能没做"，而是**状态串了**：
1. 身份切换器的 selectbox 没有 key，却每轮传 index（index 又来自 session_state），
   两者互相喂，控件被锁死 —— 手动切身份看着成功，下一轮弹回去；
2. 档案编辑表单的控件没有绑定身份，切学生会把上一个人的题目和导师带过来，
   于是"顶部只读值"和"下拉里的值"同屏给出两个答案。

AppTest 能跑真实脚本、真实 session_state，所以这类问题只能用交互测。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import qa_store, qa_seed, rehearsal_store


@pytest.fixture()
def app(tmp_path, monkeypatch):
    """用临时库跑真实入口，避免碰 data/ 里的演示数据。"""
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(qa_store, "DB_PATH", tmp_path / "qa.db")
    monkeypatch.setattr(rehearsal_store, "DB_PATH", tmp_path / "reh.db")
    qa_seed.load_seed(db_path=tmp_path / "qa.db")

    at = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"), default_timeout=90)
    at.run()
    at.switch_page("pages/1_答疑台.py")
    at.run()
    return at


def _profile(at) -> tuple[str | None, str | None]:
    """当前页上，表单下拉里的指导老师 / 论文题目。"""
    adv = [s.value for s in at.selectbox if s.label == "指导老师"]
    title = [t.value for t in at.text_input if t.label == "论文题目"]
    return (adv[0] if adv else None), (title[0] if title else None)


def _switch(at, name: str):
    who = [s for s in at.selectbox if s.label == "身份"][0]
    who.set_value(name)
    at.run()


def test_identity_switch_actually_switches(app):
    """切换身份必须真的换人 —— 不能被 index 锁死。"""
    assert app.session_state.get("actor_name") == "陈同学"
    _switch(app, "李同学")
    assert app.session_state.get("actor_name") == "李同学"


def test_profile_follows_identity(app):
    """切学生后，表单里的导师和题目要跟着换，切回来要还原。"""
    assert _profile(app)[0] == "张老师"

    _switch(app, "李同学")
    adv, title = _profile(app)
    assert adv == "刘老师"
    assert "Spring Boot" in title

    _switch(app, "陈同学")
    adv, title = _profile(app)
    assert adv == "张老师", "切回来还留着上一个学生的导师 —— session_state 串值了"
    assert "智能温室" in title


def test_route_labels_use_current_advisor(app):
    """「答疑老师」里复述的导师名，必须和档案一致，不能各说各的。"""
    route = [r for r in app.radio if r.label == "答疑老师"][0]
    assert route.options[0] == "我的指导老师（张老师）"

    _switch(app, "李同学")
    route = [r for r in app.radio if r.label == "答疑老师"][0]
    assert route.options[0] == "我的指导老师（刘老师）"


def test_private_question_has_no_public_pool_option(app):
    """隐私 + 公开池是矛盾组合：选了隐私就不该出现「公开给所有老师」。"""
    vis = [r for r in app.radio if r.label == "可见性"][0]
    vis.set_value("隐私")
    app.run()
    route = [r for r in app.radio if r.label == "答疑老师"][0]
    assert "公开给所有老师" not in route.options
