"""规则检查：全部是确定性判断，不调用任何模型。

为什么先写这一层：
1. 不依赖 API，账号没开通也能跑
2. 结果可复现，同一份文档永远得出同一份清单
3. 覆盖了论文里最致命、也最容易被答辩挑出来的那几类硬伤

四类检查：
    check_citation_coverage  文献列了却没引用
    check_floating_refs      引用了图/表，但图/表不存在
    check_structure          空章节、过短章节、小结失衡
    check_title_promise      章节标题承诺的内容没交付
"""

from __future__ import annotations

import re

from core.schemas import DocProfile, Issue

REF_HEADS = ("参考文献", "参考资料", "文献目录")
REF_ITEM_RE = re.compile(r"^\[(\d+)\]")
REF_CITE_RE = re.compile(r"\[(\d+)\]")

FIG_RE = re.compile(r"图\s*(\d+[-–—.]\d+)")
TAB_RE = re.compile(r"表\s*(\d+[-–—.]\d+)")
FIG_CAP_RE = re.compile(r"^图\s*(\d+[-–—.]\d+)")
TAB_CAP_RE = re.compile(r"^表\s*(\d+[-–—.]\d+)")

MIN_SECTION_CHARS = 300
SUMMARY_RATIO = 1.2

TABLE_WORDS = ("表结构", "数据表", "表设计", "数据库表", "字段说明")


def _fmt_nums(numbers, prefix: str) -> str:
    return "、".join(
        f"{prefix} {n}"
        for n in sorted(numbers, key=lambda x: [int(p) for p in re.split(r"[-–—.]", x)])
    )


# ---------------------------------------------------------------- 1 文献引用
def check_citation_coverage(profile: DocProfile) -> list[Issue]:
    texts = profile.texts

    ref_start = None
    for i, t in enumerate(texts):
        plain = t.replace(" ", "").replace("　", "")
        if plain in REF_HEADS or (plain.startswith(REF_HEADS) and len(plain) < 12):
            ref_start = i
            break
    if ref_start is None:
        return []

    listed = set()
    for t in texts[ref_start:]:
        m = REF_ITEM_RE.match(t)
        if m:
            listed.add(int(m.group(1)))
    if not listed:
        return []

    body = "\n".join(texts[:ref_start])
    cited = {int(x) for x in REF_CITE_RE.findall(body)}

    missing = sorted(listed - cited)
    if not missing:
        return []

    if not cited:
        return [
            Issue(
                category="引用",
                severity="严重",
                location="全文",
                message=f"列出 {len(listed)} 条参考文献，正文中一处都没有引用",
                evidence="文献列表与正文完全脱节，答辩时会被直接问到「你引用的这些文献用在哪了」",
            )
        ]

    return [
        Issue(
            category="引用",
            severity="严重",
            location="参考文献",
            message=f"第 {'、'.join(str(n) for n in missing)} 条文献在正文中未被引用",
            evidence=f"共 {len(listed)} 条文献，正文引用了 {len(cited)} 条",
        )
    ]


# ---------------------------------------------------------------- 2 图表悬空
def check_floating_refs(profile: DocProfile) -> list[Issue]:
    issues: list[Issue] = []
    texts = profile.texts

    fig_caps, tab_caps = set(), set()
    for t in texts:
        m = FIG_CAP_RE.match(t)
        if m:
            fig_caps.add(m.group(1))
            continue
        m = TAB_CAP_RE.match(t)
        if m:
            tab_caps.add(m.group(1))

    body = "\n".join(
        t for t in texts if not (FIG_CAP_RE.match(t) or TAB_CAP_RE.match(t))
    )
    fig_mentions = set(FIG_RE.findall(body))
    tab_mentions = set(TAB_RE.findall(body))

    # 图
    if fig_mentions and profile.image_count == 0:
        issues.append(
            Issue(
                category="图表",
                severity="严重",
                location="正文",
                message=f"正文引用了图（{_fmt_nums(fig_mentions, '图')}），但全文一张图片都没有",
                evidence="图号附近应有对应插图；常见原因是粘贴时丢失，或图号是凭空写的",
            )
        )
    elif fig_mentions - fig_caps:
        miss = fig_mentions - fig_caps
        issues.append(
            Issue(
                category="图表",
                severity="严重",
                location="正文",
                message=f"提及 {_fmt_nums(miss, '图')}，但找不到对应的图注",
                evidence="图注应形如「图 3-1 ×××」，紧随图片下方",
            )
        )

    # 表
    if tab_mentions and profile.table_count == 0:
        issues.append(
            Issue(
                category="图表",
                severity="严重",
                location="正文",
                message=f"正文引用了表（{_fmt_nums(tab_mentions, '表')}），但全文一张表格都没有",
                evidence="表号附近应有对应表格",
            )
        )
    elif tab_mentions - tab_caps:
        miss = tab_mentions - tab_caps
        issues.append(
            Issue(
                category="图表",
                severity="严重",
                location="正文",
                message=f"提及 {_fmt_nums(miss, '表')}，但找不到对应的表注",
                evidence="表注应形如「表 3-1 ×××」，置于表格上方",
            )
        )

    return issues


# ---------------------------------------------------------------- 3 结构
def check_structure(profile: DocProfile) -> list[Issue]:
    issues: list[Issue] = []

    if not profile.sections:
        return [
            Issue(
                category="结构",
                severity="提示",
                location="全文",
                message="未能识别出章节标题，无法做结构检查",
                evidence="标题需形如「3.1 引言」，且独立成段",
            )
        ]

    for idx, s in enumerate(profile.sections):
        # 有子节的父节（如 3.5 下面直接是 3.5.1），正文为空是正常的
        has_child = (
            idx + 1 < len(profile.sections)
            and profile.sections[idx + 1].number.startswith(s.number + ".")
        )
        if s.char_count == 0:
            if has_child:
                continue
            issues.append(
                Issue(
                    category="结构",
                    severity="严重",
                    location=s.number,
                    message=f"「{s.title}」标题之下没有任何正文",
                    evidence="空章节通常是结构调整后遗留，答辩时会被问「这一节写了什么」",
                )
            )
        elif s.char_count < MIN_SECTION_CHARS and not s.is_summary and not has_child:
            issues.append(
                Issue(
                    category="结构",
                    severity="提示",
                    location=s.number,
                    message=f"「{s.title}」仅 {s.char_count} 字，篇幅偏短",
                    evidence=f"建议不少于 {MIN_SECTION_CHARS} 字，或与相邻小节合并",
                )
            )

    summaries = [s for s in profile.sections if s.is_summary]
    others = [s for s in profile.sections if not s.is_summary]
    if summaries and others:
        max_other = max(s.char_count for s in others)
        for s in summaries:
            if s.char_count > max_other * SUMMARY_RATIO:
                issues.append(
                    Issue(
                        category="结构",
                        severity="严重",
                        location=s.number,
                        message=f"「{s.title}」{s.char_count} 字，超过正文最长一节（{max_other} 字）",
                        evidence="小结篇幅超过正文，说明本章正文偏薄，或小结在重复前文",
                    )
                )

    return issues


# ---------------------------------------------------------------- 4 标题承诺
def check_title_promise(profile: DocProfile) -> list[Issue]:
    issues: list[Issue] = []
    if profile.table_count > 0:
        return issues

    for s in profile.sections:
        if any(k in s.title for k in TABLE_WORDS):
            issues.append(
                Issue(
                    category="图表",
                    severity="严重",
                    location=s.number,
                    message=f"「{s.title}」一节没有任何表格",
                    evidence="该节标题承诺给出表结构，但全文表格数为 0",
                )
            )
    return issues


# ---------------------------------------------------------------- 汇总
def run_all(profile: DocProfile) -> list[Issue]:
    """跑完所有规则，按「严重优先」排序返回。"""
    issues: list[Issue] = []
    issues += check_citation_coverage(profile)
    issues += check_floating_refs(profile)
    issues += check_structure(profile)
    issues += check_title_promise(profile)
    return sorted(issues, key=lambda x: x.sort_key())


def summary(issues: list[Issue]) -> dict[str, int]:
    return {
        "total": len(issues),
        "severe": sum(1 for i in issues if i.severity == "严重"),
        "warning": sum(1 for i in issues if i.severity == "提示"),
    }
