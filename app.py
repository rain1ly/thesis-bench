"""论文工坊 · 单页入口

**为什么从多页改成单页**
四层是"一条链"，不是四个并列功能。分页让用户自己拼关系，滚动式则一路读下来：
写出来之前卡在哪 → 谁在等我 → 结构有什么毛病 → 答辩会被问什么。

一屏一个功能区，顶部导航用锚点跳，滚轮顺序就是叙事顺序。

**两个技术支点，缺一不可**
1. 每段用 `@st.fragment`：控件交互只重跑那一段，页面不会弹回顶部（见 ui/sections.py）
2. 锚点是原生 `<a href="#qa">`：只改 hash，浏览器自己滚，不走服务端往返

**代价**：没有 `pages/` 目录就删掉了 Streamlit 自动生成的侧边导航和 URL 路由，
位置感全靠顶部那条章节导航。切身份仍会整页重跑（身份是页面级状态），回到顶部 ——
这一条我认了，强行留位置得注入 JS 操作父页面，演示当天出问题比这个小毛病糟得多。
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import streamlit as st

from core import bootstrap, identity, qa_store, rehearsal, rehearsal_store
from core.ai_client import load_config, ping
from ui import components, home_view, sections, theme

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


# ------------------------------------------------------------------ 头部
actor = identity.ensure()
components.topbar(date=date.today().strftime("%Y.%m.%d"))
components.identity_chip(actor)
components.nav()

flash = st.session_state.pop("home_flash", None)
if flash:
    st.success(flash)

# ------------------------------------------------------------------ 01 首页
qa = qa_store.stats()
all_records = qa_store.list_records()
reh = rehearsal_store.stats()
risks = rehearsal.build_profile(all_records)
high_risks = sum(1 for t in risks if t.level == "高")
n_files, n_issues, n_severe = sample_stat()

# 首页所有"我的"数字都跟着身份走 ——
# 只让右下角队列变的话，切完身份整页看上去几乎没动静，像装饰
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

components.anchor("home")
with st.container(key="sec-home"):
    try:
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
                    "href": "#qa",
                },
                {
                    "no": "02",
                    "name": "写作台",
                    "en": "STRUCTURE CHECK",
                    "nums": f"{n_issues} ISS ／ {n_severe:02d} SEV",
                    "desc": "四类规则检查，不调模型。同一份文档永远得到同一份清单，结果可复现、可逐条核对。",
                    "href": "#writing",
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
                    "href": "#rehearsal",
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
            ],
            demo=bootstrap.is_demo(),
        )
    except Exception as exc:  # noqa: BLE001
        st.error(f"首页这一段出错：{type(exc).__name__} — {exc}")

# ------------------------------------------------------------------ 02-04
sections.qa_section(actor)
sections.writing_section(actor)
sections.rehearsal_section(actor)

# ------------------------------------------------------------------ 尾：数据来源 / 环境自检
components.anchor("tail")
with st.container(key="sec-tail"):
    st.markdown(
        "<div style='border-top:2px solid #111;margin-top:8px'></div>", unsafe_allow_html=True
    )
    c_left, c_right = st.columns([1, 1], gap="medium")

    with c_left:
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
                st.caption("清空之后，系统就把这份库当真实数据对待，不会再自动载入。")
            else:
                st.markdown("当前库**不是示例数据**，不提供一键清空。真实学生记录只能手工处理。")

    with c_right:
        with st.expander("环境自检 · 密钥与模型连通性"):
            cfg = load_config()
            if cfg.state == "ok":
                st.success(f"已读到密钥，来源：{cfg.source}")
            elif cfg.state == "placeholder":
                st.warning(f"文件找到了（{cfg.source}），但里面还是模板原文，密钥没填进去。")
            elif cfg.state == "invalid":
                st.warning(f"密钥只有 {len(cfg.api_key.strip())} 位，疑似复制不全。")
            else:
                st.error("没有读到密钥（查找位置：Streamlit Secrets、.env、环境变量）")

            st.caption(f"模型：{cfg.model}　|　接口：{cfg.base_url}")
            if st.button("测试连通性（8 token 探测）", key="ping_btn"):
                ok, msg = ping(cfg)
                (st.success if ok else st.error)(msg)

    st.caption(
        "论文工坊 · ThesisBench ｜ 演示版：身份切换代替登录，生产环境接学校统一认证　·　"
        "数据为示例数据，页面已标明"
    )
