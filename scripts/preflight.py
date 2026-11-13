"""提交前体检 —— 一条命令跑完，别在演示当天才发现哪个页面是坏的。

做的事：
1. 跑全套 pytest
2. 用 AppTest 把五个页面各渲染一遍（不需要浏览器，20 秒内出结果）
3. 检查密钥状态（只报形态，不打印密钥）

用法：
    .venv\\Scripts\\python.exe scripts\\preflight.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 单页化之后只有一个入口，检查的是"五个区块是否都渲染出来"。
# 用锚点 id 判断，不用 st-key 类名：AppTest 只拿得到 markdown 文本，拿不到 DOM 的 class。
SECTIONS = ["home", "qa", "writing", "rehearsal", "tail"]

OK, BAD = "[PASS]", "[FAIL]"


def run_tests() -> bool:
    print("1/3 运行测试 …")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    tail = (proc.stdout or proc.stderr).strip().splitlines()
    print(f"     {tail[-1] if tail else '（无输出）'}")
    return proc.returncode == 0


def run_pages() -> bool:
    """渲染单页入口，并检查五个区块的容器都出现了。

    多页时代是逐页 switch_page；单页之后没有"页面"，
    改成断言每个 section 的 key 类名都出现在 DOM 里 ——
    某一段整块没渲染（比如身份分支写反）能当场发现。
    """
    print("2/3 渲染单页 …")
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()

    errs = [str(e.value) for e in at.exception]
    if errs:
        print(f" {BAD} app.py: {errs[0][:140]}")
        return False
    print(f" {OK} app.py 渲染无异常")

    html = " ".join(str(m.value) for m in at.markdown)
    all_ok = True
    for sec in SECTIONS:
        if f'id="{sec}"' in html:
            print(f" {OK} 区块 #{sec}")
        else:
            print(f" {BAD} 区块 #{sec} 未渲染")
            all_ok = False
    return all_ok


def check_key() -> bool:
    print("3/3 检查密钥 …")
    from core.ai_client import load_config

    cfg = load_config()
    print(f"     来源：{cfg.source}　状态：{cfg.state}　模型：{cfg.model}　密钥：{cfg.masked_key}")
    if cfg.state != "ok":
        print(f" {BAD} 密钥不可用（{cfg.state}），AI 相关功能会降级；不影响规则检查与出题判分。")
        return False
    print(f" {OK} 形态正常（是否真能用，去「环境自检」页点连通性测试）")
    return True


def main() -> int:
    print("=" * 52)
    tests_ok = run_tests()
    pages_ok = run_pages()
    key_ok = check_key()
    print("=" * 52)

    if tests_ok and pages_ok:
        print(f" {OK} 可以推送 / 部署" + ("" if key_ok else "（AI 功能不可用，其余正常）"))
        return 0
    print(f" {BAD} 先修上面标红的问题，别推")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
