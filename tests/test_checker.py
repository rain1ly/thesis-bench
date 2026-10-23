"""规则检查的单元测试

用 data/samples 里的两份真实样本做回归：
    第三章 智能温室监控系统的感知层设计与数据预处理.docx
    第三章 系统总体设计与数据库设计.docx

跑法：
    .venv\\Scripts\\python.exe -m pytest tests -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.checker import run_all, summary
from core.parser import parse_docx

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples"


def load(keyword: str):
    for f in SAMPLES.glob("*.docx"):
        if keyword in f.name:
            return parse_docx(str(f))
    pytest.skip(f"样本缺失：{keyword}")


# ---------------------------------------------------------------- 解析
def test_sections_detected():
    p = load("温室")
    assert len(p.sections) >= 5
    assert p.sections[0].number.startswith("3")


def test_no_images_in_samples():
    for kw in ("温室", "数据库"):
        p = load(kw)
        assert p.image_count == 0
        assert p.table_count == 0


# ---------------------------------------------------------------- 引用
def test_citation_zero_reference():
    """两篇都列了 12 条文献，正文一处未引。"""
    for kw in ("温室", "数据库"):
        issues = run_all(load(kw))
        cite = [i for i in issues if i.category == "引用"]
        assert cite, f"{kw}：应检出文献引用问题"
        assert cite[0].severity == "严重"


# ---------------------------------------------------------------- 图表
def test_floating_figure_detected():
    p = load("数据库")
    issues = run_all(p)
    fig = [i for i in issues if i.category == "图表" and "图" in i.message]
    assert fig, "应检出悬空图引用"


def test_table_section_without_table():
    """标题承诺「主要数据表结构」，但全文无表格。"""
    p = load("数据库")
    issues = run_all(p)
    hit = [i for i in issues if "表结构" in i.message]
    assert hit, "应检出「讲表结构却没有表」"


# ---------------------------------------------------------------- 结构
def test_summary_imbalance():
    """第一篇小结 1214 字，远超正文各节。"""
    p = load("温室")
    issues = run_all(p)
    hit = [i for i in issues if "小结" in i.message and i.severity == "严重"]
    assert hit, "应检出小结篇幅失衡"


def test_parent_section_with_children_not_flagged():
    """3.5 下面有 3.5.1，本身无正文，不应报「空章节」。"""
    p = load("数据库")
    issues = run_all(p)
    empty = [i for i in issues if "没有任何正文" in i.message and i.location == "3.5"]
    assert not empty


# ---------------------------------------------------------------- 排序
def test_severe_first():
    issues = run_all(load("数据库"))
    assert issues
    severities = [i.severity for i in issues]
    assert severities == sorted(severities, key=lambda x: 0 if x == "严重" else 1)


def test_summary_counts():
    s = summary(run_all(load("数据库")))
    assert s["total"] == s["severe"] + s["warning"]
    assert s["total"] > 0
