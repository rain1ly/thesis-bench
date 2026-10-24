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

from core.checker import check_citation_coverage, run_all, summary
from core.parser import parse_docx
from core.schemas import DocProfile, Paragraph

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


# ---------------------------------------------------------------- 引用双向核对
# 用合成文档而非真实样本：这两个方向要精确控制编号，样本里造不出来
def build(cites: str, ref_count: int):
    """最小文档：一句带引用的正文 + 参考文献表。"""
    paras = [Paragraph(index=0, text=cites), Paragraph(index=1, text="参考文献")]
    for i in range(1, ref_count + 1):
        paras.append(Paragraph(index=i + 1, text=f"[{i}] 某某. 相关研究[J]. 2024."))
    return DocProfile(filename="synthetic.docx", paragraphs=paras)


def test_dangling_citation_detected():
    """正文引用 [12]，但文献表只有 11 条 —— 反向缺口。"""
    issues = check_citation_coverage(build("已有研究[12]表明这一点。", 11))
    assert any("没有对应条目" in i.message for i in issues)


def test_dangling_citation_range():
    """[1-4] 要展开成 1,2,3,4，其中 4 号不存在。"""
    issues = check_citation_coverage(build("已有研究[1-4]表明。", 3))
    hit = [i for i in issues if "没有对应条目" in i.message]
    assert hit and "[4]" in hit[0].message
    assert "[1]" not in hit[0].message  # 1-3 是存在的，不该误报


def test_unused_references_detected():
    """文献表 5 条，正文只引用 1-3 —— 正向缺口。"""
    issues = check_citation_coverage(build("已有研究[1][2][3]表明。", 5))
    hit = [i for i in issues if "未被引用" in i.message]
    assert hit and "4" in hit[0].message and "5" in hit[0].message


def test_citation_clean_when_both_directions_ok():
    """区间引用 [1-3] 恰好覆盖 3 条文献，两个方向都没有缺口。"""
    assert check_citation_coverage(build("已有研究[1-3]表明。", 3)) == []


def test_math_interval_not_treated_as_citation():
    """「归一化到 [0,1] 区间」是数学记号，不能当成引用了第 0 条文献。"""
    issues = check_citation_coverage(build("各特征归一化到[0,1]区间后输入模型。", 3))
    assert not any("没有对应条目" in i.message for i in issues)


def test_zero_never_reported_as_dangling():
    """文献编号从 1 开始，[0] 不该出现在任何报告里。"""
    issues = check_citation_coverage(build("如文献[0]所述。", 3))
    assert not any("[0]" in i.message for i in issues)
