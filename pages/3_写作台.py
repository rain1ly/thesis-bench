"""写作台 —— ② 诊断层的入口。

上传论文，按结构与规范逐条检查。
当前版本只做规则检查（不调用模型），结果确定性可复现。
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.checker import run_all, summary
from core.parser import parse_docx
from ui import components, theme

st.set_page_config(page_title="写作台 · 论文工坊", layout="wide", page_icon="◧")
theme.inject()

components.hero(
    "② 写作台 · 规则诊断",
    "先按评委的标准挑一遍毛病",
    "四类确定性检查：文献双向引用、图表悬空、章节结构、标题承诺。同一份文档永远得到同一份清单，不调模型。",
)

uploaded = st.file_uploader("选择论文文件", type=["docx"], help="支持 .docx，样本见 data/samples/")

if uploaded is None:
    st.info("还没有上传文件。可以先用 `data/samples/` 里那两份样本试试，它们的问题足够典型。")
    st.stop()

uploaded.seek(0)
try:
    profile = parse_docx(uploaded)
except Exception as exc:  # noqa: BLE001
    st.error(f"解析失败：{type(exc).__name__} — {exc}")
    st.stop()

issues = run_all(profile)
stat = summary(issues)

components.kpi([
    ("字数", f"{profile.char_count:,}", "全文", "default"),
    ("章节", len(profile.sections), "识别到的小节", "default"),
    ("图片", profile.image_count, f"表格 {profile.table_count}", "default"),
    ("检出问题", stat["total"], f"{stat['severe']} 项严重", "high" if stat["severe"] else "good"),
])

st.divider()

if issues:
    st.subheader("问题清单")
    df = pd.DataFrame(
        [
            {
                "级别": i.severity,
                "类别": i.category,
                "位置": i.location,
                "问题": i.message,
                "说明": i.evidence,
            }
            for i in issues
        ]
    )
    st.dataframe(df, width="stretch", hide_index=True, height=min(420, 56 + 36 * len(df)))
else:
    st.success("没有发现结构性问题。")

if profile.sections:
    st.subheader("章节字数分布")
    chart_df = pd.DataFrame(
        {"字数": [s.char_count for s in profile.sections]},
        index=[f"{s.number} {s.title[:10]}" for s in profile.sections],
    )
    st.bar_chart(chart_df, height=300)

    with st.expander("章节明细"):
        detail = pd.DataFrame(
            [
                {
                    "编号": s.number,
                    "标题": s.title,
                    "字数": s.char_count,
                    "段落数": len(s.body),
                }
                for s in profile.sections
            ]
        )
        st.dataframe(detail, width="stretch", hide_index=True)

st.divider()
st.caption(f"文件：{profile.filename}　|　检查项：文献引用、图表悬空、章节结构、标题承诺")
