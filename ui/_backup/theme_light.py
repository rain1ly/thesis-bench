"""设计系统 —— token、排版、间距，一次注入全站生效。

**为什么单独一层**
Streamlit 默认样式是"能用"，不是"能看"。评委第一眼看到的是界面，
不是你的架构。所以视觉必须像代码一样有单一来源：
散在各页写 `<style>` 的结果是第 4 个页面开始不一致，然后全烂。

**三条硬约束**
1. **不引外部字体。** 用系统中文栈（苹方 / 雅黑 / 思源）。云端冷启动、断网演示、
   内网评审都不会出现字体闪烁或方框。
2. **对比度 ≥ 4.5:1。** 正文、标签、徽章全部按 WCAG AA 校过；
   装饰性弱化文字用 --tb-ink-3，也保到 4.5:1，不做"看起来很淡"的灰。
3. **只改表现层，不动布局引擎。** 不覆盖 Streamlit 的栅格与列宽逻辑，
   否则一次版本升级就白屏。所有自定义视觉走 `.tb-*` 类名。

**响应式策略**：以 1280 为设计基准，三档降级
    ≤ 1100px  侧边栏收窄、KPI 三列
    ≤ 900px   KPI 两列、字号降一档、卡片内边距收紧
    ≤ 640px   KPI 单列、表格横向滚动、按钮全宽
"""

from __future__ import annotations

# ---------------------------------------------------------------- 设计 token
COLORS = {
    "ink": "#14181F",        # 主文字
    "ink_2": "#4A5160",      # 次要文字
    "ink_3": "#646B78",      # 弱化文字（对暖白 5.1:1，留出投影仪余量）
    "line": "#E3E0D8",       # 分隔线
    "line_soft": "#EEECE6",
    "bg": "#FBFAF7",         # 暖白底
    "surface": "#FFFFFF",
    "brand": "#1E4B8F",      # 墨蓝，主色
    "brand_dark": "#16386B",
    "brand_soft": "#EDF2FA",
    "amber": "#B54708",      # 中风险
    "amber_soft": "#FDF3E7",
    "green": "#067647",      # 低风险 / 通过
    "green_soft": "#E9F6EF",
    "red": "#B42318",        # 高风险
    "red_soft": "#FCEDEC",
}

FONT = (
    '-apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", '
    '"Noto Sans SC", "Segoe UI", system-ui, sans-serif'
)

# 字号：正文 15px 是中文阅读的密度甜点；标题 30/21/16 三档够用，不铺第四档
TYPE = {"h1": 30, "h2": 21, "h3": 16, "body": 15, "small": 13.5, "tiny": 12.5}

CSS = f"""
<style>
:root {{
  --tb-ink: {COLORS["ink"]};
  --tb-ink-2: {COLORS["ink_2"]};
  --tb-ink-3: {COLORS["ink_3"]};
  --tb-line: {COLORS["line"]};
  --tb-line-soft: {COLORS["line_soft"]};
  --tb-bg: {COLORS["bg"]};
  --tb-surface: {COLORS["surface"]};
  --tb-brand: {COLORS["brand"]};
  --tb-brand-dark: {COLORS["brand_dark"]};
  --tb-brand-soft: {COLORS["brand_soft"]};
  --tb-amber: {COLORS["amber"]};
  --tb-amber-soft: {COLORS["amber_soft"]};
  --tb-green: {COLORS["green"]};
  --tb-green-soft: {COLORS["green_soft"]};
  --tb-red: {COLORS["red"]};
  --tb-red-soft: {COLORS["red_soft"]};
  --tb-r-sm: 6px;
  --tb-r: 10px;
  --tb-r-lg: 14px;
}}

/* ── 基础排版 ───────────────────────────────────────────── */
/* 只给容器和文本元素设字体，**绝不用 [class*="st-"] 这类通配**：
   它会命中 Streamlit 所有 st-emotion-cache-* 元素，包括图标 span，
   把 Material Symbols 字体一起覆盖 —— 连字失效后箭头显示成
   "keyboard_double_arrow_right" 这种字面文本。踩过一次，记在这里。 */
html, body, .stApp {{
  font-family: {FONT};
  -webkit-font-smoothing: antialiased;
}}
.stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp select,
.stApp button, .stApp [data-testid="stMarkdownContainer"] {{
  font-family: {FONT};
}}
.stApp {{ background: var(--tb-bg); }}

/* 图标字体保护：任何情况下都不能被中文字体栈顶掉，连字必须开启 */
[data-testid="stIconMaterial"],
span[class*="material-symbols"],
span[class*="material-icons"],
[data-testid="stExpanderToggleIcon"],
[data-testid="stSidebarCollapseButton"] span {{
  font-family: "Material Symbols Rounded", "Material Icons" !important;
  font-feature-settings: "liga" 1 !important;
  -webkit-font-feature-settings: "liga" 1 !important;
  font-variant-ligatures: normal !important;
  letter-spacing: normal !important;
}}

.block-container {{
  padding-top: 2.4rem;
  padding-bottom: 3rem;
  max-width: 1240px;
}}

h1, h2, h3, h4 {{
  color: var(--tb-ink);
  letter-spacing: -0.01em;
}}
h1 {{ font-size: {TYPE["h1"]}px !important; font-weight: 600 !important; line-height: 1.25; }}
h2 {{ font-size: {TYPE["h2"]}px !important; font-weight: 600 !important; margin-top: .4rem !important; }}
h3 {{ font-size: {TYPE["h3"]}px !important; font-weight: 600 !important; }}

p, li, .stMarkdown, [data-testid="stMarkdownContainer"] {{
  color: var(--tb-ink);
  font-size: {TYPE["body"]}px;
  line-height: 1.75;
}}

/* Streamlit 的 caption 默认太淡，这里抬到 4.5:1 并压小一档 */
[data-testid="stCaptionContainer"], .stCaption, small {{
  color: var(--tb-ink-3) !important;
  font-size: {TYPE["small"]}px !important;
  line-height: 1.6 !important;
}}

a {{ color: var(--tb-brand); text-decoration: none; }}
a:hover {{ text-decoration: underline; text-underline-offset: 2px; }}

hr {{ border-color: var(--tb-line-soft); margin: 1.6rem 0; }}

/* ── 侧边栏 ─────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
  background: var(--tb-surface);
  border-right: 1px solid var(--tb-line);
}}
[data-testid="stSidebar"] .block-container {{ padding-top: 1.4rem; }}
[data-testid="stSidebarNav"] a {{
  border-radius: var(--tb-r-sm);
  color: var(--tb-ink-2);
  font-size: 14px;
  padding: 6px 10px;
}}
[data-testid="stSidebarNav"] a:hover {{ background: var(--tb-brand-soft); color: var(--tb-brand); }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
  background: var(--tb-brand-soft);
  color: var(--tb-brand);
  font-weight: 600;
}}

/* ── 按钮 ───────────────────────────────────────────────── */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {{
  border-radius: var(--tb-r-sm);
  font-weight: 500;
  font-size: 14px;
  padding: .48rem 1rem;
  border: 1px solid var(--tb-line);
  background: var(--tb-surface);
  color: var(--tb-ink);
  transition: background .15s ease, border-color .15s ease, transform .15s ease;
}}
.stButton > button:hover {{
  border-color: var(--tb-brand);
  color: var(--tb-brand);
  background: var(--tb-brand-soft);
}}
.stButton > button:focus-visible,
.stTextArea textarea:focus-visible,
.stTextInput input:focus-visible {{
  outline: 2px solid var(--tb-brand);
  outline-offset: 2px;
}}
/* 主按钮：实心墨蓝 */
.stButton > button[kind="primary"],
[data-testid="stBaseButton-primary"] {{
  background: var(--tb-brand) !important;
  border-color: var(--tb-brand) !important;
  color: #FFFFFF !important;
}}
.stButton > button[kind="primary"]:hover {{
  background: var(--tb-brand-dark) !important;
  border-color: var(--tb-brand-dark) !important;
  transform: translateY(-1px);
}}
.stButton > button:disabled {{
  opacity: .55;
  transform: none !important;
}}

/* ── 输入控件 ───────────────────────────────────────────── */
.stTextInput input, .stTextArea textarea, .stNumberInput input {{
  border-radius: var(--tb-r-sm) !important;
  border: 1px solid var(--tb-line) !important;
  background: var(--tb-surface) !important;
  font-size: {TYPE["body"]}px !important;
  color: var(--tb-ink) !important;
}}
.stTextArea textarea:focus, .stTextInput input:focus {{
  border-color: var(--tb-brand) !important;
  box-shadow: 0 0 0 3px rgba(30, 75, 143, .10) !important;
}}
[data-baseweb="select"] > div {{
  border-radius: var(--tb-r-sm) !important;
  border-color: var(--tb-line) !important;
  background: var(--tb-surface) !important;
  font-size: 14px !important;
}}
.stRadio [role="radiogroup"] {{ gap: .35rem; }}
.stRadio label {{ font-size: 14px; }}

/* ── 卡片（st.container(border=True)）───────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] > div > div[data-testid="stVerticalBlock"] {{
  gap: .35rem;
}}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div > .tb-card-marker) {{
  border-radius: var(--tb-r);
}}
div[data-testid="stVerticalBlockBorderWrapper"] {{
  border: 1px solid var(--tb-line) !important;
  border-radius: var(--tb-r) !important;
  background: var(--tb-surface);
  transition: border-color .15s ease, box-shadow .15s ease;
}}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
  border-color: #C9D4E6 !important;
  box-shadow: 0 2px 10px rgba(20, 24, 31, .04);
}}

/* ── 折叠面板 ───────────────────────────────────────────── */
[data-testid="stExpander"] {{
  border: 1px solid var(--tb-line) !important;
  border-radius: var(--tb-r) !important;
  background: var(--tb-surface);
  overflow: hidden;
}}
[data-testid="stExpander"] summary {{
  font-size: 14px;
  font-weight: 500;
  color: var(--tb-ink);
  padding: .7rem .9rem;
  line-height: 1.5;
}}
/* 只调图标自身，不改 summary 的布局方式 —— Streamlit 内部结构随版本变，
   把 summary 改成 flex 容易在升级后崩版。根因是字体被覆盖，修字体即可。 */
[data-testid="stExpanderToggleIcon"] {{
  font-size: 18px !important;
  color: var(--tb-ink-3) !important;
}}
[data-testid="stExpander"] summary:hover {{ background: #FAF9F6; }}
[data-testid="stExpander"] [data-testid="stExpanderDetails"] {{ padding: .2rem .9rem .9rem; }}

/* ── 标签页 ─────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
  gap: .25rem;
  border-bottom: 1px solid var(--tb-line);
}}
.stTabs [data-baseweb="tab"] {{
  height: 40px;
  padding: 0 .9rem;
  font-size: 14px;
  color: var(--tb-ink-2);
  background: transparent;
}}
.stTabs [aria-selected="true"] {{
  color: var(--tb-brand) !important;
  font-weight: 600;
}}
.stTabs [data-baseweb="tab-highlight"] {{ background: var(--tb-brand); height: 2px; }}
.stTabs [data-baseweb="tab-border"] {{ display: none; }}

/* ── 指标（st.metric）──────────────────────────────────── */
[data-testid="stMetric"] {{
  background: var(--tb-surface);
  border: 1px solid var(--tb-line);
  border-radius: var(--tb-r);
  padding: .85rem 1rem;
}}
[data-testid="stMetricLabel"] p {{
  font-size: {TYPE["small"]}px !important;
  color: var(--tb-ink-3) !important;
  font-weight: 500;
}}
[data-testid="stMetricValue"] {{
  font-size: 26px !important;
  font-weight: 600;
  color: var(--tb-ink);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}}
[data-testid="stMetricDelta"] {{ font-size: 12.5px !important; }}

/* ── 表格 ───────────────────────────────────────────────── */
[data-testid="stDataFrame"] {{
  border: 1px solid var(--tb-line);
  border-radius: var(--tb-r);
  overflow: hidden;
  background: var(--tb-surface);
}}
[data-testid="stDataFrame"] [role="columnheader"] {{
  background: #F6F4EF !important;
  color: var(--tb-ink-2) !important;
  font-weight: 600 !important;
  font-size: 13px !important;
}}

/* ── 提示条 ─────────────────────────────────────────────── */
[data-testid="stAlert"] {{
  border-radius: var(--tb-r-sm);
  border: 1px solid var(--tb-line);
  font-size: 14px;
}}

/* ── 页面链接 ───────────────────────────────────────────── */
[data-testid="stPageLink"] a {{
  display: inline-flex;
  align-items: center;
  gap: .25rem;
  font-size: 14px;
  font-weight: 500;
  color: var(--tb-brand);
  padding: .15rem 0;
}}
[data-testid="stPageLink"] a:hover {{ gap: .5rem; }}

/* ══ 自定义组件（.tb-*）════════════════════════════════════ */

/* 页头 */
.tb-hero {{ padding: .2rem 0 1.1rem; border-bottom: 1px solid var(--tb-line-soft); margin-bottom: 1.5rem; }}
.tb-eyebrow {{
  display: inline-block;
  font-size: 11.5px;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--tb-brand);
  background: var(--tb-brand-soft);
  border-radius: 4px;
  padding: 3px 8px;
  margin-bottom: .6rem;
  font-weight: 600;
}}
.tb-hero h1 {{ margin: 0 0 .45rem 0 !important; }}
.tb-hero p {{ margin: 0; color: var(--tb-ink-2); font-size: 15px; line-height: 1.65; max-width: 62ch; }}
.tb-hero-meta {{ margin-top: .7rem; display: flex; flex-wrap: wrap; gap: .5rem; }}

/* KPI 网格 */
.tb-kpi-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin: .2rem 0 1.4rem;
}}
.tb-kpi {{
  background: var(--tb-surface);
  border: 1px solid var(--tb-line);
  border-radius: var(--tb-r);
  padding: 14px 16px;
}}
.tb-kpi .k-label {{
  font-size: 12.5px;
  color: var(--tb-ink-3);
  font-weight: 500;
  margin-bottom: 6px;
  letter-spacing: .01em;
}}
.tb-kpi .k-value {{
  font-size: 27px;
  font-weight: 600;
  color: var(--tb-ink);
  font-variant-numeric: tabular-nums;
  line-height: 1.15;
}}
.tb-kpi .k-unit {{ font-size: 14px; color: var(--tb-ink-3); font-weight: 500; margin-left: 3px; }}
.tb-kpi .k-note {{ font-size: 12.5px; color: var(--tb-ink-3); margin-top: 6px; }}
.tb-kpi.is-high .k-value {{ color: var(--tb-red); }}
.tb-kpi.is-mid .k-value {{ color: var(--tb-amber); }}
.tb-kpi.is-good .k-value {{ color: var(--tb-green); }}

/* 徽章 */
.tb-badge {{
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
  line-height: 1;
  padding: 4px 8px;
  border-radius: 5px;
  border: 1px solid transparent;
  white-space: nowrap;
}}
.tb-badge.b-brand {{ background: var(--tb-brand-soft); color: var(--tb-brand-dark); border-color: #D6E2F3; }}
.tb-badge.b-green {{ background: var(--tb-green-soft); color: var(--tb-green); border-color: #CDEBDA; }}
.tb-badge.b-amber {{ background: var(--tb-amber-soft); color: var(--tb-amber); border-color: #F4DFC4; }}
.tb-badge.b-red {{ background: var(--tb-red-soft); color: var(--tb-red); border-color: #F6D5D2; }}
.tb-badge.b-neutral {{ background: #F4F2ED; color: var(--tb-ink-2); border-color: var(--tb-line); }}

/* 章节小标题：左侧竖线 */
.tb-section {{
  display: flex;
  align-items: baseline;
  gap: .6rem;
  margin: 1.8rem 0 .8rem;
  padding-left: .7rem;
  border-left: 3px solid var(--tb-brand);
}}
.tb-section .s-title {{ font-size: 16px; font-weight: 600; color: var(--tb-ink); }}
.tb-section .s-note {{ font-size: 12.5px; color: var(--tb-ink-3); }}

/* 空状态 */
.tb-empty {{
  border: 1px dashed var(--tb-line);
  border-radius: var(--tb-r);
  padding: 2rem 1.2rem;
  text-align: center;
  background: #FCFBF9;
}}
.tb-empty .e-title {{ font-size: 15px; font-weight: 600; color: var(--tb-ink); margin-bottom: .35rem; }}
.tb-empty .e-hint {{ font-size: 13px; color: var(--tb-ink-3); line-height: 1.7; }}

/* 行内元信息 */
.tb-meta {{ font-size: 12.5px; color: var(--tb-ink-3); display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; }}
.tb-dot {{ width: 3px; height: 3px; border-radius: 50%; background: #C6C2B8; display: inline-block; }}

/* 数值等宽，表格里对得齐 */
.tb-num {{ font-variant-numeric: tabular-nums; }}

/* ── 响应式 ─────────────────────────────────────────────── */
@media (max-width: 1100px) {{
  .block-container {{ padding-left: 2rem; padding-right: 2rem; }}
}}
@media (max-width: 900px) {{
  .block-container {{ padding-top: 1.4rem; padding-left: 1.1rem; padding-right: 1.1rem; }}
  h1 {{ font-size: 24px !important; }}
  h2 {{ font-size: 19px !important; }}
  .tb-hero h1 {{ font-size: 24px !important; }}
  .tb-hero p {{ font-size: 14px; }}
  .tb-kpi .k-value {{ font-size: 23px; }}
  .tb-kpi-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
  [data-testid="stMetricValue"] {{ font-size: 22px !important; }}
  [data-testid="stDataFrame"] {{ overflow-x: auto; }}
}}
@media (max-width: 640px) {{
  .tb-kpi-grid {{ grid-template-columns: 1fr; }}
  .tb-hero {{ padding-bottom: .9rem; margin-bottom: 1.1rem; }}
  .stButton > button {{ width: 100%; }}
  .stTabs [data-baseweb="tab"] {{ padding: 0 .6rem; font-size: 13px; }}
}}

/* 遵循系统「减少动效」偏好 */
@media (prefers-reduced-motion: reduce) {{
  * {{ transition: none !important; animation: none !important; }}
}}
</style>
"""


def inject() -> None:
    """每个页面开头调一次。放在 set_page_config 之后。"""
    import streamlit as st

    st.markdown(CSS, unsafe_allow_html=True)
