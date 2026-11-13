"""界面交互回归 —— 守几个被用户当场发现的 session_state 坑。

1. 身份切换曾经被 index 锁死：无 key 的 selectbox 每轮按 index 重置值，
   而 index 又来自 session_state，两者互相喂 —— 手动切成功，下一轮弹回去。
2. 档案编辑表单的控件没绑身份，切学生会把上一个人的题目和导师带过来，
   于是"只读值"和"下拉里的值"同屏给出两个答案。
3. 提交按钮曾经用 `disabled=not text.strip()`：text_area 失焦前值不回写，
   按钮永远灰着，用户必须先点一下输入框外面。

**单页化之后**：没有 pages/ 目录，也没有 switch_page。
所有区块在同一页里，身份切换走顶栏那个 popover（key 以 `pop_name_` 开头）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core import qa_seed, qa_store, rehearsal_store

APP = Path(__file__).resolve().parent.parent / "app.py"


@pytest.fixture()
def app(tmp_path, monkeypatch):
    """用临时库跑真实入口，避免碰 data/ 里的演示数据。"""
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(qa_store, "DB_PATH", tmp_path / "qa.db")
    monkeypatch.setattr(rehearsal_store, "DB_PATH", tmp_path / "reh.db")
    qa_seed.load_seed(db_path=tmp_path / "qa.db")

    at = AppTest.from_file(str(APP), default_timeout=120)
    at.run()
    return at


def _profile(at) -> tuple[str | None, str | None]:
    """表单下拉里的指导老师 / 论文题目。"""
    adv = [s.value for s in at.selectbox if s.label == "指导老师"]
    title = [t.value for t in at.text_input if t.label == "论文题目"]
    return (adv[0] if adv else None), (title[0] if title else None)


def _switch(at, name: str) -> None:
    """走顶栏 popover 里那个姓名下拉 —— 和用户真实操作同一条路径。"""
    box = [s for s in at.selectbox if (s.key or "").startswith("pop_name")][0]
    box.set_value(name)
    at.run()


def _switch_role(at, role: str) -> None:
    box = [r for r in at.radio if (r.key or "").startswith("pop_role")][0]
    box.set_value(role)
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


def test_submit_button_clickable_without_blur(app):
    """提交按钮不能依赖 text_area 的实时值来决定是否可点。

    text_area 要等失焦（或 Ctrl+Enter）才写回 session_state，
    所以 `disabled=not text.strip()` 在打字过程中永远看到旧值 ——
    按钮一直灰着，用户必须先点一下输入框外面才能提交。
    """
    btn = [b for b in app.button if b.label == "提交问题"][0]
    assert not btn.disabled, "输入框为空时按钮也不该禁用，否则用户输入后它仍然是灰的"


def test_empty_submit_warns_instead_of_crashing(app):
    """点了但没写内容：给提示，不炸，也不生成空记录。"""
    btn = [b for b in app.button if b.label == "提交问题"][0]
    btn.click()
    app.run()
    assert not app.exception
    assert any("请先填写问题内容" in w.value for w in app.warning)


def test_teacher_view_appears_in_same_page(app):
    """切到老师身份后，同一页里必须出现待办控件 —— 不再有"老师端"这个页面。

    这是合并答疑台与老师端的验收点：身份一换，02 区块整个变形。
    """
    _switch_role(app, "老师")
    assert app.session_state.get("actor_role") == "老师"

    ok = [b for b in app.button if b.label == "通过并入库"]
    assert ok, "切到老师身份后，同一页里应该出现待办"
    assert all(b.disabled for b in ok), "未勾选「我已核对」时「通过并入库」必须禁用"

    chk = [c for c in app.checkbox if c.label.startswith("我已核对")][0]
    chk.check()
    app.run()
    ok = [b for b in app.button if b.label == "通过并入库"]
    assert not ok[0].disabled, "勾选后应可点击"


def test_student_view_has_no_teacher_tools(app):
    """学生身份下不该出现「通过并入库」—— 两套视图不能同时渲染。"""
    assert app.session_state.get("actor_role") == "学生"
    assert not [b for b in app.button if b.label == "通过并入库"]
    assert [b for b in app.button if b.label == "提交问题"]
