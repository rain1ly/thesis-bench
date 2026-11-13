"""设计系统 —— token、排版、间距，一次注入全站生效。

**这一版：纸底 + 黑框 + 一个信号红**

三条来源，各管一段，不平均用力：
1. **瑞士版式**管结构 —— 严格四栏、竖线分区、字号两极（42px / 6.5px，中间几乎不设档）、
   全部左对齐、禁止居中。
2. **纸感材质**管表面 —— 底色 #F2F1EC（暖纸），卡片纯白，2px 黑框，右上切角。
   层次靠"纸 vs 卡"的色差，不靠阴影。
3. **宽字距 + 等宽**管细节 —— 英文与数字 0.2–0.3em，中文 0.02–0.04em。

**三条硬约束（都是踩过的坑）**
1. **不引外部字体。** 中文用系统栈，数字用系统等宽。断网演示、内网评审、
   投影仪都不会出现字体闪烁或方框。
2. **对比度 ≥ 4.5:1。** 纸底比纯白更容易"看起来够深其实不够"，
   三级文字全部按 WCAG AA 校过，测试里逐个断言（实测 16.7 / 9.9 / 4.7）。
3. **只改表现层，不动布局引擎。** 不覆盖 Streamlit 的栅格与列宽逻辑，
   否则一次版本升级就白屏。所有自定义视觉走 `.tb-*` 类名。

**三个必须遵守的排版规则（写在这里，因为写错就是一眼假）**
- 中文 `letter-spacing` 不超过 0.04em。短标签（≤8 字）可到 0.2em，
  但长句拉宽会断句散架。宽字距只对英文和数字成立。
- 切角吃版面：右上角的内容，右边界必须退到 `父宽 − 切角 − 8px` 之外。
- 父元素有 border 时，绝对定位的装饰线要补偿 border 宽度，
  否则和 clip-path 的切边错位。
"""

from __future__ import annotations

# ---------------------------------------------------------------- 设计 token
COLORS = {
    "ink": "#111111",        # 主文字 / 主色
    "ink_2": "#3D3D3D",      # 次要文字
    "ink_3": "#6B6B6B",      # 弱化文字（对纸底 4.7:1，压线但不越界）
    "line": "#D9D7D0",       # 分隔线
    "line_soft": "#E4E2DB",  # 更淡的分隔
    "bg": "#F2F1EC",         # 暖纸底
    "surface": "#FFFFFF",    # 卡片
    "brand": "#111111",      # 主色（黑）
    "brand_on": "#FFFFFF",   # 压在主色上的文字
    "red": "#E30613",        # 信号红，只给编号和异常数字
    "yellow": "#F5E027",     # 荧光黄，全站只允许出现在一个高亮块
    "amber": "#8A5A00",      # 中风险
    "green": "#1F6B3A",      # 低风险 / 通过
    "mono_ink": "#111111",
}

FONT = (
    '-apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", '
    '"Noto Sans SC", "Segoe UI", system-ui, sans-serif'
)
MONO = 'ui-monospace, "Cascadia Mono", Consolas, "SF Mono", Menlo, monospace'

# 字号：两级极端是这套的骨架。中间只留 14 / 9.5 两个过渡档。
TYPE = {
    "display": 42,
    "h1": 26,
    "h2": 18,
    "h3": 14,
    "body": 13.5,
    "small": 11,
    "micro": 9.5,
    "label": 7,
}

# 切角尺寸：主卡 30，小卡 14。右上角内容要退到 切角+8 之外。
CUT_LG = 30
CUT_SM = 14

CSS_TEMPLATE = """
<style>
:root {
  --tb-ink: __INK__;
  --tb-ink-2: __INK_2__;
  --tb-ink-3: __INK_3__;
  --tb-line: __LINE__;
  --tb-line-soft: __LINE_SOFT__;
  --tb-bg: __BG__;
  --tb-surface: __SURFACE__;
  --tb-brand: __BRAND__;
  --tb-brand-on: __BRAND_ON__;
  --tb-red: __RED__;
  --tb-yellow: __YELLOW__;
  --tb-amber: __AMBER__;
  --tb-green: __GREEN__;
  --tb-cut-lg: 30px;
  --tb-cut-sm: 14px;
}

/* ── 基础排版 ───────────────────────────────────────────── */
/* 只给容器和文本元素设字体，**绝不用 [class*="st-"] 这类通配**：
   它会命中 Streamlit 所有 st-emotion-cache-* 元素，包括图标 span，
   把 Material Symbols 字体一起覆盖 —— 连字失效后箭头显示成
   "keyboard_double_arrow_right" 这种字面文本。踩过一次，记在这里。 */
html, body, .stApp {
  font-family: __FONT__;
  -webkit-font-smoothing: antialiased;
}
.stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp select,
.stApp button, .stApp [data-testid="stMarkdownContainer"] {
  font-family: __FONT__;
}
.stApp { background: var(--tb-bg); }

/* 图标字体保护：任何情况下都不能被中文字体栈顶掉，连字必须开启 */
[data-testid="stIconMaterial"],
span[class*="material-symbols"],
span[class*="material-icons"],
[data-testid="stExpanderToggleIcon"],
[data-testid="stSidebarCollapseButton"] span {
  font-family: "Material Symbols Rounded", "Material Icons" !important;
  font-feature-settings: "liga" 1 !important;
  -webkit-font-feature-settings: "liga" 1 !important;
  font-variant-ligatures: normal !important;
  letter-spacing: normal !important;
}

.block-container {
  padding-top: 1.6rem;
  padding-bottom: 3rem;
  max-width: 1260px;
}

h1, h2, h3, h4 { color: var(--tb-ink); }
h1 { font-size: __H1__px !important; font-weight: 900 !important; letter-spacing: -0.02em; line-height: 1.05; }
h2 { font-size: __H2__px !important; font-weight: 900 !important; letter-spacing: -0.01em; }
h3 { font-size: __H3__px !important; font-weight: 900 !important; letter-spacing: 0.02em; }

p, li, .stMarkdown, [data-testid="stMarkdownContainer"] {
  color: var(--tb-ink);
  font-size: __BODY__px;
  line-height: 1.7;
}

[data-testid="stCaptionContainer"], .stCaption, small {
  color: var(--tb-ink-3) !important;
  font-size: __SMALL__px !important;
  line-height: 1.6 !important;
}

a { color: var(--tb-ink); text-decoration: none; border-bottom: 1px solid var(--tb-line); }
a:hover { border-bottom-color: var(--tb-ink); }

hr { border-color: var(--tb-line); margin: 1.4rem 0; }

/* ── 侧边栏 ─────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: var(--tb-surface);
  border-right: 1px solid var(--tb-line);
}
[data-testid="stSidebar"] .block-container { padding-top: 1.2rem; }
[data-testid="stSidebarNav"] a {
  border-radius: 0;
  color: var(--tb-ink-2);
  font-size: 13px;
  padding: 7px 10px;
  border-left: 2px solid transparent;
}
[data-testid="stSidebarNav"] a:hover { background: #F7F6F1; color: var(--tb-ink); }
[data-testid="stSidebarNav"] a[aria-current="page"] {
  background: #F7F6F1;
  color: var(--tb-ink);
  font-weight: 900;
  border-left-color: var(--tb-red);
}

/* ── 按钮 ───────────────────────────────────────────────── */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {
  border-radius: 0;
  font-weight: 700;
  font-size: 12px;
  letter-spacing: 0.08em;
  padding: .5rem 1.1rem;
  border: 1.5px solid var(--tb-ink);
  background: var(--tb-surface);
  color: var(--tb-ink);
  transition: background .12s ease, color .12s ease;
}
.stButton > button:hover {
  background: var(--tb-ink);
  color: var(--tb-brand-on);
}
.stButton > button:focus-visible,
.stTextArea textarea:focus-visible,
.stTextInput input:focus-visible {
  outline: 2px solid var(--tb-red);
  outline-offset: 2px;
}
.stButton > button[kind="primary"],
[data-testid="stBaseButton-primary"] {
  background: var(--tb-ink) !important;
  border-color: var(--tb-ink) !important;
  color: var(--tb-brand-on) !important;
}
.stButton > button[kind="primary"]:hover {
  background: var(--tb-red) !important;
  border-color: var(--tb-red) !important;
}
.stButton > button:disabled { opacity: .4; }

/* ── 输入控件 ───────────────────────────────────────────── */
.stTextInput input, .stTextArea textarea, .stNumberInput input {
  border-radius: 0 !important;
  border: 1px solid var(--tb-line) !important;
  background: var(--tb-surface) !important;
  font-size: __BODY__px !important;
  color: var(--tb-ink) !important;
}
.stTextArea textarea:focus, .stTextInput input:focus {
  border-color: var(--tb-ink) !important;
  box-shadow: none !important;
}
[data-baseweb="select"] > div {
  border-radius: 0 !important;
  border-color: var(--tb-line) !important;
  background: var(--tb-surface) !important;
  font-size: 12.5px !important;
}
.stRadio [role="radiogroup"] { gap: .3rem; }
.stRadio label { font-size: 12.5px; }

/* ── 卡片（st.container(border=True)）───────────────────── */
div[data-testid="stVerticalBlockBorderWrapper"] {
  border: 1.5px solid var(--tb-ink) !important;
  border-radius: 0 !important;
  background: var(--tb-surface);
  padding: 4px;
}
[data-testid="stVerticalBlockBorderWrapper"] > div > div[data-testid="stVerticalBlock"] {
  gap: .3rem;
}

/* ── 折叠面板 ───────────────────────────────────────────── */
[data-testid="stExpander"] {
  border: 1px solid var(--tb-line) !important;
  border-radius: 0 !important;
  background: var(--tb-surface);
}
[data-testid="stExpander"] summary {
  font-size: 12.5px;
  font-weight: 700;
  color: var(--tb-ink);
  padding: .7rem .9rem;
  line-height: 1.5;
}
[data-testid="stExpanderToggleIcon"] {
  font-size: 17px !important;
  color: var(--tb-ink-3) !important;
}
[data-testid="stExpander"] summary:hover { background: #F7F6F1; }
[data-testid="stExpander"] [data-testid="stExpanderDetails"] { padding: .2rem .9rem .9rem; }

/* ── 标签页 ─────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  gap: 0;
  border-bottom: 2px solid var(--tb-ink);
}
.stTabs [data-baseweb="tab"] {
  height: 38px;
  padding: 0 1rem;
  font-size: 12.5px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--tb-ink-3);
  background: transparent;
  border-radius: 0;
}
.stTabs [aria-selected="true"] { color: var(--tb-ink) !important; }
.stTabs [data-baseweb="tab-highlight"] { background: var(--tb-red); height: 2px; }
.stTabs [data-baseweb="tab-border"] { display: none; }

/* ── 指标（st.metric）──────────────────────────────────── */
[data-testid="stMetric"] {
  background: var(--tb-surface);
  border: 1px solid var(--tb-line);
  border-radius: 0;
  padding: .85rem 1rem;
}
[data-testid="stMetricLabel"] p {
  font-size: __SMALL__px !important;
  color: var(--tb-ink-3) !important;
  font-family: __MONO__;
  letter-spacing: 0.16em;
}
[data-testid="stMetricValue"] {
  font-size: 26px !important;
  font-weight: 900;
  color: var(--tb-ink);
  font-family: __MONO__;
  line-height: 1.15;
}
[data-testid="stMetricDelta"] { font-size: 11px !important; }

/* ── 表格 ───────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
  border: 1px solid var(--tb-line);
  border-radius: 0;
  overflow: hidden;
  background: var(--tb-surface);
}
[data-testid="stDataFrame"] [role="columnheader"] {
  background: #F2F1EC !important;
  color: var(--tb-ink-2) !important;
  font-weight: 700 !important;
  font-size: 11.5px !important;
  letter-spacing: 0.08em;
}

/* ── 提示条 ─────────────────────────────────────────────── */
[data-testid="stAlert"] {
  border-radius: 0;
  border: 1px solid var(--tb-line);
  font-size: 12.5px;
  border-left-width: 3px;
}

/* ── 页面链接 ───────────────────────────────────────────── */
[data-testid="stPageLink"] a {
  display: inline-flex;
  align-items: center;
  gap: .3rem;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--tb-ink);
  border-bottom: none;
}
[data-testid="stPageLink"] a:hover { color: var(--tb-red); }

/* ══ 自定义组件（.tb-*）════════════════════════════════════ */

/* 顶栏：黑条 + 两端信息 */
.tb-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--tb-ink);
  padding: 5px 14px;
  margin-bottom: 14px;
}
.tb-topbar .left { display: flex; align-items: center; gap: 11px; }
.tb-topbar .brand { font-size: 7px; letter-spacing: 0.26em; color: #F2F1EC; font-family: __MONO__; }
.tb-topbar .sep { width: 1px; height: 8px; background: #3A3A3A; }
.tb-topbar .dim { font-size: 7px; letter-spacing: 0.26em; color: #6E6E6E; font-family: __MONO__; }
.tb-topbar .faint { font-size: 7px; letter-spacing: 0.26em; color: #4E4E4E; font-family: __MONO__; }

/* 身份方框：可交互记号（亮描边 + 提亮底色 + 箭头） */
.tb-chip {
  display: inline-flex;
  align-items: center;
  gap: 14px;
  border: 1px solid rgba(255,255,255,0.26);
  border-radius: 4px;
  padding: 4px 11px;
  background: rgba(255,255,255,0.10);
  cursor: pointer;
}
.tb-chip .who { font-size: 8px; letter-spacing: 0.28em; color: #C4C4C4; }
.tb-chip .page { font-size: 8.5px; letter-spacing: 0.24em; color: #7FB6C4; font-family: __MONO__; }
.tb-chip .go { font-size: 9px; color: #7FB6C4; line-height: 1; }
.tb-chip:hover { border-color: rgba(255,255,255,0.45); background: rgba(255,255,255,0.16); }

/* 页头：小标签 + 超粗标题 + 2px 黑线 */
.tb-hero { margin-bottom: 18px; }
.tb-hero .eyebrow {
  font-size: 7px;
  letter-spacing: 0.3em;
  color: var(--tb-ink-3);
  font-family: __MONO__;
  margin-bottom: 8px;
}
.tb-hero h1 {
  font-size: __HERO__px !important;
  font-weight: 900 !important;
  letter-spacing: -0.025em !important;
  line-height: 1 !important;
  color: var(--tb-ink);
  margin: 0 0 10px 0 !important;
}
.tb-hero .lead {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.tb-hero .mark {
  background: var(--tb-yellow);
  color: var(--tb-ink);
  font-size: 17px;
  font-weight: 900;
  letter-spacing: 0.03em;
  padding: 1px 7px;
  line-height: 1.45;
}
.tb-hero .sub {
  font-size: 10.5px;
  color: var(--tb-ink-2);
  line-height: 1.7;
  max-width: 62ch;
}
.tb-hero .rule { height: 2px; background: var(--tb-ink); }
.tb-hero-meta { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }

/* 三段链条：01 → 02 → 03 */
.tb-chain {
  display: grid;
  grid-template-columns: 1fr 20px 1fr 20px 1fr;
  align-items: start;
  margin-top: 12px;
}
.tb-chain .node { padding: 0 8px; }
.tb-chain .node:first-child { padding-left: 0; }
.tb-chain .node:last-child { padding-right: 0; }
.tb-chain .arrow {
  display: flex;
  justify-content: center;
  padding-top: 22px;
  font-size: 11px;
  color: #C4C2BB;
  line-height: 1;
}
.tb-chain .no {
  font-size: 8.5px;
  letter-spacing: 0.2em;
  color: var(--tb-red);
  font-family: __MONO__;
}
.tb-chain .en {
  font-size: 6.5px;
  letter-spacing: 0.24em;
  color: var(--tb-ink-3);
  font-family: __MONO__;
}
.tb-chain .name {
  font-size: 14px;
  font-weight: 900;
  letter-spacing: 0.02em;
  color: var(--tb-ink);
  margin-top: 5px;
}
.tb-chain .nums {
  font-size: 7.5px;
  letter-spacing: 0.2em;
  color: var(--tb-ink-3);
  font-family: __MONO__;
  margin-top: 2px;
}
.tb-chain .desc {
  border-top: 1px solid var(--tb-line-soft);
  margin-top: 8px;
  padding-top: 6px;
  font-size: 9.5px;
  line-height: 1.7;
  color: var(--tb-ink-2);
}

/* KPI 网格：白卡 + 编号 + 等宽数字 */
.tb-kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(168px, 1fr));
  gap: 10px;
  margin: 2px 0 16px;
}
.tb-kpi {
  background: var(--tb-surface);
  border: 1.5px solid var(--tb-ink);
  padding: 13px 14px 11px;
  position: relative;
  clip-path: polygon(0 0, calc(100% - 14px) 0, 100% 14px, 100% 100%, 0 100%);
}
.tb-kpi .k-top { display: flex; justify-content: space-between; align-items: baseline; }
.tb-kpi .k-label {
  font-size: 8px;
  letter-spacing: 0.2em;
  color: var(--tb-ink-3);
  font-family: __MONO__;
}
.tb-kpi .k-no {
  font-size: 7.5px;
  letter-spacing: 0.2em;
  color: var(--tb-red);
  font-family: __MONO__;
}
.tb-kpi .k-value {
  font-size: 26px;
  font-weight: 900;
  color: var(--tb-ink);
  font-family: __MONO__;
  line-height: 1.15;
  margin-top: 6px;
}
.tb-kpi .k-unit {
  font-size: 9px;
  color: var(--tb-ink-3);
  font-family: __MONO__;
  margin-left: 3px;
}
.tb-kpi .k-note {
  font-size: 8px;
  letter-spacing: 0.16em;
  color: var(--tb-ink-3);
  font-family: __MONO__;
  margin-top: 6px;
}
.tb-kpi.is-high .k-value, .tb-kpi.is-high .k-note { color: var(--tb-red); }
.tb-kpi.is-mid .k-value, .tb-kpi.is-mid .k-note { color: var(--tb-amber); }
.tb-kpi.is-good .k-value, .tb-kpi.is-good .k-note { color: var(--tb-green); }

/* 徽章：方角 + 等宽小字，不用胶囊 */
.tb-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 9.5px;
  font-weight: 700;
  font-family: __MONO__;
  letter-spacing: 0.12em;
  line-height: 1;
  padding: 4px 7px;
  border-radius: 0;
  border: 1px solid var(--tb-line);
  background: #F7F6F1;
  color: var(--tb-ink-2);
  white-space: nowrap;
}
.tb-badge.b-brand { background: var(--tb-ink); color: var(--tb-brand-on); border-color: var(--tb-ink); }
.tb-badge.b-red { background: #FCEBEB; color: var(--tb-red); border-color: #F2C9C9; }
.tb-badge.b-amber { background: #FAEEDA; color: var(--tb-amber); border-color: #EBD6B4; }
.tb-badge.b-green { background: #EAF3DE; color: var(--tb-green); border-color: #CFE0BA; }

/* 章节标题：小标签 + 2px 黑线 */
.tb-section {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin: 22px 0 10px;
  padding-bottom: 6px;
  border-bottom: 2px solid var(--tb-ink);
}
.tb-section .s-title {
  font-size: 9px;
  letter-spacing: 0.24em;
  font-family: __MONO__;
  font-weight: 700;
  color: var(--tb-ink);
}
.tb-section .s-note {
  font-size: 8px;
  letter-spacing: 0.2em;
  font-family: __MONO__;
  color: var(--tb-ink-3);
}

/* 空状态 */
.tb-empty {
  border: 1px dashed var(--tb-line);
  padding: 2rem 1.2rem;
  text-align: center;
  background: #F7F6F1;
}
.tb-empty .e-title { font-size: 13px; font-weight: 900; color: var(--tb-ink); margin-bottom: .35rem; }
.tb-empty .e-hint { font-size: 11.5px; color: var(--tb-ink-3); line-height: 1.7; }

/* 行内元信息 */
.tb-meta {
  font-size: 10px;
  letter-spacing: 0.1em;
  color: var(--tb-ink-3);
  font-family: __MONO__;
  display: flex;
  flex-wrap: wrap;
  gap: .5rem;
  align-items: center;
}
.tb-dot { width: 3px; height: 3px; background: #C6C2B8; display: inline-block; }

/* 卡片标题行：编号 + 中文 + 英文 */
.tb-card-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  padding-bottom: 7px;
  border-bottom: 1px solid var(--tb-line-soft);
}
.tb-card-head .ch-left { display: flex; align-items: baseline; gap: 9px; }
.tb-card-head .ch-no {
  font-size: 8px;
  letter-spacing: 0.2em;
  color: var(--tb-red);
  font-family: __MONO__;
}
.tb-card-head .ch-name { font-size: 13.5px; font-weight: 900; color: var(--tb-ink); letter-spacing: 0.02em; }
.tb-card-head .ch-en {
  font-size: 6.5px;
  letter-spacing: 0.24em;
  color: var(--tb-ink-3);
  font-family: __MONO__;
}

/* 数值等宽 */
.tb-num { font-family: __MONO__; }

/* ── 响应式 ─────────────────────────────────────────────── */
@media (max-width: 1100px) {
  .block-container { padding-left: 1.6rem; padding-right: 1.6rem; }
}
@media (max-width: 940px) {
  .tb-chain { grid-template-columns: 1fr; gap: 10px; }
  .tb-chain .arrow { display: none; }
  .tb-chain .node { padding: 0; }
  .tb-hero h1 { font-size: 30px !important; }
  .tb-kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 640px) {
  .tb-kpi-grid { grid-template-columns: 1fr; }
  .tb-topbar { flex-direction: column; align-items: flex-start; gap: 8px; }
  .stButton > button { width: 100%; }
}

/* 遵循系统「减少动效」偏好 */
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; animation: none !important; }
}
</style>
"""


def _build_css() -> str:
    """token 注入。

    用 __KEY__ 占位再替换，而不是 f-string —— CSS 里全是花括号，
    f-string 要写成 {{ }}，几百行下来极易漏一个，且报错信息难读。
    """
    css = CSS_TEMPLATE
    for key, value in COLORS.items():
        css = css.replace(f"__{key.upper()}__", value)
    css = css.replace("__FONT__", FONT)
    css = css.replace("__MONO__", MONO)
    css = css.replace("__BODY__", str(TYPE["body"]))
    css = css.replace("__SMALL__", str(TYPE["small"]))
    css = css.replace("__H1__", str(TYPE["h1"]))
    css = css.replace("__H2__", str(TYPE["h2"]))
    css = css.replace("__H3__", str(TYPE["h3"]))
    css = css.replace("__HERO__", str(TYPE["display"]))
    return css


CSS = _build_css()


def inject() -> None:
    """每个页面开头调一次。放在 set_page_config 之后。"""
    import streamlit as st

    st.markdown(CSS, unsafe_allow_html=True)
