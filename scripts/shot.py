"""截图工具：开发期用来看真实渲染，不参与运行。

为什么需要它：视觉问题用 AppTest 抓不到 —— 它只渲染结构、不算样式。
这次踩的坑（CSS 选择器里的 testid 在 Streamlit 1.66 已不存在）
代码层面完全看不出来，只能真的渲染一次。

用法：
    python scripts/shot.py                     # 截全部页面到临时目录
    python scripts/shot.py 8577 答疑台          # 只截一页
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

# 文件名去掉数字前缀就是 URL：pages/1_答疑台.py → /答疑台
PAGES = [
    ("首页", "/"),
    ("答疑台", "/答疑台"),
    ("老师端", "/老师端"),
    ("写作台", "/写作台"),
    ("预演台", "/预演台"),
]


def main() -> None:
    port = sys.argv[1] if len(sys.argv) > 1 else "8577"
    only = sys.argv[2] if len(sys.argv) > 2 else ""
    out = Path(tempfile.gettempdir())

    with sync_playwright() as p:
        # 用系统自带的 Edge：playwright 下载 chromium 要 150MB，演示前不值得等。
        # channel='msedge' 走本机已装的 Chromium 内核，渲染结果一致。
        browser = p.chromium.launch(channel="msedge")
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=2)

        for name, path in PAGES:
            if only and only not in name:
                continue
            url = f"http://localhost:{port}{path}"
            page.goto(url, wait_until="networkidle", timeout=45000)
            # Streamlit 是 WebSocket 增量渲染，networkidle 之后还有零星补丁
            time.sleep(2.5)
            f = out / f"shot_{name}.png"
            page.screenshot(path=str(f), full_page=True)
            print(f"{f}  {page.title()[:20]}")

        browser.close()


if __name__ == "__main__":
    main()
