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

/* ── 布局：贴顶、全宽、跟随缩放 ─────────────────────────── */
/* 三条都是被用户当场指出来的：
   1) 顶栏上方有 32px 白边 —— stHeader 默认占位，压成 0；
   2) 内容被 max-width:1260px 关在中间，浏览器放大后两侧全是白边；
   3) 缩放后字号不变但可用宽度变小，排版直接崩 —— 所以边距用 clamp 跟随视口。 */
[data-testid="stHeader"] {
  height: 0 !important;
  min-height: 0 !important;
  background: transparent !important;
}
/* 光把 stHeader 压成 0 还不够：外层还有两道默认 padding，
   留着就是那 30 多像素白边（用户说的"没贴死浏览器上方"）。 */
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"] {
  padding-top: 0 !important;
  margin-top: 0 !important;
}
[data-testid="stMainBlockContainer"],
.block-container {
  padding: 0 0 2.5rem !important;
  max-width: 100% !important;
}
/* 内边距放在这一层，顶栏用负 margin 顶出去 —— 这样黑条贴边，正文仍有边距。
   注意选择器层级：stVerticalBlock 的**直接父级**就是 stMainBlockContainer，
   中间没有再套 div。之前按 `> div > div >` 写，整段没命中，
   于是 gap 一直是 15px，顶栏永远差那条缝。 */
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"],
[data-testid="stMainBlockContainer"] > div > div > [data-testid="stVerticalBlock"] {
  padding-left: clamp(12px, 1.9vw, 30px);
  padding-right: clamp(12px, 1.9vw, 30px);
  /* 1.66 的纵向排布用的是 flex gap，不是 margin ——
     gap 不清零的话，第一行会被推下 15px，顶栏就贴不住。 */
  gap: 0 !important;
}
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"]
  > [data-testid="stElementContainer"] {
  margin-bottom: 14px;
}
/* Streamlit 在正文最前面塞了一个高度为 0 的占位容器（logo 位）。
   它自己不可见，但上一行给的 margin-bottom 会变成实打实的 14px 空隙 ——
   顶栏就永远差那一条。所以首个子元素不给下边距。 */
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"]
  > [data-testid="stElementContainer"]:first-child,
[data-testid="stMainBlockContainer"] > div > div > [data-testid="stVerticalBlock"]
  > [data-testid="stElementContainer"]:first-child {
  margin-bottom: 0 !important;
}
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"]
  > [data-testid="stElementContainer"]:last-child,
[data-testid="stMainBlockContainer"] > div > div > [data-testid="stVerticalBlock"]
  > [data-testid="stElementContainer"]:last-child {
  margin-bottom: 0;
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
/* 去掉"这是一个 Streamlit 应用"的破绽：右上角 Deploy 按钮、Running 状态、⋮ 菜单。
   评委不会因此加分，但看到 Deploy 会立刻意识到这是现成框架搭的。
   只隐藏工具栏内容，不动 stHeader 的高度 —— 折叠侧边栏的按钮挂在它下面。 */
[data-testid="stToolbar"] { display: none !important; }
[data-testid="stStatusWidget"] { display: none !important; }
/* 元素悬停时右上角浮出的"下载/全屏"工具栏 —— 鼠标扫过会闪，录屏时尤其刺眼 */
[data-testid="stElementToolbar"] { display: none !important; }
/* 侧边栏折叠按钮是 fixed 定位，钉在窗口左上角。顶栏贴顶之后它正好压在黑条上，
   露出一个 "»" 符号。演示时不需要折叠侧边栏，直接隐藏。 */
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapsedControl"] { display: none !important; }
[data-testid="stHeader"] { background: transparent !important; }

/* 首页专用：让主卡吃掉剩余视口高度。
   否则内容只有 ~640px，900px 屏幕下面空 260px，看上去像没做完。
   用 :has(.cv) 把规则限定在首页，不影响其它页面。 */
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"]:has(.cv) {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"]:has(.cv)
  > [data-testid="stElementContainer"]:has(.cv) {
  flex: 1 1 auto;
}
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"]:has(.cv)
  > [data-testid="stElementContainer"]:has(.cv) .cv {
  height: 100%;
}

/* 入口文件必须叫 app.py（云端 Main file path 写死了这个路径），
   Streamlit 直接拿文件名当导航标题，于是侧边栏第一项显示成 "app"。
   不想为此重构入口，用伪元素覆盖文案：隐藏原来的 <p>，再用 ::before 写中文。 */
[data-testid="stSidebarNav"] a[href$="/"] p { display: none; }
[data-testid="stSidebarNav"] a[href$="/"]::before {
  content: "首页";
  font-size: 13px;
  font-weight: inherit;
  letter-spacing: inherit;
}

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
/* 按钮文字必须继承按钮颜色。
   踩过的坑：上面有一条全局 `p { color: var(--tb-ink) }`，
   而 Streamlit 1.66 把按钮文字包在 <div><p> 里 —— 于是主按钮变成"黑底黑字"，
   整颗按钮看上去是个纯黑方块。
   注意只把 `p` 设成 inherit 不够：那层 <div> 也被染黑了，`p` 继承它还是黑的。
   所以用 `*` 把整条链都拉回按钮自身的颜色。 */
.stButton button *, .stDownloadButton button *,
[data-testid="stBaseButton-primary"] *,
[data-testid="stBaseButton-secondary"] *,
[data-testid="stBaseButton-primaryFormSubmit"] *,
[data-testid="stFormSubmitButton"] button * {
  color: inherit !important;
  font-size: 12px !important;
  font-weight: 700 !important;
  letter-spacing: 0.08em !important;
  line-height: 1.4 !important;
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
/* 下拉框外框：用 :has(> input) 找"包裹输入框的那层"，比记层级稳。
   （1.66 移除了 data-baseweb，原来那条 [data-baseweb="select"] 是死的。）
   圆角已经在 config.toml 的 baseRadius 里统一设成 0，这里只补边框和底色。 */
[data-testid="stSelectbox"] div:has(> input),
[data-testid="stMultiSelect"] div:has(> input) {
  border-radius: 0 !important;
  border-color: var(--tb-line) !important;
  background: var(--tb-surface) !important;
}
[data-testid="stSelectbox"] input,
[data-testid="stMultiSelect"] input {
  font-size: 12.5px !important;
  color: var(--tb-ink) !important;
}
[data-testid="stRadio"] [role="radiogroup"] { gap: .3rem; }
[data-testid="stRadio"] label { font-size: 12.5px; }

/* ── 卡片（st.container(border=True)）───────────────────── */
/* 踩过的坑，写在这里免得再犯：
   Streamlit 1.66 里 `stVerticalBlockBorderWrapper` 这个 testid **已经不存在**
   （在包的 304 个 js 文件里搜，命中 0 次）。选择器写了不会报错，只是静默失效 ——
   于是外层容器全站保持默认的圆角灰边，看上去"只多了几条线"。
   改用 `key=` + `.st-key-<key>` 类名：这是官方支持的稳定入口，不依赖内部 DOM。
   命名约定：所有需要卡片外观的容器，key 以 `tb-` 开头。 */
div[data-testid="stVerticalBlockBorderWrapper"],
[class*="st-key-tb-"] {
  border: 2px solid var(--tb-ink) !important;
  border-radius: 0 !important;
  background: var(--tb-surface) !important;
  padding: 14px 16px !important;
}
/* 卡片内部收紧间距：原生控件的默认 gap 会把卡片撑得松散 */
[class*="st-key-tb-"] > div > div[data-testid="stVerticalBlock"] { gap: .45rem; }
/* 状态左条：靠 key 前缀区分，比在界面上加一行说明更快被看见 */
[class*="st-key-tb-priv-"] { border-left: 5px solid var(--tb-red) !important; }
[class*="st-key-tb-pub-"]  { border-left: 5px solid var(--tb-line) !important; }
/* 嵌套卡片（老师端待办里还会再套一层）不要双重描边 */
[class*="st-key-tb-"] [class*="st-key-tb-"] {
  border-width: 1px !important;
  padding: 10px 12px !important;
}

/* ── 折叠面板 ───────────────────────────────────────────── */
[data-testid="stExpander"] {
  border: 1px solid var(--tb-line) !important;
  border-radius: 0 !important;
  background: var(--tb-surface);
}
/* 带 key 的折叠面板（老师端待办等）：统一黑框 + 状态左条。
   左条颜色由 key 前缀决定，见上面 tb-priv / tb-pub 那段注释。 */
[class*="st-key-tbx-"] {
  border: 2px solid var(--tb-ink) !important;
  border-radius: 0 !important;
  background: var(--tb-surface) !important;
  overflow: hidden;
}
[class*="st-key-tbx-priv-"] { border-left: 5px solid var(--tb-red) !important; }
[class*="st-key-tbx-pub-"]  { border-left: 5px solid var(--tb-line) !important; }
/* 预演台题单：未预演的需要显眼，已答过的退后 */
[class*="st-key-tbx-todo-"] { border-left: 5px solid var(--tb-ink) !important; }
[class*="st-key-tbx-done-"] { border-left: 5px solid var(--tb-line) !important; }
/* 学生的「我的问题」：还在等答复的用黑条，已入库的退后 */
[class*="st-key-tbx-wait-"] { border-left: 5px solid var(--tb-ink) !important; }
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
/* 已经踩了两次的地方，记清楚：
   1) `data-baseweb` 在 1.66 被彻底移除（304 个 js 文件里搜，命中 0）。
   2) 标签**不是 button**，是 `<div data-testid="stTab" aria-selected>`。
      写成 button[role="tab"] 一条都不命中 —— 页面上三个标签会挤成一串没有分隔的文字。
   现在用 `[data-testid="stTab"]` + aria-selected，这两者在任何版本都稳定。 */
[data-testid="stTabs"] [role="tablist"] {
  gap: 0;
  border-bottom: 2px solid var(--tb-ink);
}
[data-testid="stTab"] {
  height: 38px;
  padding: 0 1rem;
  display: flex;
  align-items: center;
  font-size: 12.5px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--tb-ink-3);
  background: transparent;
  border-radius: 0;
  cursor: pointer;
}
[data-testid="stTab"]:hover { color: var(--tb-ink); }
[data-testid="stTab"][aria-selected="true"] {
  color: var(--tb-ink) !important;
  /* 下划线而不是背景块：背景块会把"标签页"变成"按钮" */
  box-shadow: inset 0 -3px 0 0 var(--tb-red);
}

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
/* Streamlit 的 info/warning/success 自带浅蓝/浅黄/浅绿底，
   放在纸底上像贴上去的贴纸。统一成白底，语义只由左粗条表达 ——
   这也符合整套设计"颜色只用来标状态，不用来装饰"的规则。 */
[data-testid="stAlert"],
[data-testid="stAlertContainer"] {
  border-radius: 0;
  border: 1px solid var(--tb-line);
  border-left: 4px solid var(--tb-ink);
  /* 底色挂在 stAlertContainer 上，只在 stAlert 上设没用 —— 蓝底会透出来 */
  background: var(--tb-surface) !important;
  font-size: 12.5px;
  padding: .7rem .9rem;
}
[data-testid="stAlert"] p,
[data-testid="stAlert"] div,
[data-testid="stAlert"] span {
  color: var(--tb-ink) !important;
  font-size: 12.5px !important;
  line-height: 1.65 !important;
}
[data-testid="stAlertContentWarning"] ~ * { border-left-color: var(--tb-amber); }
[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) { border-left-color: var(--tb-amber); }
[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) { border-left-color: var(--tb-red); }
[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) { border-left-color: var(--tb-green); }

/* ── 上传框 ─────────────────────────────────────────────── */
/* 默认是灰色虚线块，在一张纸底页面上格外突兀。改成白底细虚线 + 直角。 */
[data-testid="stFileUploader"] section[data-testid="stFileUploaderDropzone"],
[data-testid="stFileUploaderDropzone"] {
  background: var(--tb-surface) !important;
  border: 1px dashed var(--tb-line) !important;
  border-radius: 0 !important;
}
[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--tb-ink) !important; }

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

/* 顶栏：黑条贴死页面边缘（负 margin 抵消正文边距），高度固定 40px */
.tb-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--tb-ink);
  height: 40px;
  padding: 0 clamp(12px, 1.9vw, 30px);
  /* 左右负 margin 抵消正文边距，让黑条通到窗口边缘；
     纵向间距交给父级统一控制，这里不再自加 margin-bottom（会与父级叠加） */
  margin: 0 calc(-1 * clamp(12px, 1.9vw, 30px));
}
.tb-topbar .left { display: flex; align-items: center; gap: 11px; }
.tb-topbar .brand { font-size: 8px; letter-spacing: 0.26em; color: #F2F1EC; font-family: __MONO__; }
.tb-topbar .sep { width: 1px; height: 8px; background: #3A3A3A; }
.tb-topbar .dim { font-size: 8px; letter-spacing: 0.26em; color: #6E6E6E; font-family: __MONO__; }
.tb-topbar .faint { font-size: 8px; letter-spacing: 0.26em; color: #4E4E4E; font-family: __MONO__; }

/* ── 身份方框：真控件（popover），浮在顶栏右端 ─────────────── */
/* 为什么不用纯 HTML：那个 ↗ 看着能点，点了却什么都不发生，等于假按钮。
   改成 st.popover 之后点开就是身份切换器。
   定位用 fixed 而不是负 margin —— 负 margin 只是"看起来在上面"，
   元素仍占文档流，一旦 popover 内部有高度就会把顶栏文字顶下去，
   出现"黑条空着、文字跑到条下面"的错位。 */
[class*="st-key-identity_pop"] {
  position: fixed !important;
  top: 7px !important;
  right: clamp(12px, 1.9vw, 30px) !important;
  width: auto !important;
  height: auto !important;
  z-index: 1000000 !important;
}
[class*="st-key-identity_pop"] [data-testid="stPopover"] { display: inline-block; }
[class*="st-key-identity_pop"] button {
  height: 26px !important;
  min-height: 26px !important;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  border: 1px solid rgba(255, 255, 255, 0.26) !important;
  border-radius: 4px !important;
  background: rgba(255, 255, 255, 0.10) !important;
  padding: 0 11px !important;
  margin: 0 !important;
}
[class*="st-key-identity_pop"] button:hover {
  border-color: rgba(255, 255, 255, 0.5) !important;
  background: rgba(255, 255, 255, 0.18) !important;
}
/* 只改文字所在的 <p>，**不要用 span 通配** ——
   popover 按钮里还有一个承载图标的 <span data-testid="stIconMaterial">，
   字体一被换成等宽，Material Symbols 的连字失效，界面上会露出
   `keyboard_double_arrow_right` 这种图标名字面量。这个坑犯过两次了。 */
[class*="st-key-identity_pop"] button p {
  color: #C4C4C4 !important;
  font-size: 9px !important;
  letter-spacing: 0.26em !important;
  font-family: __MONO__ !important;
  line-height: 1 !important;
  margin: 0 !important;
}
/* 图标必须留在图标字体里，并显式开连字 */
[class*="st-key-identity_pop"] [data-testid="stIconMaterial"] {
  font-family: "Material Symbols Rounded", "Material Icons" !important;
  font-feature-settings: "liga" 1 !important;
  -webkit-font-feature-settings: "liga" 1 !important;
  font-size: 14px !important;
  color: #7FB6C4 !important;
  letter-spacing: normal !important;
}
/* 弹层本身也要跟着这套语言：默认是白底大圆角 + 柔和阴影，
   在这张黑白纸感的页面上像个贴上去的便签。改成直角 + 2px 黑框 + 硬阴影。 */
[data-testid="stPopoverBody"] {
  border-radius: 0 !important;
  border: 2px solid var(--tb-ink) !important;
  background: var(--tb-surface) !important;
  box-shadow: 5px 5px 0 rgba(17, 17, 17, 0.14) !important;
}
/* 箭头交给 popover 自带的 chevron：它表示"点开"，比 ↗（表示"跳走"）更准确。
   之前自己画过一个伪元素箭头，结果和 chevron 并排出现两个箭头。 */

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
