"""数据模型：文档画像、章节、问题条目。

这一层只有结构，没有逻辑。
解析在 parser.py，检查在 checker.py，界面在 app.py。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 严重程度排序用：数字越小越靠前
SEVERITY_WEIGHT = {"严重": 0, "提示": 1}


@dataclass
class Paragraph:
    """一个非空段落。"""

    index: int
    text: str
    style: str = ""


@dataclass
class Section:
    """一个章节（由「3.2 标题」这类段落切出来）。"""

    number: str
    title: str
    body: list[str] = field(default_factory=list)

    @property
    def char_count(self) -> int:
        return sum(len(t) for t in self.body)

    @property
    def is_summary(self) -> bool:
        return any(k in self.title for k in ("小结", "总结", "结语"))


@dataclass
class DocProfile:
    """一份文档的完整画像。"""

    filename: str
    paragraphs: list[Paragraph] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    image_count: int = 0
    table_count: int = 0

    @property
    def texts(self) -> list[str]:
        return [p.text for p in self.paragraphs]

    @property
    def char_count(self) -> int:
        return sum(len(t) for t in self.texts)


@dataclass
class Issue:
    """一条检查结果。"""

    category: str  # 引用 / 图表 / 结构
    severity: str  # 严重 / 提示
    location: str  # 章节号，或「全文」
    message: str
    evidence: str = ""

    def sort_key(self) -> tuple[int, str]:
        return (SEVERITY_WEIGHT.get(self.severity, 9), self.category)
