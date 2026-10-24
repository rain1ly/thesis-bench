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
OUT = ROOT / "docs" / "分镜表.pdf"

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
SUB = ParagraphStyle("s", fontName="YaHei", fontSize=8.5, leading=13, textColor=MUTED)
H2 = ParagraphStyle("h2", fontName="Hei", fontSize=11, leading=15, textColor=INK, spaceBefore=6, spaceAfter=3)
BODY = ParagraphStyle("b", fontName="YaHei", fontSize=8.4, leading=13, textColor=INK)
NOTE = ParagraphStyle("n", parent=BODY, fontSize=8, leading=12, textColor=MUTED)
CELL = ParagraphStyle("c", fontName="YaHei", fontSize=9, leading=13.2, textColor=INK, alignment=TA_LEFT)
CELL_C = ParagraphStyle("cc", parent=CELL, fontName="Hei", textColor=colors.HexColor("#0C447C"))
CELL_MUTED = ParagraphStyle("cm", parent=CELL, fontSize=8.2, leading=12.6, textColor=MUTED)
TH = ParagraphStyle("th", fontName="Hei", fontSize=9.2, leading=13, textColor=colors.white)

ROWS = [
    ("0:00–0:12", "首页静止，<b>鼠标不动</b>", "写了三年一万多字，自己读五遍看不出问题；导师只有半小时；答辩十分钟被问住"),
    ("0:12–0:22", "仍停首页", "问题不是他不会写，是<b>没人记得他一路卡在哪</b>"),
    ("0:22–0:35", "鼠标缓慢扫过三张卡片", "所以拆成三层，是<b>一条链</b>，不是三个功能"),
    ("0:35–1:00", "答疑台 → 提问框输入 → 出现「历史上问过 N 次」", "边打字边查重：问过几次一眼看得见。这一步不调模型，字符重叠就够"),
    ("1:00–1:20", "提交 → 导师审核 → 改一句 → 通过", "AI 只起草，导师改完才能入库；学术判断不交给模型"),
    ("1:20–1:45", "写作台 → 上传 samples 的 docx → 13 项问题", "四类规则检查，确定性，同一份文档永远同一份清单"),
    ("1:45–2:05", "预演台 → 风险画像表", "出题依据不是题库，是<b>这个学生问过什么</b>：数据来源 4 次、横跨三个阶段"),
    ("2:05–2:20", "生成题单 → 展开第 1 题", "答题前不给要点，那是答案"),
    ("2:20–2:35", "作答 → 提交 → <b>命中 1/3</b>，漏点弹出", "答完才告诉你漏了「说清数据边界」"),
    ("2:35–2:55", "点「让 AI 评委追问」", "AI 不给评价，只继续问（念出两条追问）"),
    ("2:55–3:10", "再答一遍 → <b>3/3</b> → 预演记录 → 逐题轨迹", "1/3 到 3/3。<b>价值不在这一屏，在这条线往哪走</b>"),
    ("3:10–3:25", "回首页", "边界说清楚：数据是模拟的、要点匹配是保守下限、AI 只起草不裁决"),
    ("3:25–3:35", "停在三张卡片", "一句话收尾：维普管交上去之后，我们管写出来之前"),
]

PREP = [
    ("① 埋钩子", "先答一次只说来源（得 1/3）→ 关掉；录的时候答第二遍拿 3/3，轨迹才出现 1/3 → 3/3"),
    ("② 唤醒容器", "免费版闲置会休眠，提前打开一次，等页面完全出来再开录"),
    ("③ 清场", "F11 全屏、缩放 100%、关通知；桌面不要开终端，不要露 .env"),
    ("④ 定窗口", "1280×800 或 1440×900，太宽字小、太窄卡片会挤成竖排"),
]

INPUTS = [
    ("答疑台", "我的数据只有200条，做回归够吗？", "命中 62%（历史记录：样本量只有 300 条，做回归够吗？）"),
    ("预演台 · 第一答", "数据来自公开数据集，但和我的传感器对不上。", "1/3 · 漏「说清数据边界」「对不齐怎么处理」"),
    ("预演台 · 第二答", "数据来自UCI的公开数据集，做了字段映射和量纲换算；局限是只覆盖夏季，极寒场景不适用。", "3/3 · 扎实"),
    ("写作台", "data/samples/ 里任一份 docx", "样本一 6 项 / 3 严重；样本二 7 项 / 4 严重"),
]

TRAPS = [
    "鼠标乱晃 —— 录屏第一杀手。移动要慢，点到哪儿停稳半秒再点。",
    "等加载 —— 云端首次点击有 1–3 秒延迟，等的时候别说话、别重复点。",
    "念界面文字 —— 「我点击这里，这里显示了……」信息量为零。说结论，说为什么。",
    "说「我们的系统非常强大」 —— 一个形容词都别用，让 1/3 → 3/3 自己说话。",
    "藏局限 —— 评委见过的作品都吹全能；主动说局限反而显得可信。",
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
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]
    for i in zebra:
        style.append(("BACKGROUND", (0, i), (-1, i), BAND))
    t.setStyle(TableStyle(style))
    return t


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("YaHei", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(14 * mm, 9 * mm, "论文工坊 · ThesisBench ｜ 演示视频分镜表 ｜ 2026-10-24")
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
        title="论文工坊 · 演示视频分镜表",
        author="论文工坊 ThesisBench",
    )
    width = landscape(A4)[0] - 28 * mm
    story = []

    # ── 第 1 页：只放分镜表，拍的时候看这一页
    story.append(Paragraph("演示视频分镜表", TITLE))
    story.append(
        Paragraph(
            "2026 第九届传智杯 · AI 创新应用挑战赛（个人赛 · B 组）　|　"
            "3 分钟版　|　含 2 分钟 AI 协同实拍　|　2026-10-24",
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
            "录前准备、可照抄的输入句子、六个翻车点见第 2 页。"
            "　<b>最容易被漏掉的是「埋钩子」</b>：单答一次只是功能演示，有 1/3 → 3/3 的轨迹才是闭环。",
            NOTE,
        )
    )

    # ── 第 2 页：录前 → 录时 → 别踩的坑
    story.append(PageBreak())

    story.append(Paragraph("录前准备与录屏输入", TITLE))
    story.append(
        Paragraph("第 1 页拍摄时看，这一页开录前看一遍。顺序别换 —— 第①条没做，后面录得再顺，视频也只是功能清单。", SUB)
    )
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("录之前先做四件事", H2))
    story.append(Spacer(1, 3 * mm))

    prep_rows = [[p("", TH), p("做法", TH)]]
    prep_rows[0] = [p("步骤", TH), p("做法", TH)]
    for k, v in PREP:
        prep_rows.append([p(k, CELL_C), p(v)])
    story.append(box(prep_rows, [26 * mm, width - 26 * mm], zebra=(2, 4)))
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            "<font color='#A32D2D'>① 是唯一一步不在录屏里、却决定视频有没有说服力的动作</font>："
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
            "以上为 2026-10-24 在示例数据上的实测值。改过题库、示例数据或章节结构后，"
            "<font color='#A32D2D'>录前重跑 scripts/preflight.py 并重新核对</font> —— "
            "视频里的数字和界面对不上，比没有视频更糟。",
            NOTE,
        )
    )

    story.append(Paragraph("六个容易翻车的地方", H2))
    half = 3
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

    story.append(Spacer(1, 3 * mm))
    story.append(
        Paragraph(
            "收尾那一句：维普管交上去之后合不合规，"
            "<font color='#0C447C'><b>我们管写出来之前卡在哪、能不能过答辩。</b></font>",
            ParagraphStyle("end", parent=BODY, fontSize=10, leading=15),
        )
    )

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"已生成：{OUT}　（约 {OUT.stat().st_size / 1024:.0f} KB）")


if __name__ == "__main__":
    build()
