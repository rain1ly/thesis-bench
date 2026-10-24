"""启动自愈 —— 保证任何人第一次打开，看到的都是满的。

这件事的起因很具体：`qa.db` 被 `.gitignore` 忽略，仓库里一条数据都没有。
评委 clone 下来跑，或者点开云端链接，进「预演台」看到的是
「还没有答疑记录，出不了题」——要先摸到答疑台的第三个 tab 点两下才看得见东西。
主打卖点在第一屏是空的，演示价值当场折一半。

所以它解决两个真问题，不是演示技巧：

1. **首次访问体验。** 也是省赛视频的第一镜，不能是一句提示。
2. **云端数据存活。** Streamlit Cloud 的容器文件系统是临时的，重启就丢库；
   有自愈逻辑，库自己会重新长出来，不用人守着点按钮。

一条纪律：**能自动载入，也能安全清空。**
清空前必须确认「这库是示例数据」——真实学生数据不允许被一键抹掉。
判断依据是 meta 表里的 demo 标记，外加一条兼容规则（见 is_demo）。
"""

from __future__ import annotations

from pathlib import Path

from core import qa_store, rehearsal_store
from core.qa_seed import load_seed, seed_students


def ensure_demo(db_path: str | Path | None = None) -> int:
    """库空则载入示例，返回载入条数；已有数据则什么都不做。

    幂等由 load_seed 保证（非空库不重复插入），这里只管判断"该不该动手"。

    但用户点过「清空」之后不能又自动灌回来 —— 那样清空按钮就成了笑话。
    所以留一个 demo_off 开关：显式清空过一次，就不再自动载入，
    想恢复得自己去答疑台点「载入示例数据」。
    """
    if qa_store.get_meta("demo_off", db_path=db_path) == "1":
        return 0
    if qa_store.stats(db_path)["total"] > 0:
        return 0
    return load_seed(db_path)


def is_demo(db_path: str | Path | None = None) -> bool:
    """这个库是示例数据吗？

    优先看 meta 标记。老库（加标记之前建的）没有标记，退一步按学生名判断：
    所有提问者的名字都落在示例名单里，就按示例数据对待。

    这条兼容规则有误判的可能 —— 如果用户自己录了一个叫「陈同学」的真实学生，
    也会被判成示例。代价是可以接受的：判错的后果只是多显示一行说明，
    而判不出来的后果是把真实数据当演示，那更糟。
    """
    if qa_store.get_meta("demo", db_path=db_path) == "1":
        return True

    rows = qa_store.list_records(db_path=db_path)
    if not rows:
        return False
    return {r.student for r in rows} <= seed_students()


def clear_demo(db_path: str | Path | None = None, rehearsal_db: str | Path | None = None) -> tuple[int, int]:
    """清空示例数据，返回 (答疑条数, 预演条数)。

    两个库必须一起清：预演记录的 source_ids 指回答疑记录，
    只清一边会留下一堆指向不存在记录的题单，比不清更糟。
    """
    if not is_demo(db_path):
        raise ValueError("当前库不是示例数据，拒绝清空。真实数据请手工处理。")

    n_qa = qa_store.clear_all(db_path)
    n_reh = rehearsal_store.clear_all(rehearsal_db)
    # 记下"用户主动清过"，否则下次刷新 ensure_demo 又把示例灌回来
    qa_store.set_meta("demo_off", "1", db_path)
    return n_qa, n_reh


def demo_notice(expanded: bool = False) -> None:
    """页面顶部的数据来源说明。

    示例数据是模拟的，就必须标出来 —— 伪装成真实访谈记录是最容易被评委一句话拆穿的事。
    """
    import streamlit as st

    if not is_demo():
        return

    n = qa_store.stats()["total"]
    if expanded:
        st.info(
            f"**当前为示例数据**：{n} 条模拟答疑，4 条虚构学生线（数据焦虑 / 图表规范 / 实验设计 / 问卷方法），"
            "用于演示流程与冷启动，不是真实访谈记录。清空入口在首页。"
        )
    else:
        st.caption(f"数据来源：{n} 条模拟答疑（虚构学生，非真实访谈）")
