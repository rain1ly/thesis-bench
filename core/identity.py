"""身份与可见性 —— 导师反馈之后新增的一层。

**这里要交代一次判断被推翻的过程，否则半年后没人知道为什么突然多了个表。**

10-24 的判断是：「不做用户体系，一个学生名就是字符串，等真要多角色登录了再拆」。
当时的理由站得住：这一阶段的目标是把闭环跑通并演示清楚。

10-29 导师一句话把前提推翻了。他问的不是"能不能加个登录框"，而是四件业务事实：
1. 学生和指导老师没有绑定；
2. 老师那边看不到论文题目；
3. 公开和隐私没有边界（学生的困惑可能不想让全班看见）；
4. 提问没有分类，老师无从判断该谁接。

这四条不是"技术复杂度"，是**数据模型缺了东西**。补关系的成本远小于让场景不成立。

所以这一层只做两件事：**关系** 和 **规则**。不做密码：
Streamlit 没有原生账号体系，硬上认证库等于给自己加一道演示失败点。
身份切换器代替登录，生产环境接学校统一认证 —— 这条写在技术文档里，不藏着。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core import qa_store
from core.qa_store import QARecord

ROLES = ("学生", "老师")


@dataclass(frozen=True)
class Actor:
    role: str
    name: str

    @property
    def is_teacher(self) -> bool:
        return self.role == "老师"

    @property
    def label(self) -> str:
        return f"{self.role} · {self.name}"


# ------------------------------------------------------------------ 名册
def teacher_names(db_path: str | Path | None = None) -> list[str]:
    """教师名单，被指派问题多的排前面。

    和学生名单同一个道理：默认身份该落在"有活干"的人身上，
    而不是按姓名字典序碰巧排第一的那个。演示时第一屏才有内容。
    """
    names = qa_store.teacher_names(db_path)
    if not names:
        return ["张老师"]
    load: dict[str, int] = {}
    for r in qa_store.list_records(db_path=db_path):
        if r.assigned_to:
            load[r.assigned_to] = load.get(r.assigned_to, 0) + 1
    return sorted(names, key=lambda n: (-load.get(n, 0), n))


def student_names(db_path: str | Path | None = None) -> list[str]:
    """学生名单，提问多的排前面。

    默认身份取第一个 —— 演示第一屏应该落在最活跃、最有故事的学生身上，
    而不是按姓名编码碰巧排第一的那个。和预演台「默认打开最该练的学生」同一个道理。
    """
    names = qa_store.student_names(db_path)
    counts: dict[str, int] = {}
    for r in qa_store.list_records(db_path=db_path):
        counts[r.student] = counts.get(r.student, 0) + 1
    ordered = sorted(names, key=lambda n: (-counts.get(n, 0), n))
    return ordered or ["陈同学"]


# ------------------------------------------------------------------ 可见性（纯函数，可测）
def can_view(record: QARecord, actor: Actor) -> bool:
    """这条答疑记录，当前身份能不能看。

    规则按"谁有权知道什么"排，不按"谁是管理员"排 —— 隐私问题的边界要守住：
    **它不能被当成「公开池里没人认领」而推给别的老师。**
    """
    if not actor.is_teacher:
        # 学生：自己的全部；别人的只看已通过的公开问答（沉淀区）
        if record.student == actor.name:
            return True
        return record.visibility == "公开" and record.status == "已通过"

    # 老师视角
    if record.assigned_to:
        return record.assigned_to == actor.name
    # 未指派 = 公开池。隐私问题必须指定老师，不该出现在这里；
    # 万一出现了（历史数据或误操作），宁可看不见也不要越界。
    return record.visibility == "公开"


def visible_records(records: list[QARecord], actor: Actor) -> list[QARecord]:
    return [r for r in records if can_view(r, actor)]


def inbox(records: list[QARecord], teacher: str) -> list[QARecord]:
    """老师待办：还没答复、且归我管的。

    排序：隐私优先（学生特意设了边界，更要及时），再按提交时间倒序。
    公开池里没人接的问题排在指定问题之后 —— 先把点名找你的答了。
    """
    mine = [
        r
        for r in records
        if r.status == "待审核"
        and (
            r.assigned_to == teacher
            or (not r.assigned_to and r.visibility == "公开")
        )
    ]
    # 稳定排序要用两次：先排次要键（时间），再排主键（归谁管 + 是否隐私）。
    # 反过来写的话主次会颠倒 —— 时间会变成主序，指定给我的问题被挤到最后。
    mine.sort(key=lambda r: r.created_at, reverse=True)
    mine.sort(key=lambda r: (0 if r.assigned_to == teacher else 1, 0 if r.is_private else 1))
    return mine


def public_pool(records: list[QARecord]) -> list[QARecord]:
    """公开池：没指定老师、非隐私、还没答复的。任何老师都能接。"""
    return [
        r
        for r in records
        if r.status == "待审核" and not r.assigned_to and not r.is_private
    ]


# ------------------------------------------------------------------ 身份切换（唯一有副作用的地方）
def current() -> Actor:
    """读当前身份，不渲染任何控件。给业务函数用。"""
    import streamlit as st

    role = st.session_state.get("actor_role", "学生")
    name = st.session_state.get("actor_name")
    if not name:
        name = student_names()[0] if role == "学生" else teacher_names()[0]
    return Actor(role=role, name=name)


def ensure() -> Actor:
    """消费挂起的身份切换，返回当前身份。**不渲染任何控件。**

    身份入口只有一个：顶栏右端那个 popover（`components.identity_chip`）。
    侧边栏原来那套 radio + selectbox 已经拆掉 —— 两个入口同时存在时，
    popover 每轮都会拿它自己的旧名字把身份改回去，两边互相打架
    （上一版就是这个毛病，4 条身份测试当场红掉）。

    为什么仍然需要「挂起标记」：控件一旦创建，它的 key 就不能再写
    （StreamlitAPIException: cannot be modified after the widget ... is instantiated）。
    所以切换方只写 `_actor_pending`，由这里在下一轮最开头消费。
    """
    import streamlit as st

    pending = st.session_state.pop("_actor_pending", None)
    if pending:
        p_role, p_name = pending
        st.session_state["actor_role"] = p_role
        if p_name:
            st.session_state["actor_name"] = p_name
        else:
            # 只切角色（顶栏方框里改角色那一下）：名字交给新名单的第一个
            pool = student_names() if p_role == "学生" else teacher_names()
            st.session_state["actor_name"] = pool[0]

    actor = current()
    # 把当前身份显式写回 state：current() 可能只是用了默认值而没落库，
    # 外部（测试、调试面板）读 session_state["actor_role"] 会拿到 None
    st.session_state["actor_role"] = actor.role
    st.session_state["actor_name"] = actor.name

    # 身份真的变了才提示。没有这个反馈，用户切完只看到页面闪一下，
    # 很难判断到底切没切 —— 两个身份的界面结构长得很像。
    last = st.session_state.get("_actor_last")
    if last and last != (actor.role, actor.name):
        st.toast(f"已切换：{actor.role} · {actor.name}")
    st.session_state["_actor_last"] = (actor.role, actor.name)

    return actor


# 过渡别名：旧的 pages/ 脚本仍按这个名字调用，行为与 ensure 一致
render_switcher = ensure


# ------------------------------------------------------------------ 老师端视图数据
def my_students(teacher: str, records: list[QARecord]) -> list[dict]:
    """我指导的学生：论文题目、提问数、未答复数、最近提问、风险。

    风险用「未答复 ≥3 高 / ≥1 中 / 0 低」，和答疑台原来那张画像表口径一致，
    不然两个页面给出两个风险等级，用户会先怀疑系统。
    """
    roster = [s for s in qa_store.all_students() if s.get("advisor") == teacher]
    known = {s["name"] for s in roster}
    # 指名找我的学生即使没建档也要露面，否则老师永远看不见他。
    # 只在公开池里提过问的别人家学生不进这张表 —— 那是待办的事，不是"我的学生"。
    for name in sorted({r.student for r in records if r.assigned_to == teacher and r.student not in known}):
        roster.append({"name": name, "thesis_title": "", "advisor": teacher, "major": ""})

    rows = []
    for s in roster:
        mine = [r for r in records if r.student == s["name"]]
        unanswered = sum(1 for r in mine if not r.final_answer)
        rows.append(
            {
                "学生": s["name"],
                "论文题目": s.get("thesis_title") or "（未填写）",
                "提问数": len(mine),
                "未答复": unanswered,
                "最近提问": mine[0].created_at if mine else "",
                "风险": "高" if unanswered >= 3 else ("中" if unanswered >= 1 else "低"),
            }
        )
    rows.sort(key=lambda r: (-r["未答复"], r["学生"]))
    return rows


def category_counts(records: list[QARecord]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in records:
        out[r.category] = out.get(r.category, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))
