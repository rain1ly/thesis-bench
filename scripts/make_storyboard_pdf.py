"""生成《演示视频分镜表》PDF。

一次性工具，跑一次出 PDF，改内容就改这里的 ROWS 再跑。
reportlab 不在 requirements.txt 里 —— 它只是做材料用，不进运行时依赖。

版式：两页 A4 横向。第 1 页只有分镜表（拍摄时看这一页就够），第 2 页是录前准备与照抄输入。

用法：
    .venv\\Scripts\\python.exe scripts\\make_storyboard_pdf.py
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = Path.home() / "Desktop" / "演示视频分镜表.pdf"

FONT_DIR = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("YaHei", str(FONT_DIR / "msyh.ttc"), subfontIndex=0))
pdfmetrics.registerFont(TTFont("Hei", str(FONT_DIR / "simhei.ttf")))

INK = colors.HexColor("#2C2C2A")
MUTED = colors.HexColor("#5F5E5A")
LINE = colors.HexColor("#D3D1C7")
BAND = colors.HexColor("#F1EFE8")
ACCENT = colors.HexColor("#185FA5")
DANGER = colors.HexColor("#A32D2D")

TITLE = ParagraphStyle("t", fontName="Hei", fontSize=17, leading=21, textColor=INK)
SUB = ParagraphStyle("s", fontName="YaHei", fontSize=8.5, leading=13, textColor=MUTED, wordWrap="CJK")
H2 = ParagraphStyle("h2", fontName="Hei", fontSize=11, leading=15, textColor=INK, spaceBefore=6, spaceAfter=3)
BODY = ParagraphStyle("b", fontName="YaHei", fontSize=8.4, leading=13, textColor=INK, wordWrap="CJK")
NOTE = ParagraphStyle("n", parent=BODY, fontSize=8, leading=12, textColor=MUTED, wordWrap="CJK")
# wordWrap="CJK" 是必须的，不是可选优化：
# reportlab 默认按空格断词，而中文没有空格 —— 整段会被当成一个不可分割的"单词"，
# 列宽装不下时不会换行，而是把词整个甩到下一行并溢出列边界。
# 现象：明明列很宽，一行却只排了十几个字，下一行离谱地长。
CELL = ParagraphStyle(
    "c",
    fontName="YaHei",
    fontSize=8.8,
    leading=12.6,
    textColor=INK,
    alignment=TA_LEFT,
    wordWrap="CJK",
)
CELL_C = ParagraphStyle("cc", parent=CELL, fontName="Hei", textColor=colors.HexColor("#0C447C"))
CELL_MUTED = ParagraphStyle("cm", parent=CELL, fontSize=8.2, leading=12.6, textColor=MUTED)
TH = ParagraphStyle("th", fontName="Hei", fontSize=9.2, leading=13, textColor=colors.white)

ROWS = [
    ("0:00–0:14", "首页静止，<b>鼠标不动</b>", "写了三年一万多字，自己读五遍看不出问题；导师只有半小时；答辩十分钟被问住"),
    ("0:14–0:26", "仍停首页", "问题不是他不会写，是<b>没人记得他一路卡在哪</b>"),
    ("0:26–0:40", "缓慢扫过主卡：黄色「论文工坊」、三段链条、右下 COVERAGE 圆环", "所以拆成三层，是<b>一条链</b>：上一层的产出是下一层的输入。圆环里已经是埋钩子后的真实覆盖率"),
    ("0:40–1:02", "点导航 02 滚到答疑台：分类选「数据分析」，答疑老师选「我的指导老师」，可见性选「隐私」", "提问先定三件事：属于哪类问题、交给谁、给谁看。隐私只有我和老师可见"),
    ("1:02–1:16", "输入问题 → 下方出现「问过 1 次，相似 62%」", "还没提交就提示问过 —— 这一步不调模型，字符重叠就够"),
    ("1:16–1:33", "点提交 → 状态面板展开：读取题目与分类 → 匹配历史 1 条 → 草稿<b>逐字</b>写出", "AI 只给草稿，200 字以内；涉及数据判断写「需要导师确认」。逐字返回是为了让它看起来在处理，而不是一个转圈图标"),
    ("1:33–2:04", "点<b>顶栏右上身份方框</b> → 切到老师 → 同区整段变形为待办 → 改一句 → <b>勾「我已核对」</b> → 通过入库 → 我的学生表", "换身份看：老师这边是待办和名单，论文题目就在表里。<b>不勾选点不了通过</b> —— AI 草稿不经过我确认就不算答复"),
    ("2:04–2:16", "顶栏切回<b>学生</b> → 我的问题 → 答复已入库", "学生看到的是导师改过的定稿，不是 AI 原话"),
    ("2:16–2:38", "点导航 03 滚到写作台 → 上传 samples 的 docx → 13 项问题", "四类规则检查，确定性：同一份文档永远得到同一份清单"),
    ("2:38–2:54", "点导航 04 滚到预演台 → 风险画像表（学生身份直接是自己的，无选择框）", "出题依据不是题库，是<b>这个学生的困惑史</b>：数据来源 4 次、横跨三个阶段"),
    ("2:54–3:06", "生成题单 → 展开第 1 题", "答题前不给要点，那是答案"),
    ("3:06–3:18", "作答 → 提交 → <b>命中 1/3</b>，漏点弹出", "答完才告诉你漏了「说清数据边界」"),
    ("3:18–3:34", "点「让 AI 评委追问」", "AI 不给评价，只继续问（念出两条追问）"),
    ("3:34–3:48", "再答一遍 → <b>3/3</b> → 预演记录 → 逐题轨迹", "1/3 到 3/3。<b>价值不在这一屏，在这条线往哪走</b>"),
    ("3:48–4:00", "点导航 01 回首页，停在圆环与链条", "边界说清楚：数据是模拟的、要点匹配是下限、AI 只起草不裁决"),
]

PREP = [
    ("① 推送并验收", "git push（走 SSH，已配好）→ 等 Cloud 自动部署 2 分钟 → 按 <b>docs/部署说明.md</b> 第 4 节 9 条逐条验收。云端和本地必须是同一版，否则录的和评委看的是两个东西"),
    ("② 重置数据", "本地跑 <b>scripts/reset_demo.py --yes</b> 回到 30 条干净示例。不重置会查出「问过 2 次、相似 100%」—— 试过的那句已经进库了"),
    ("③ 埋钩子", "预演台答一次只说来源（1/3）→ 关掉。顺带让首页 COVERAGE 圆环有真实数字，不再是一只空环"),
    ("④ 定身份", "点<b>顶栏右上身份方框</b>确认「学生 · 陈同学」，别停在老师身份开录（重置后她有 15 条答疑）"),
    ("⑤ 选录制地址", "用<b>云端 URL</b> 录（评委点开的就是它，顺带验证线上可用）；云端抽风就退回 localhost:8501 本地录，界面一致"),
    ("⑥ 清场", "F11 全屏、缩放 100%、关通知；桌面别开终端，别露 .env；只留一个标签页"),
]

INPUTS = [
    ("答疑台", "我的数据只有200条，做回归够吗？", "命中 62%（历史记录：样本量只有 300 条，做回归够吗？）"),
    ("预演台 · 第一答", "数据来自公开数据集，但和我的传感器对不上。", "1/3 · 漏「说清数据边界」「对不齐怎么处理」"),
    ("预演台 · 第二答", "数据来自UCI的公开数据集，做了字段映射和量纲换算；局限是只覆盖夏季，极寒场景不适用。", "3/3 · 扎实"),
    ("写作台", "data/samples/ 里任一份 docx", "样本一 6 项 / 3 严重；样本二 7 项 / 4 严重"),
]

# 上面右侧数字全部是「重置后」的实测值。不重置会出现 100% 相似、17 条答疑 —— 画面和这里对不上。

TRAPS = [
    "鼠标乱晃 —— 录屏第一杀手。移动要慢，点到哪儿停稳半秒再点。",
    "等加载 —— 云端首次点击有 1–3 秒延迟，等的时候别说话、别重复点。",
    "念界面文字 —— 「我点击这里，这里显示了……」信息量为零。说结论，说为什么。",
    "说「我们的系统非常强大」 —— 一个形容词都别用，让 1/3 → 3/3 自己说话。",
    "藏局限 —— 评委见过的作品都吹全能；主动说局限反而显得可信。",
    "切身份切太快 —— 切完停一秒再动鼠标，否则观众看不清现在是「谁」在看。",
    "念稿感 —— 眼睛盯着屏幕念，一听就是读的。提前念两遍，说人话。",
    "最后一小时才录 —— 出一次容器重启，设置全得重来。",
]


def p(text: str, style: ParagraphStyle = CELL) -> Paragraph:
    return Paragraph(text, style)


def box(rows: list[list], widths: list[float], zebra: tuple[int, ...] = ()) -> Table:
    t = Table(rows, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for i in zebra:
        style.append(("BACKGROUND", (0, i), (-1, i), BAND))
    t.setStyle(TableStyle(style))
    return t


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("YaHei", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(14 * mm, 9 * mm, "论文工坊 · ThesisBench ｜ 演示视频分镜表 ｜ 2026-11-14")
    canvas.drawRightString(landscape(A4)[0] - 14 * mm, 9 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def build() -> None:
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=15 * mm,
        title="论文工坊 · 演示视频分镜表 v2",
        author="论文工坊 ThesisBench",
    )
    width = landscape(A4)[0] - 28 * mm
    story = []

    # ── 第 1 页：只放分镜表，拍的时候看这一页
    story.append(Paragraph("演示视频分镜表", TITLE))
    story.append(
        Paragraph(
            "2026 第九届传智杯 · AI 创新应用挑战赛（个人赛 · B 组）　|　"
            "4 分钟版　|　含 2 分钟 AI 协同实拍　|　2026-11-14 v4（单页滚动版 · 顶栏切身份 · 预演台分形态）",
            SUB,
        )
    )
    story.append(Spacer(1, 3 * mm))

    head = [p("时间", TH), p("画面 / 操作", TH), p("口播要点", TH)]
    data = [head] + [[p(t, CELL_C), p(scene), p(vo)] for t, scene, vo in ROWS]
    story.append(box(data, [22 * mm, 92 * mm, width - 114 * mm], zebra=tuple(i for i in range(1, len(data)) if i % 2 == 0)))

    story.append(Spacer(1, 2.5 * mm))
    story.append(
        Paragraph(
            "录前准备、可照抄的输入句子、八个翻车点见第 2 页。"
            "　<b>最容易被漏掉的是「埋钩子」</b>：单答一次只是功能演示，有 1/3 → 3/3 的轨迹才是闭环。",
            NOTE,
        )
    )

    # ── 第 2 页：录前 → 录时 → 别踩的坑
    story.append(PageBreak())

    story.append(Paragraph("录前准备与录屏输入", TITLE))
    story.append(
        Paragraph("第 1 页拍摄时看，这一页开录前看一遍。顺序别换 —— 第②条没做，后面录得再顺，视频也只是功能清单。", SUB)
    )
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("录之前先做六件事", H2))
    story.append(Spacer(1, 3 * mm))

    prep_rows = [[p("", TH), p("做法", TH)]]
    prep_rows[0] = [p("步骤", TH), p("做法", TH)]
    for k, v in PREP:
        prep_rows.append([p(k, CELL_C), p(v)])
    story.append(box(prep_rows, [26 * mm, width - 26 * mm], zebra=(2, 4)))
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            "<font color='#A32D2D'>② 是唯一一步不在录屏里、却决定视频有没有说服力的动作</font>："
            "没有那条 1/3 → 3/3 的轨迹，预演台在观众眼里只是个答题框。",
            NOTE,
        )
    )

    story.append(Paragraph("录屏时照抄这几句（已实测）", H2))
    in_rows = [[p("位置", TH), p("输入内容", TH), p("预期结果", TH)]]
    for where, text, expect in INPUTS:
        in_rows.append([p(where, CELL_C), p(f"<font name='Hei'>{text}</font>"), p(expect, CELL_MUTED)])
    story.append(
        box(
            in_rows,
            [30 * mm, width * 0.53, width - 30 * mm - width * 0.53],
            zebra=(1, 3),
        )
    )
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            "以上为 2026-11-14 在示例数据上的实测值。改过题库、示例数据或章节结构后，"
            "<font color='#A32D2D'>录前重跑 scripts/preflight.py 并重新核对</font> —— "
            "视频里的数字和界面对不上，比没有视频更糟。　"
            "<font color='#0C447C'><b>收尾那一句：维普管交上去之后合不合规，"
            "我们管写出来之前卡在哪、能不能过答辩。</b></font>",
            NOTE,
        )
    )

    story.append(Paragraph("八个容易翻车的地方", H2))
    half = 4
    left = [Paragraph(f"<font name='Hei' color='#A32D2D'>{i}.</font>　{t}", NOTE) for i, t in enumerate(TRAPS[:half], 1)]
    right = [
        Paragraph(f"<font name='Hei' color='#A32D2D'>{i}.</font>　{t}", NOTE)
        for i, t in enumerate(TRAPS[half:], half + 1)
    ]
    trap_rows = [[left[i], right[i]] for i in range(half)]
    traps = Table(trap_rows, colWidths=[width / 2, width / 2])
    traps.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(traps)

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"已生成：{OUT}　（约 {OUT.stat().st_size / 1024:.0f} KB）")


if __name__ == "__main__":
    build()
