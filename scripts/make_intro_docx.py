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

    normal = doc.styles["Normal"]
    normal.font.name = SONG
    normal.font.size = Pt(10.5)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), SONG)

    # ══════════════════════════════════ 封面
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

    for _ in range(5):
        doc.add_paragraph()

    for line in (
        "2026 第九届传智杯全国大学生数智创新与 AI 应用大赛",
        "AI 创新应用挑战赛（技术应用赛 · 个人赛 · B 组）",
        "",
        "2026 年 11 月",
    ):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(line)
        r.font.size = Pt(11)
        r.font.color.rgb = INK if line else GRAY
        cn_font(r)

    doc.add_page_break()

    # ══════════════════════════════════ 阅读指引
    h1(doc, "本材料与评审维度的对应关系")

    body(
        doc,
        "为便于评审，本材料按评审维度的权重组织章节。下表可直接用于索引："
        "每个维度都能在指定章节找到对应的事实、数据与可验证材料。",
    )
    table(
        doc,
        ["评审维度", "权重", "对应章节", "该章提供的关键证据"],
        [
            [
                "过程可复现性与演进链路",
                "25%",
                "第三章",
                "25 次提交时间线、三次推翻记录、Prompt 归档与约束来历",
            ],
            [
                "解题有效性与实用价值",
                "25%",
                "第一、二章",
                "痛点定义、完整闭环（答疑→诊断→预演→回流）、双身份使用路径",
            ],
            [
                "方法创新性与意图控制",
                "20%",
                "第三章 3.3、第四章",
                "用答疑史出题的方法、Prompt 逐条约束、AI 职责边界的四次否决",
            ],
            [
                "工程质量与架构设计",
                "15%",
                "第四章",
                "四个关键决策、85 条测试、隐私可见性规则、密钥四态处理",
            ],
            [
                "用户体验与产品精细度",
                "15%",
                "第五章",
                "设计系统、响应式三档、对比度实测、AI 状态与失败原因分类",
            ],
        ],
        widths=[4.6, 1.4, 3.0, 6.2],
    )

    body(
        doc,
        "所有数字（提交次数、测试条数、检出问题数、响应字数）均可在仓库中复现，"
        "方法见第三章 3.6。",
    )

    # ══════════════════════════════════ 一
    h1(doc, "一、问题定义与定位")

    h2(doc, "1.1 一个具体的场景")
    body(
        doc,
        "学生陈某在开题时问「我的数据从哪来才可信」，导师答了一次；"
        "中期他又问了一遍，导师又答了一遍；到定稿前他第三次问，"
        "这次问的是「我之前说的那个数据集和我的传感器对不上」。",
    )
    body(
        doc,
        "（本场景取自系统内置示例数据，是按真实提问模式合成的典型情形，非真实访谈记录。"
        "真实样本的采集与脱敏列为下一版计划，见 7.4。）",
        indent=False,
    )
    body(doc, "三个问题分别出现，看起来都不算大。但把它们连起来看，会发现三件事同时发生了：")
    bullet(doc, "学生没有记录自己问过什么，于是同样的问题反复出现；", bold_prefix="一是　")
    bullet(doc, "导师不知道这个问题已经答过两次，每次都要重新组织语言；", bold_prefix="二是　")
    bullet(doc, "直到答辩前，谁都没发现「数据边界」这件事其实一直没想清楚。", bold_prefix="三是　")

    h2(doc, "1.2 三件事没人做")
    body(
        doc,
        "现有的论文管理系统，从格式合规到查重流程都很完整，但它们都在处理「交上去之后」的问题。"
        "上面那三件事发生在「写出来的过程中」，目前没有工具管：",
    )
    bullet(doc, "学生的困惑史没有被记录，所以「他卡在哪」无法被分析；", bold_prefix="记录　")
    bullet(doc, "导师的重复劳动没有被复用，同样的答复每次重写；", bold_prefix="复用　")
    bullet(doc, "学生在答辩前无法自查「哪些地方其实说不清」。", bold_prefix="自查　")

    h2(doc, "1.3 与合规系统的边界")
    table(
        doc,
        ["维度", "合规审查系统（如维普）", "论文工坊（本项目）"],
        [
            ["输入数据", "论文成品", "论文 + 学生的答疑记录"],
            ["介入时点", "提交之后", "写作过程 + 答辩之前"],
            ["输出", "合规报告（查重率、格式项）", "诊断清单 + 答辩预演题单"],
            ["判断依据", "比对库 + 格式规范", "确定性规则 + 学生自己的困惑记录"],
        ],
        widths=[3.2, 5.6, 6.4],
    )
    body(doc, "本项目明确不做三件事：不查重、不代写、不管流程。")

    h2(doc, "1.4 一句定位")
    body(
        doc,
        "合规系统管「交上去之后合不合规」，本项目管「写出来之前卡在哪、能不能过答辩」。",
        indent=False,
    )

    # ══════════════════════════════════ 二
    h1(doc, "二、系统闭环与使用方式")

    h2(doc, "2.1 一条链，三层")
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
        "    答疑史 → 主题风险画像 → 出题 → 作答 → 要点覆盖判分\n"
        "                    ↓\n"
        "    发现缺口 → 带着新问题回到①",
    )

    h2(doc, "2.2 三个模块")
    body(
        doc,
        "提问时先定三件事：问题分类（论文写作 / 数据分析 / 代码实现 / 系统使用 / 格式规范 / 其他）、"
        "交给哪位老师（我的导师 / 指定其他老师 / 公开给所有老师）、可见性（公开 / 隐私）。"
        "AI 起草答复草稿，导师审核修改后才入库；学生提交前，系统会比对历史记录并提示"
        "「这个问题你自己问过几次」。",
        bold_prefix="① 答疑台 · 学生端　",
    )
    body(
        doc,
        "待办按「点名找我的 → 公开池」排序，隐私问题优先；「我的学生」一栏显示每人论文题目、"
        "提问数、未答复数与风险等级；「沉淀库」按分类查看已通过的公开问答并统计分布。",
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
        "按该学生的答疑记录计算主题风险分，生成答辩预演题单；作答后给出要点覆盖反馈；"
        "可调用 AI 扮演评委追问；逐题轨迹记录「1/3 → 3/3」的改进过程。",
        bold_prefix="③ 预演台　",
    )

    h2(doc, "2.3 双身份与可见性")
    body(
        doc,
        "系统区分学生与老师两种身份。学生只能看到自己的问题与已通过的公开问答；"
        "老师只能看到指派给自己的、以及公开池中的问题。",
    )
    body(
        doc,
        "一条硬规则：隐私问题永不进入公开池——包括「标记为隐私但未指定老师」的异常数据，"
        "系统选择让谁都看不见，而不是越权派发给其他老师。这条规则有专门的测试用例。",
    )

    h2(doc, "2.4 使用方式")
    table(
        doc,
        ["步骤", "操作"],
        [
            ["1", "访问在线地址（或本地运行 streamlit run app.py），首次打开自动载入示例数据"],
            ["2", "侧边栏选择身份：学生 / 老师"],
            ["3", "学生：填写论文题目与导师 → 提问 → 查看答复 → 打开预演台自测"],
            ["4", "老师：进入老师端 → 处理待办 → 查看名下学生 → 浏览沉淀库"],
            ["5", "上传论文到写作台，获得结构性问题清单"],
        ],
        widths=[2.0, 13.2],
    )

    img_slot(doc, "图 1", "首页总览：三层卡片、闭环徽章链、四项指标")
    caption(doc, "图 1　首页总览——十秒内说清「这是什么、三层各自走到哪」")

    # ══════════════════════════════════ 三
    h1(doc, "三、开发过程与 AI 协作")

    body(
        doc,
        "本项目由一名零编程基础的学生（作者本人）在 AI 辅助下完成。"
        "AI 承担编码，作者承担判断。本章记录判断发生在哪里。",
    )

    h2(doc, "3.1 开发时间线")
    body(
        doc,
        "下表按开发阶段排列。P 编号是本项目的阶段标记，与每条 git 提交信息末尾的编号一致，"
        "可用 git log 逐条核对。",
    )
    table(
        doc,
        ["阶段", "时间", "做了什么", "为什么现在做"],
        [
            ["P01–P06", "10-22 ~ 10-23", "规则检查、答疑台、存储层、环境自检", "先把不依赖模型的链路跑通，模型出错时才能判断是代码问题还是提示词问题"],
            ["P07", "10-24", "预演台：风险画像、题库、要点判分", "有了答疑史才能出题，顺序不能反"],
            ["P08", "10-24", "总览页与启动自愈", "空库时第一屏是空的，演示价值为零"],
            ["P09–P12", "10-24", "技术文档、部署说明、视频脚本、分镜表", "作品需要能被复现，不只是能跑"],
            ["P13", "10-29", "学生导师绑定、可见性规则、老师端", "**导师现场反馈推翻了原有判断**，见 3.2"],
            ["P14–P16", "10-29", "设计系统、图标缺陷修复、身份状态缺陷修复", "界面是最先被看见的部分；两处缺陷由使用者实测发现"],
            ["P20", "11-11", "Prompt 归档补全、AI 协作说明", "按评审细则补齐过程材料"],
        ],
        widths=[2.0, 2.6, 5.4, 5.2],
    )

    h2(doc, "3.2 三次由人的判断推翻 AI 方案")
    body(
        doc,
        "这三件事比功能清单更能说明协作是真实的——因为只有真人会否决 AI。",
        indent=False,
    )

    body(
        doc,
        "AI 给出的第一版方案是「结构 / 方法 / 数据 / 论证 / 规范 / 创新」六维打分，"
        "功能更完整、演示更好看。作者否掉了：分数不可验证，学生会为分数辩护而不是为内容改进；"
        "而且这套评分与合规系统正面重叠，我们没有数据优势。最终改为「只报要点覆盖、不打分」，"
        "并规定答题前不显示考察要点。",
        bold_prefix="其一 · 否掉六维评分　",
    )
    body(
        doc,
        "最初的定位是「学位论文预评审平台」——查漏、评分、押题。作者判断这条赛道"
        "无法取胜：对方有采购渠道和比对库。于是整体转向「导学协同」，把「答疑史」当成核心数据资产，"
        "定位从「更好的检测工具」变成「别人做不了的事」。",
        bold_prefix="其二 · 重做整个选题定位　",
    )
    body(
        doc,
        "技术文档原本写着「刻意不做用户体系，等真要多角色登录了再拆」。"
        "指导教师看完系统后当场指出四件事：学生与导师没有绑定、老师看不到论文题目、"
        "公开与隐私没有边界、提问没有分类。作者判断这不是「技术复杂度」而是"
        "**数据模型缺了东西**，补关系的成本远小于让整个场景不成立。最终为答疑表新增四列、"
        "新建学生与教师两张表、新增老师端页面。**原判断连同推翻依据一起留在技术文档里，不删旧结论。**",
        bold_prefix="其三 · 导师反馈推翻文档判断　",
    )

    h2(doc, "3.3 Prompt 工程：以「评委追问」为例")
    body(doc, "全系统只有两处调用大模型，两处 Prompt 的全部约束如下（追问场景）：")
    table(
        doc,
        ["#", "约束", "不加会怎样"],
        [
            ["1", "只针对空泛、前后不一致、未交代清楚处追问", "模型会追问细枝末节，那不是评委的问法"],
            ["2", "输出 2 条，每条不超过 40 字", "不限条数会输出五六条，学生看不过来"],
            ["3", "答得完整时只输出「暂无可追问」", "不给出路，模型为凑满条数会硬编问题，学生一眼识破"],
            ["4", "评委不打分，只继续问", "否则输出必然滑向「回答得比较完整，但可以更具体」这类泛泛点评"],
            ["5", "不复述答案、不给建议", "复述使追问变长而信息量为零；给建议则越界成了导师"],
        ],
        widths=[1.0, 6.6, 7.6],
    )
    body(
        doc,
        "第 3 条是这套 Prompt 里最关键的一条：**给模型一个「不做事」的出口**。"
        "不给出口，它一定会为了完成任务而编造——而学生识破一次，整套预演的可信度就没了。",
    )
    body(doc, "实测（问题：「你的数据从哪来的，为什么可信？」；学生答「来自公开数据集，但和我的传感器对不上，只保留了能对上的字段」）：")
    quote(
        doc,
        "1. 公开数据集具体是哪个名称、哪个版本，如何核查？\n"
        "2. 对不上的字段占多少比例，只保留能对上的字段会带来什么偏差？",
    )
    body(
        doc,
        "两条分别为 24 字与 28 字，不含评价词、不复述、不给建议，与五条约束逐条吻合。"
        "另一处 Prompt（答复起草）的实测输出为 134 字，末尾原样出现「这一点需要导师确认」。",
    )

    h2(doc, "3.4 什么交给 AI，什么不交")
    table(
        doc,
        ["不做", "原因"],
        [
            ["不生成答辩参考答案", "答辩没有标准答案；模型一给，学生就背"],
            ["不给论文打分", "分数不可验证，会诱导学生为分数辩护"],
            ["不裁决学术判断", "涉及研究设计、数据可得性的结论必须由导师确认，Prompt 中强制输出这句话"],
            ["不做语义判定的最终结论", "规则能判的（引用、结构、要点）全部用纯函数，可复现、出错可定位"],
        ],
        widths=[5.0, 10.2],
    )
    body(
        doc,
        "这四条的共同依据：**判断能不能交给 AI，取决于答错的代价谁承担。**",
        indent=False,
    )

    h2(doc, "3.5 过程材料索引")
    table(
        doc,
        ["材料", "位置", "内容"],
        [
            ["提交历史", "git log（25 次）", "每次提交对应一个可验证的功能范围"],
            ["Prompt 归档", "prompts/（4 份）", "两处 Prompt 全文、逐条约束来历、实测核对、哪些已验证/未验证"],
            ["AI 协作说明", "docs/AI协作说明.md", "分工表、三次推翻、四件不做的事"],
            ["技术文档", "docs/技术文档.md", "含「一次被推翻的判断」整节，保留原结论"],
            ["部署与复现", "docs/部署说明.md", "验收清单与故障对照表"],
            ["回归测试", "tests/（85 条）", "断言设计承诺，而非函数返回值"],
        ],
        widths=[3.0, 5.0, 7.2],
    )

    h2(doc, "3.6 三条可自行验证的线索")
    numbered(doc, "git log --oneline：提交是否按功能递进，而不是一次全量导入。")
    numbered(doc, "docs/技术文档.md 第 2.3.1 节：被推翻的判断是否真的保留着原话与推翻依据。")
    numbered(doc, "pytest -q：85 条测试是否真的全绿。")
    body(
        doc,
        "如果这三条查不出问题，说明过程是真的。反过来也成立：一次全量提交、看不出迭代痕迹的仓库，"
        "功能做得再多也解释不了它是怎么来的。",
    )

    img_slot(doc, "图 2", "老师端：待办列表 / 我的学生 / 沉淀库")
    caption(doc, "图 2　老师端——导师反馈后新增的页面，直接回应「老师那边能看到什么」")

    # ══════════════════════════════════ 四
    h1(doc, "四、工程质量与可验证性")

    h2(doc, "4.1 四个关键决策")
    body(doc, "技术选型只记录「有取舍」的部分，其余实现细节不属于评审关注点。")
    table(
        doc,
        ["决策", "选择", "为什么不是另一个"],
        [
            [
                "语义判断与数值计算分离",
                "规则引擎（纯函数）+ 模型（仅两处）",
                "全部交给模型则结果不可复现、出错无法定位；全部用规则则「这句话空不空」判不出来",
            ],
            [
                "重复问题检测",
                "字符 bigram 重叠系数",
                "不用 Jaccard：学生追问常只说半句，长度差会稀释并集，重叠系数除以较短集合仍可识别",
            ],
            [
                "数据存储",
                "单文件 SQLite + 幂等迁移",
                "评委 clone 后无需安装数据库服务；老库通过 PRAGMA 判列存在后逐列 ALTER，历史数据不丢",
            ],
            [
                "界面定制",
                "设计 token + CSS 注入，系统字体栈",
                "不引外部字体：云端冷启动、断网演示、内网评审都不会出现字体闪烁或方框",
            ],
        ],
        widths=[3.4, 4.4, 7.4],
    )

    h2(doc, "4.2 测试：断言的是设计承诺")
    body(
        doc,
        "85 条自动化测试，全部使用临时数据库，不触碰演示数据。"
        "其中相当比例的断言针对「如果破了，产品逻辑就塌了」的点：",
    )
    bullet(doc, "导师答案必须盖过 AI 草稿——AI 只起草不裁决的兜底；")
    bullet(doc, "跨阶段重复的风险必须高于同阶段重复——出题优先级的依据；")
    bullet(doc, "题单必须能追回答疑记录编号——「用你的困惑出题」的唯一证据；")
    bullet(doc, "空答必须标记「未作答」而不是 0 分——避免学生误以为已在准备；")
    bullet(doc, "清空示例数据之后不许自动回流——否则清空按钮形同虚设。")

    h2(doc, "4.3 数据安全与边界处理")
    bullet(doc, "隐私问题永不进入公开池，异常数据（隐私但未指派）宁可不可见也不越权派发；")
    bullet(doc, "密钥全程脱敏展示，不进日志、不进界面；")
    bullet(doc, "模型异常分类为中文原因（密钥无效 / 余额不足 / 模型不存在 / 限流 / 超时），"
                "避免把「要换密钥」和「要充值」混成一句「调用失败」；")
    bullet(doc, "AI 不可用不阻塞业务：问题照常入库，只是没有草稿，导师手写。")

    img_slot(doc, "图 3", "写作台：问题清单与章节字数分布")
    caption(doc, "图 3　写作台——四类规则检查，同一份文档永远得到同一份清单")

    # ══════════════════════════════════ 五
    h1(doc, "五、用户体验与产品精细度")

    h2(doc, "5.1 设计系统")
    body(
        doc,
        "视觉不是逐页手调的，而是由一套 token 统一控制——否则第四个页面开始就走样。",
    )
    table(
        doc,
        ["项", "取值", "理由"],
        [
            ["主色 / 背景", "墨蓝 #1E4B8F / 暖白 #FBFAF7", "纯白在投影仪上刺眼；墨蓝比亮蓝更稳"],
            ["正文字号", "15px / 行高 1.75", "中文阅读密度：16px 偏松、14px 偏挤"],
            ["字体", "系统中文栈（苹方 / 雅黑 / 思源）", "不引外部字体，断网演示也不出现方框"],
            ["响应式", "1100 / 900 / 640 三档", "窄屏时指标单列、按钮全宽、表格横向滚动"],
            ["无障碍", "对比度 17.05 / 7.63 / 5.14 : 1", "均高于 WCAG AA 要求的 4.5:1，并支持「减少动效」偏好"],
        ],
        widths=[3.0, 5.6, 6.6],
    )
    body(
        doc,
        "这些约束被写成了自动化测试：字体规则中一旦出现通配选择器、主题色与样式表不同步、"
        "对比度低于 4.5:1，测试就会失败。视觉问题不该靠人眼复查。",
    )

    h2(doc, "5.2 AI 响应状态与失败提示")
    body(
        doc,
        "AI 调用是系统里唯一「不一定成功」的环节，因此状态提示被当成功能而不是装饰：",
    )
    bullet(doc, "密钥状态四态区分：未配置 / 占位符 / 无效 / 正常，每种给不同的处理建议；")
    bullet(doc, "「环境自检」页提供一键连通性测试，返回模型原话而不是「连接成功」；")
    bullet(doc, "起草与追问均显示进行中状态；失败时给出可操作原因，而不是「出错了」；")
    bullet(doc, "无密钥时两处 AI 功能降级但整个系统仍可完整演示（当前版本的响应为一次性返回，"
                "流式输出已列入下一版计划）。")

    h2(doc, "5.3 交互细节")
    bullet(doc, "答题前不显示考察要点——显示了就是给答案；要点折叠并写明这个理由；")
    bullet(doc, "预演默认打开「最该练」的学生，而不是按姓名排序；")
    bullet(doc, "身份切换在侧边栏，切换后各页数据随之变化，指标口径随身份调整；")
    bullet(doc, "空状态给出下一步动作，而不是只提示「暂无数据」。")

    img_slot(doc, "图 4", "预演台：风险画像表、题单与要点覆盖反馈")
    caption(doc, "图 4　预演台——出题依据可追溯到具体答疑记录")

    # ══════════════════════════════════ 六
    h1(doc, "六、项目图片")

    body(doc, "本节预留图片位，按图注补充即可。建议每张图配一行说明「这张图证明了什么」，而不是只写功能名。")
    table(
        doc,
        ["位置", "应放内容", "建议图注"],
        [
            ["图 1", "首页总览", "三层卡片与闭环说明：十秒看完全貌"],
            ["图 2", "老师端", "待办、我的学生（含论文题目）、沉淀库"],
            ["图 3", "写作台", "问题清单与章节字数分布"],
            ["图 4", "预演台", "风险画像、题单、要点覆盖反馈"],
            ["图 5", "AI 协同", "答复起草结果与评委追问两条输出"],
            ["图 6", "环境自检", "密钥四态诊断与连通性测试"],
            ["图 7", "移动端", "窄屏单列布局，证明响应式"],
        ],
        widths=[1.8, 4.0, 9.4],
    )

    img_slot(doc, "图 5", "AI 协同：答复起草与评委追问的实际输出")
    caption(doc, "图 5　AI 协同实拍——评委只追问，不给评价")

    img_slot(doc, "图 6", "环境自检：密钥四态诊断与连通性测试")
    caption(doc, "图 6　环境自检——一眼看出是没配、配错还是没余额")

    img_slot(doc, "图 7", "移动端适配：窄屏下的单列布局")
    caption(doc, "图 7　移动端适配——窄屏下指标单列、按钮全宽、表格横向滚动")

    # ══════════════════════════════════ 七
    h1(doc, "七、项目来源、边界与后续")

    h2(doc, "7.1 来源说明")
    body(doc, "本项目为独立开发，未复用第三方项目代码。")
    bullet(doc, "开发起点：2026 年 10 月 22 日，全部代码在本仓库内从零编写；")
    bullet(doc, "第三方依赖均为通用开源库：Streamlit（界面框架）、python-docx（文档解析）、"
                "openai SDK（模型调用）、pandas（表格渲染）、reportlab（仅用于生成分镜表的工具脚本，不参与运行时）；")
    bullet(doc, "不涉及对商业论文系统的逆向或数据抓取。")

    h2(doc, "7.2 三次目标调整")
    table(
        doc,
        ["阶段", "初始设想", "调整原因", "结果"],
        [
            ["v1", "预评审平台：六维评分、答辩押题", "与合规系统正面重叠，缺乏数据优势", "放弃评分功能"],
            ["v2", "导学协同：答疑沉淀 → 诊断 → 预演", "找到别人没有的数据（答疑史）", "确立三层闭环"],
            ["v3", "增加双身份、公开与隐私分级", "导师现场反馈指出数据模型缺失", "补关系模型与可见性规则"],
        ],
        widths=[1.4, 5.2, 5.4, 3.2],
    )

    h2(doc, "7.3 已知边界")
    bullet(doc, "示例数据为模拟数据（4 条虚构学生线、30 条答疑），页面与文档均已标明，不伪装为真实采集；")
    bullet(doc, "要点判分为关键词匹配，属保守下限，同义表述可能漏判，界面固定提示「自查清单，非成绩单，可人工修正」；")
    bullet(doc, "演示版以身份切换代替登录，未实现密码与会话；接入学校统一认证时仅需替换一个函数；")
    bullet(doc, "云端 SQLite 为临时存储，容器重启后数据重置，由启动自愈逻辑重新载入示例；")
    bullet(doc, "预演台题库当前硬编码于代码，切换至差异较大的学科需调整题目配置。")

    h2(doc, "7.4 下一版计划")
    numbered(doc, "AI 响应改为流式输出，并展示模型思考状态；")
    numbered(doc, "题库外置为配置文件，支持跨学科替换；")
    numbered(doc, "引入真实脱敏答疑样本，替换部分模拟数据；")
    numbered(doc, "增加论文两版对比，输出「改了什么、有没有改好」的差异清单。")

    # ══════════════════════════════════ 附录
    h1(doc, "附录　运行环境")
    table(
        doc,
        ["项目", "说明"],
        [
            ["语言与框架", "Python 3.13（云端建议 3.12）、Streamlit 1.66、pandas 3.x、python-docx 1.1、openai SDK"],
            ["数据存储", "单文件 SQLite，无需数据库服务"],
            ["部署方式", "Streamlit Community Cloud，密钥通过 Secrets 注入；本地可用 .env"],
            ["测试", "pytest 85 条，含界面交互用例，全部使用临时数据库"],
            ["访问方式", "浏览器打开即可，支持手机窄屏（响应式三档）"],
        ],
        widths=[3.2, 12.0],
    )

    doc.save(OUT)
    print(f"已生成：{OUT}　（{OUT.stat().st_size / 1024:.0f} KB）")


if __name__ == "__main__":
    build()
