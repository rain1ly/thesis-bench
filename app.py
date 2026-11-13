"""论文工坊 · 总览页

这一页只干一件事：让第一次打开的人在十秒内明白
**这套东西是什么、三层各自走到哪、数据是哪来的。**

版式按设计稿一比一实现（见 ui/home_view.py）：
贴边黑条 → 大卡片（描边标题 + 黄块 + 切角）→ 三段链条 → 圆环 + 待办队列 → 黑条 → 状态栏。

中间那条 01 → 02 → 03 不是三张并列卡片，是链条。箭头必须在，
因为产品的核心口径是「上一层的产出是下一层的输入」——
并列卡片会让版式说出相反的话。
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import streamlit as st

from core import bootstrap, identity, qa_store, rehearsal, rehearsal_store
from ui import components, home_view, theme

ROOT = Path(__file__).resolve().parent

st.set_page_config(page_title="论文工坊 · ThesisBench", layout="wide", page_icon="◧")
theme.inject()

# 空库自动长出来：云端容器重启、评委刚 clone，都不该看到空页面
bootstrap.ensure_demo()


@st.cache_data(show_spinner=False)
def sample_stat() -> tuple[int, int, int]:
    """拿仓库里的两份样本跑一遍规则检查，首页显示真实数字而不是写死的文案。"""
    from core.checker import run_all, summary
    from core.parser import parse_docx

    files = total = severe = 0
    for p in sorted((ROOT / "data" / "samples").glob("*.docx")):
        try:
            stat = summary(run_all(parse_docx(str(p))))
        except Exception:  # noqa: BLE001 - 首页不该因为一份坏样本白屏
            continue
        files += 1
        total += stat["total"]
        severe += stat["severe"]
    return files, total, severe


@st.cache_data(show_spinner=False)
def build_tag() -> str:
    """卡片右上角的 BUILD。写死过一次，之后就一直是旧的 —— 能读仓库就别手填。"""
    import subprocess

    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() or "DEMO"
    except Exception:  # noqa: BLE001 - 没有 git（云端压缩包）时不该报错
        return "DEMO"


def _wait_text(created: str) -> str:
    """把「什么时候提的」换算成「等了多久」。只有后者能驱动动作。"""
    try:
        t = datetime.strptime(created[:16], "%Y-%m-%d %H:%M")
    except Exception:  # noqa: BLE001
        return ""
    mins = int((datetime.now() - t).total_seconds() // 60)
    if mins < 0:
        return ""
    if mins < 60:
        return f"{mins}M"
    return f"{mins // 60}H{mins % 60:02d}"


def _queue_item(r) -> dict:
    return {
        "time": r.created_at[11:16] if len(r.created_at) >= 16 else "",
        "wait": _wait_text(r.created_at),
        "who": r.student,
        "cat": r.category,
        "text": r.question,
        "priv": r.is_private,
        "tag": "PRIV" if r.is_private else "POOL",
    }


actor = identity.render_switcher()

components.topbar(date=date.today().strftime("%Y.%m.%d"))
components.identity_chip(actor, "01 / 05")

# st.rerun 会丢掉本轮的提示消息，所以先存再显示 —— 否则点完清空什么反馈都没有
flash = st.session_state.pop("home_flash", None)
if flash:
    st.success(flash)

qa = qa_store.stats()
all_records = qa_store.list_records()
reh = rehearsal_store.stats()
risks = rehearsal.build_profile(all_records)
high_risks = sum(1 for t in risks if t.level == "高")
n_files, n_issues, n_severe = sample_stat()

if qa["total"] == 0:
    components.empty("答疑库是空的", "去「答疑台」载入示例数据，或直接以学生身份提第一个问题。")

# 首页所有"我的"数字都跟着身份走 ——
# 只让右下角队列变的话，切完身份整页看上去几乎没动静，像是装饰。
if actor.is_teacher:
    _mine = identity.inbox(all_records, actor.name)
    _pool = identity.public_pool(all_records)
    queue_rows = _mine[:3]
    qa_nums = f"待我处理 {len(_mine):02d} ／ 公开池 {len(_pool):02d}"
    queue_title = "待我处理"
    my_label, my_value = "待我处理", len(_mine)
else:
    _own = [r for r in all_records if r.student == actor.name]
    _waiting = [r for r in _own if not r.final_answer]
    queue_rows = _waiting[:3]
    qa_nums = f"我的提问 {len(_own):02d} ／ 待答 {len(_waiting):02d}"
    queue_title = "我的待答"
    my_label, my_value = "我的提问", len(_own)

coverage = int(round(reh["coverage"] * 100)) if reh["points_total"] else 0

home_view.render(
    build=build_tag(),
    date_str=date.today().strftime("%Y.%m.%d"),
    chain=[
        {
            "no": "01",
            "name": "答疑台",
            "en": "QA SYSTEM",
            "nums": qa_nums,
            "desc": "分类、交给谁、公开或隐私。AI 起草，导师改完才入库。这一层沉淀下来的困惑，是下面两层的输入。",
            "href": "/答疑台",
        },
        {
            "no": "02",
            "name": "写作台",
            "en": "STRUCTURE CHECK",
            "nums": f"{n_issues} ISS ／ {n_severe:02d} SEV",
            "desc": "四类规则检查，不调模型。同一份文档永远得到同一份清单，结果可复现、可逐条核对。",
            "href": "/写作台",
        },
        {
            "no": "03",
            "name": "预演台",
            "en": "REHEARSAL",
            "nums": (
                f"{reh['questions']:02d} Q ／ {coverage} PCT"
                if reh["points_total"]
                else f"{reh['questions']:02d} Q"
            ),
            "desc": "用他自己的困惑出题，只报要点覆盖，不打分。漏掉的要点直接指出来。",
            "href": "/预演台",
        },
    ],
    coverage=coverage,
    queue=[_queue_item(r) for r in queue_rows],
    queue_title=queue_title,
    foot=[
        f"TC {datetime.now().strftime('%H:%M:%S')}",
        f"REC {qa['total']}",
        f"{my_label} {my_value}",
        f"STU {len({r.student for r in all_records})}",
        f"TCH {len(identity.teacher_names())}",
        f"HIGH {high_risks}",
        f"MODE ／ {'TEACHER' if actor.is_teacher else 'STUDENT'}",
        f"SAMPLE {n_files}",
    ],
    page="01 / 05",
    demo=bootstrap.is_demo(),
)

# 三个入口放在最底部：它们走 Streamlit 前端路由（无刷新），
# 但插在卡片和大黑条之间会打断"主卡 → 待办 → 状态栏"的版式节奏。
st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
_l1, _l2, _l3, _l4 = st.columns([1, 1, 1, 2], gap="small")
with _l1:
    st.page_link("pages/1_答疑台.py", label="答疑台 →")
with _l2:
    st.page_link("pages/3_写作台.py", label="写作台 →")
with _l3:
    st.page_link("pages/4_预演台.py", label="预演台 →")
with _l4:
    st.page_link("pages/2_老师端.py", label="老师端 →")

with st.expander("数据来源与清空"):
    if bootstrap.is_demo():
        st.markdown(
            "当前库是**示例数据**：30 条模拟答疑、4 条虚构学生线，"
            "用于演示流程与冷启动。不是真实访谈记录，也不会写成真实记录。"
        )
        ok = st.checkbox("我确认要清空示例数据（答疑与预演记录会一起删）")
        if st.button("清空示例数据", disabled=not ok):
            n_qa, n_reh = bootstrap.clear_demo()
            st.session_state["home_flash"] = (
                f"已清空 {n_qa} 条答疑、{n_reh} 条预演记录。"
                "系统不会自动再灌回来 —— 想恢复去「答疑台」点「载入示例数据」。"
            )
            st.rerun()
        st.caption("清空之后，系统就把这份库当真实数据对待，不会再自动载入，也不再提供这个清空入口。")
    else:
        st.markdown("当前库**不是示例数据**，不提供一键清空。真实学生记录只能手工处理。")
