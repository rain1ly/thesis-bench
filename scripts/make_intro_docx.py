"""生成《作品介绍》Word 文档到桌面。

一次性工具，改内容改这里的 CONTENT 再跑。
排版按中文公文/参赛材料的习惯来：标题黑体、正文宋体五号、1.5 倍行距、首行缩进两字符，
图片位置留成带底纹的占位框，方便直接往里插图。

用法：
    .venv\\Scripts\\python.exe scripts\\make_intro_docx.py
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = Path.home() / "Desktop" / "作品介绍.docx"

HEI = "微软雅黑"
SONG = "宋体"
INK = RGBColor(0x1A, 0x1A, 0x1A)
GRAY = RGBColor(0x6B, 0x6B, 0x6B)


# ---------------------------------------------------------------- 基础排版
def cn_font(run, name: str = SONG) -> None:
    """中文字体必须显式设 eastAsia，只设 font.name 对汉字无效。"""
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)


def body(doc, text: str, indent: bool = True, bold_prefix: str = ""):
    p = doc.add_paragraph()
    fmt = p.paragraph_format
    fmt.line_spacing = 1.5
    fmt.space_after = Pt(4)
    if indent:
        fmt.first_line_indent = Cm(0.74)  # 相当于两个汉字
    if bold_prefix:
        r = p.add_run(bold_prefix)
        r.bold = True
        r.font.size = Pt(10.5)
        r.font.color.rgb = INK
        cn_font(r)
    r = p.add_run(text)
    r.font.size = Pt(10.5)
    r.font.color.rgb = INK
    cn_font(r)
    return p


def h1(doc, text: str):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(16)
    p.paragraph_format.space_after = Pt(8)
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(15)
    r.font.color.rgb = INK
    cn_font(r, HEI)
    # 章标题下加一条细横线，视觉上分隔
    pPr = p._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:color"), "1E4B8F")
    borders.append(bottom)
    pPr.append(borders)
    return p


def h2(doc, text: str):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(12)
    r.font.color.rgb = INK
    cn_font(r, HEI)
    return p


def bullet(doc, text: str, bold_prefix: str = ""):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.line_spacing = 1.4
    p.paragraph_format.space_after = Pt(3)
    if bold_prefix:
        r = p.add_run(bold_prefix)
        r.bold = True
        r.font.size = Pt(10.5)
        cn_font(r)
    r = p.add_run(text)
    r.font.size = Pt(10.5)
    cn_font(r)
    return p


def numbered(doc, text: str):
    p = doc.add_paragraph(style="List Number")
    p.paragraph_format.line_spacing = 1.4
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(text)
    r.font.size = Pt(10.5)
    cn_font(r)
    return p


def quote(doc, text: str):
    """引用块：浅灰底 + 左边框，用来放实测输出。"""
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.8)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.4
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), "F6F5F1")
    pPr.append(shd)
    r = p.add_run(text)
    r.font.size = Pt(10)
    r.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
    cn_font(r)
    return p


def table(doc, headers: list[str], rows: list[list[str]], widths: list[float] | None = None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = True

    hdr = t.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = ""
        p = hdr[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(9.5)
        r.font.color.rgb = INK
        cn_font(r, HEI)
        shd = OxmlElement("w:shd")
        shd.set(qn("w:fill"), "EDF2FA")
        hdr[i]._tc.get_or_add_tcPr().append(shd)

    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            p.paragraph_format.line_spacing = 1.25
            r = p.add_run(val)
            r.font.size = Pt(9)
            r.font.color.rgb = INK
            cn_font(r)

    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def img_slot(doc, label: str, desc: str, height_cm: float = 5.6):
    """图片占位框：浅底 + 细边框，中央提示文字。"""
    t = doc.add_table(rows=1, cols=1)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = t.cell(0, 0)

    trPr = t.rows[0]._tr.get_or_add_trPr()
    trH = OxmlElement("w:trHeight")
    trH.set(qn("w:val"), str(int(height_cm * 567)))
    trH.set(qn("w:hRule"), "atLeast")
    trPr.append(trH)

    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), "FAF9F5")
    cell._tc.get_or_add_tcPr().append(shd)

    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"［ 此处插入 {label} ］")
    r.font.size = Pt(10.5)
    r.bold = True
    r.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
    cn_font(r, HEI)

    p2 = cell.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = p2.add_run(desc)
    r2.font.size = Pt(9)
    r2.font.color.rgb = GRAY
    cn_font(r2)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def caption(doc, text: str):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(10)
    r = p.add_run(text)
    r.font.size = Pt(9)
    r.font.color.rgb = GRAY
    cn_font(r)


def footer_page_number(doc):
    footer = doc.sections[0].footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    for tag, attr, text in (
        ("w:fldChar", "begin", None),
        ("w:instrText", None, " PAGE "),
        ("w:fldChar", "end", None),
    ):
        el = OxmlElement(tag)
        if attr:
            el.set(qn("w:fldCharType"), attr)
        if text:
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._r.append(el)
    run.font.size = Pt(9)
    cn_font(run)


# ---------------------------------------------------------------- 文档
def build() -> None:
    doc = Document()

    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.top_margin = Cm(2.4)
    sec.bottom_margin = Cm(2.2)
    sec.left_margin = Cm(2.6)
    sec.right_margin = Cm(2.6)
    footer_page_number(doc)

    # 正文默认样式
    normal = doc.styles["Normal"]
    normal.font.name = SONG
    normal.font.size = Pt(10.5)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), SONG)

    # ── 封面区
    for _ in range(3):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("论文工坊 · ThesisBench")
    r.bold = True
    r.font.size = Pt(26)
    r.font.color.rgb = RGBColor(0x1E, 0x4B, 0x8F)
    cn_font(r, HEI)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("作 品 介 绍")
    r.font.size = Pt(16)
    r.font.color.rgb = INK
    cn_font(r, HEI)

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("学位论文导学协同系统")
    r.font.size = Pt(11)
    r.font.color.rgb = GRAY
    cn_font(r)

    for _ in range(6):
        doc.add_paragraph()

    for line in (
        "2026 第九届传智杯全国大学生数智创新与 AI 应用大赛",
        "AI 创新应用挑战赛（技术应用赛 · 个人赛 · B 组）",
        "",
        "2026 年 10 月",
    ):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(line)
        r.font.size = Pt(11)
        r.font.color.rgb = INK if line else GRAY
        cn_font(r)

    doc.add_page_break()

    # ── 一、项目详情与使用方式
    h1(doc, "一、项目详情与使用方式")

    h2(doc, "1.1 项目定位")
    body(
        doc,
        "维普类系统解决的是「论文提交之后的合规审查」——查重率、格式项、流程流转。"
        "本项目解决的是另一段时间的问题：「写作过程中的卡点在哪儿，以及答辩之前能不能站得住」。"
        "两者的输入数据、介入时点、输出结果都不重叠。",
    )
    table(
        doc,
        ["维度", "维普类合规系统", "论文工坊（本项目）"],
        [
            ["输入数据", "论文成品", "论文 + 学生的答疑史"],
            ["介入时点", "提交之后", "写作过程 + 答辩之前"],
            ["输出", "合规报告（查重率、格式项）", "诊断清单 + 答辩预演题单"],
            ["判断依据", "比对库 + 格式规范", "确定性规则 + 学生自己的困惑记录"],
        ],
        widths=[3.2, 5.6, 6.4],
    )
    body(doc, "本项目明确不做三件事：不查重、不代写、不管流程。")

    h2(doc, "1.2 三层架构")
    body(doc, "三个模块不是并列功能，而是一条链：上一层的产出是下一层的输入。")
    quote(
        doc,
        "① 答疑台（学生端 / 老师端）\n"
        "    学生提问 → AI 起草 → 导师审核 → 入库沉淀\n"
        "                    ↓\n"
        "② 写作台（诊断）\n"
        "    上传 docx → 四类规则检查 → 问题清单\n"
        "                    ↓\n"
        "③ 预演台\n"
        "    答疑史 → 主题风险画像 → 出题 → 作答 → 要点覆盖判分",
    )

    h2(doc, "1.3 三个模块说明")
    body(
        doc,
        "提问时先定三件事：问题分类（论文写作 / 数据分析 / 代码实现 / 系统使用 / 格式规范 / 其他）、"
        "交给哪位老师（我的导师 / 指定其他老师 / 公开给所有老师）、可见性（公开 / 隐私）。"
        "AI 起草答复草稿，导师审核修改后才入库。同一学生提出近似问题时，系统自动提示历史答复。",
        bold_prefix="① 答疑台 · 学生端　",
    )
    body(
        doc,
        "待办按「点名找我的 → 公开池」排序，隐私问题优先；「我的学生」显示每人论文题目、提问数、"
        "未答复数与风险等级；「沉淀库」按分类查看已通过的公开问答，并统计分类分布。",
        bold_prefix="① 答疑台 · 老师端　",
    )
    body(
        doc,
        "上传 .docx，执行四类确定性检查：文献双向引用、图表悬空、章节结构失衡、标题承诺未兑现，"
        "输出问题清单与章节字数分布。同一份文档永远得到同一份结果。",
        bold_prefix="② 写作台　",
    )
    body(
        doc,
        "按该学生的答疑记录计算主题风险分，生成答辩预演题单；学生作答后按要点覆盖给出反馈；"
        "可调用 AI 扮演评委追问；逐题轨迹记录「1/3 → 3/3」的改进过程。",
        bold_prefix="③ 预演台　",
    )

    h2(doc, "1.4 使用方式")
    table(
        doc,
        ["步骤", "操作"],
        [
            ["1", "访问在线地址（或本地运行 streamlit run app.py）"],
            ["2", "侧边栏选择身份：学生 / 老师"],
            ["3", "学生：填写论文题目与导师 → 提问 → 查看答复 → 打开预演台自测"],
            ["4", "老师：进入老师端 → 处理待办 → 查看名下学生 → 浏览沉淀库"],
            ["5", "上传论文到写作台，获得结构性问题清单"],
        ],
        widths=[2.0, 13.2],
    )
    body(
        doc,
        "首次打开会自动载入 30 条示例数据（虚构学生，页面明确标注来源），可直接体验完整流程；"
        "清空入口位于首页折叠区。",
    )

    img_slot(doc, "图 1", "首页总览：三层卡片、闭环徽章链、KPI 状态")
    caption(doc, "图 1　首页总览——十秒内说清「这是什么、三层各自走到哪」")

    # ── 二、亮点
    h1(doc, "二、项目亮点")

    highlights = [
        (
            "1. 用「答疑史」出题——别人拿不到的数据。",
            "通用题库谁都能做，但「这个学生在数据来源问题上问了 4 次、横跨开题到定稿三个阶段」"
            "只有沉淀了过程的系统才有。题单中每道题都可追溯到具体答疑记录编号，演示时可当场换学生重算。",
        ),
        (
            "2. 只报要点覆盖，不打分。",
            "主动放弃「百分制评分」这类看起来更唬人的功能。78 分是虚假的精确，学生只会为分数辩护；"
            "「你漏了『说清数据边界』」才是能照着改的东西。",
        ),
        (
            "3. AI 只起草，不裁决。",
            "AI 产出（答复草稿、评委追问）一律标记为待审核或仅供参考，导师点通过才入库。"
            "学术判断不交给模型，这一点在数据层与测试层双重约束。",
        ),
        (
            "4. 规则先于模型。",
            "四类文档检查、主题风险计算、出题、要点判分全部是确定性纯函数——不依赖密钥、结果可复现、"
            "出错可定位。评委当场换一个学生演示，无需等待模型响应。",
        ),
        (
            "5. 没有密钥也能完整演示。",
            "代码对密钥做了四态降级（未配置 / 占位符 / 无效 / 正常）。未配置时规则检查、出题、判分、"
            "老师端、界面全部正常，仅 AI 起草与 AI 追问两处降级。",
        ),
        (
            "6. 双身份与可见性边界。",
            "学生与导师绑定、论文题目随问题快照留存、公开与隐私分级。隐私问题永不进入公开池——"
            "包括「隐私但未指定老师」的异常数据，系统选择谁都看不见，而不是越界派发。",
        ),
        (
            "7. 工程质量可验证。",
            "85 条自动化测试，其中相当比例的断言针对设计承诺本身（如「导师答案必须盖过 AI 草稿」"
            "「跨阶段重复的风险必须高于同阶段重复」「清空之后不许自动回流」），而非函数返回值。",
        ),
    ]
    for prefix, text in highlights:
        body(doc, text, bold_prefix=prefix)

    img_slot(doc, "图 2", "老师端：待办列表 / 我的学生 / 沉淀库")
    caption(doc, "图 2　老师端——先看谁在等我，再看谁卡住了")

    # ── 三、AI 技术落地
    h1(doc, "三、AI 技术落地使用情况")

    body(
        doc,
        "本项目对 AI 的使用是收敛的、可审计的：全系统只有两处真正调用大模型，"
        "其余环节全部由确定性算法完成。",
    )

    h2(doc, "3.1 两处调用")
    table(
        doc,
        ["场景", "触发时机", "核心约束"],
        [
            [
                "答复起草",
                "学生提交问题后",
                "200 字以内；禁止空话；涉及研究设计、数据可得性、结论可靠性必须写明「这一点需要导师确认」；不代写正文",
            ],
            [
                "评委追问",
                "学生提交作答后手动触发",
                "仅针对空泛、前后不一致、未交代清楚处追问；输出 2 条且每条不超过 40 字；答得完整时只输出「暂无可追问」；不评价、不复述、不建议",
            ],
        ],
        widths=[2.6, 3.6, 9.0],
    )
    body(
        doc,
        "「暂无可追问」这个出口是刻意留的：不给出路，模型会为了凑满两条而硬编问题，"
        "那种追问学生一眼能识破，整个预演的可信度就没了。",
    )

    h2(doc, "3.2 实测结果")
    body(doc, "连通性：ping 返回「模型已回话」，密钥有效、余额正常。")
    body(doc, "答复起草实测（输入：陈同学 · 定稿 · 「结论部分怎么写得不像凑字数？」），输出 134 字：")
    quote(
        doc,
        "结论只回答引言提出的问题，逐条对应，不重复正文。写法：每条结论用「本文发现……」开头，"
        "后接证据（数据、案例编号），再写适用范围与限制。删掉「综上所述」「具有重要意义」等套话。"
        "若某条结论无数据支撑，删去或改为「待进一步验证」。结论是否成立、能否定稿，这一点需要导师确认。",
    )
    body(doc, "三条硬性约束均满足：可执行、无套话、带「需要导师确认」。")
    body(doc, "评委追问实测（学生答「数据来自公开数据集，但和我的传感器对不上，所以只保留了能对上的字段」）：")
    quote(
        doc,
        "1. 公开数据集具体是哪个名称、哪个版本，如何核查？\n"
        "2. 对不上的字段占多少比例，只保留能对上的字段会带来什么偏差？",
    )
    body(doc, "不评价、不复述、不建议，符合设计预期。")

    h2(doc, "3.3 工程保障")
    for item in (
        "密钥脱敏展示，不进日志、不进界面；",
        "异常分类为中文原因（401 / 402 / 404 / 429 / 超时），避免把「要换密钥」和「要充值」混成一句「调用失败」；",
        "更换模型供应商只改三行环境变量，业务代码零改动；",
        "「环境自检」页提供四态诊断与一键连通性测试。",
    ):
        bullet(doc, item)

    h2(doc, "3.4 AI 明确不做的三件事")
    numbered(doc, "不生成参考答案——答辩没有标准答案，模型一旦生成，学生就会背它。")
    numbered(doc, "不给论文打分——分数不可验证，会诱导学生为分数辩护而不是为内容改进。")
    numbered(doc, "不做语义判定的最终结论——规则能判的（引用对不对、章节平不平衡、要点提没提到）一律用纯函数。")
    body(
        doc,
        "判断边界可以概括成一句：能不能交给模型，取决于答错的代价谁承担。"
        "答错一个答辩问题，代价由学生自己承担，所以这里不让模型替他答。",
    )

    img_slot(doc, "图 3", "AI 协同：答复起草结果 / 评委追问两条输出")
    caption(doc, "图 3　AI 协同实拍——评委只追问，不给评价")

    # ── 四、关键技术
    h1(doc, "四、关键技术")

    table(
        doc,
        ["类别", "技术", "在本项目中的用途"],
        [
            ["文档解析", "python-docx + 自定义标题识别", "三重限制（长度、标点、编号）判定章节标题，避免正文误判"],
            [
                "规则引擎",
                "纯函数 + 正则",
                "文献双向核对、图表悬空、结构失衡、标题承诺；支持 [1] / [1,2] / [1-3] 引用写法，并对 [0,1] 数学区间防误报",
            ],
            [
                "文本相似",
                "字符 bigram 重叠系数",
                "重复问题检测。选它而非 Jaccard：学生追问常只说半句，长度差会稀释 Jaccard，重叠系数除以较短集合仍可识别",
            ],
            [
                "风险建模",
                "加权评分模型",
                "风险 = 次数×1.0 + (涉及时段−1)×1.5 + 未答复×1.2；权重对应可观察事实，不是调参结果",
            ],
            ["判分", "要点关键词覆盖", "只报命中数不折算分数；空答标记「未作答」而非 0 分"],
            ["大模型", "OpenAI 兼容接口（DeepSeek）", "仅两处调用，约束写在提示词里，产出标记待审核"],
            [
                "数据存储",
                "SQLite + 幂等迁移",
                "单文件数据库；PRAGMA 判列存在后逐列 ALTER，老库打开即升级，历史数据不丢",
            ],
            ["状态管理", "Streamlit Session State", "双身份切换、控件 key 按身份隔离，避免跨用户状态串值"],
            [
                "前端",
                "设计 token + CSS 注入",
                "统一色彩、字号、间距、圆角；系统字体栈（不依赖外部字体，断网不出方框）；响应式三档（1100 / 900 / 640）",
            ],
            ["无障碍", "WCAG AA", "正文与弱化文字对比度经计算校验（17.05 / 7.63 / 5.14 : 1），支持系统「减少动效」偏好"],
            ["工程", "pytest + AppTest 交互测试", "85 条测试，含真实交互用例（身份切换、表单串值）"],
        ],
        widths=[2.4, 4.6, 8.2],
    )

    img_slot(doc, "图 4", "写作台：问题清单与章节字数分布")
    caption(doc, "图 4　写作台——四类规则检查，同一份文档同一份结果")

    # ── 五、图片
    h1(doc, "五、项目图片")

    body(doc, "本节预留图片位，待补充。建议按下表配图，并给每张图写一行图注，说明「这张图证明了什么」。")
    table(
        doc,
        ["位置", "应放内容", "建议配图说明"],
        [
            ["图 1", "首页总览", "三层卡片、闭环徽章链、KPI 状态"],
            ["图 2", "老师端", "待办列表 / 我的学生表 / 沉淀库分类分布"],
            ["图 3", "预演台与 AI 协同", "风险画像表 + 题单 + 要点覆盖反馈 + 追问输出"],
            ["图 4", "写作台", "上传 docx 后的问题清单与章节字数分布"],
            ["图 5", "环境自检", "密钥四态诊断与连通性测试"],
            ["图 6", "移动端适配", "窄屏下的单列布局（证明响应式）"],
        ],
        widths=[1.8, 4.0, 9.4],
    )
    img_slot(doc, "图 5", "环境自检：密钥四态诊断与连通性测试")
    caption(doc, "图 5　环境自检——四态诊断，一眼看出是没配、配错还是没余额")

    img_slot(doc, "图 6", "移动端适配：窄屏下的单列布局")
    caption(doc, "图 6　移动端适配——窄屏下 KPI 单列、按钮全宽、表格横向滚动")

    # ── 六、来源与优化
    h1(doc, "六、项目来源与优化部分说明")

    body(doc, "本项目为独立开发，未复用第三方项目代码。", bold_prefix="")

    for item in (
        "开发起点：2026 年 10 月 22 日，全部代码在本仓库内从零编写；",
        "第三方依赖均为通用开源库：Streamlit（界面框架）、python-docx（文档解析）、openai SDK（模型调用）、"
        "pandas（表格渲染）、reportlab（仅用于生成分镜表 PDF 的工具脚本，不参与运行时）；",
        "不涉及对维普、知网等商业系统的逆向或数据抓取。",
    ):
        bullet(doc, item)

    body(doc, "项目自身经历的三次目标调整（如实记录，便于评审理解演进逻辑）：")
    table(
        doc,
        ["阶段", "初始设想", "调整原因", "结果"],
        [
            ["v1", "学位论文「预评审平台」：六维评分、答辩押题", "与维普类系统正面重叠，缺乏数据优势", "放弃评分功能"],
            ["v2", "转向「导学协同」：答疑沉淀 → 诊断 → 预演", "找到了别人没有的数据（答疑史）", "确立三层架构"],
            [
                "v3",
                "增加学生 / 导师双身份、公开与隐私分级",
                "导师现场反馈：看不到论文题目、学生与导师未绑定、隐私无边界",
                "补数据模型与可见性规则",
            ],
        ],
        widths=[1.4, 5.2, 5.4, 3.2],
    )

    body(doc, "已知边界（如实标注）：")
    for item in (
        "示例数据为模拟数据（4 条虚构学生线、30 条答疑），页面与文档均已标明，不伪装为真实采集；",
        "要点判分为关键词匹配，属保守下限，同义表述可能漏判，界面固定提示「自查清单，非成绩单，可人工修正」；",
        "演示版以身份切换代替登录，未实现密码与会话；接入学校统一认证时仅需替换一个函数；",
        "云端 SQLite 为临时存储，容器重启后数据重置，由启动自愈逻辑重新载入示例；",
        "预演台题库当前硬编码于代码，切换至差异较大的学科需调整题目配置。",
    ):
        bullet(doc, item)

    # ── 附录
    h1(doc, "附录　运行环境")
    table(
        doc,
        ["项目", "说明"],
        [
            ["语言与框架", "Python 3.13（云端建议 3.12）、Streamlit 1.66、pandas 3.x、python-docx 1.1、openai SDK"],
            ["数据存储", "单文件 SQLite，无需数据库服务"],
            ["部署方式", "Streamlit Community Cloud，密钥通过 Secrets 注入，本地可用 .env"],
            ["测试", "pytest 85 条，含 AppTest 交互用例，全部使用临时数据库"],
            ["访问方式", "浏览器打开即可，支持手机窄屏（响应式三档）"],
        ],
        widths=[3.2, 12.0],
    )

    doc.save(OUT)
    print(f"已生成：{OUT}　（{OUT.stat().st_size / 1024:.0f} KB）")


if __name__ == "__main__":
    build()
