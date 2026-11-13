"""导出真实 DOM 里的 data-testid 与类名 —— 用来核对 CSS 选择器。

起因：ui/theme.py 里有一批选择器（staVerticalBlockBorderWrapper、data-baseweb=...）
在 Streamlit 1.66 上根本不存在，样式静默失效。写 CSS 前必须先看一眼真实结构，
否则改一百行也白改。

用法：
    python scripts/dump_dom.py 8577 答疑台
"""

from __future__ import annotations

import sys
import time

from playwright.sync_api import sync_playwright


def main() -> None:
    port = sys.argv[1] if len(sys.argv) > 1 else "8577"
    path = sys.argv[2] if len(sys.argv) > 2 else "/"

    with sync_playwright() as p:
        # 用系统自带的 Edge：playwright 下载 chromium 要 150MB，演示前不值得等。
        # channel='msedge' 走本机已装的 Chromium 内核，渲染结果一致。
        browser = p.chromium.launch(channel="msedge")
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(f"http://localhost:{port}{path}", wait_until="networkidle", timeout=45000)
        time.sleep(2.5)

        rows = page.evaluate(
            """() => {
                const seen = new Map();
                document.querySelectorAll('[data-testid]').forEach(el => {
                    const id = el.getAttribute('data-testid');
                    if (!seen.has(id)) {
                        const cls = (el.className && el.className.baseVal !== undefined)
                            ? el.className.baseVal : (el.className || '');
                        seen.set(id, String(cls).split(' ').filter(Boolean).slice(0, 3).join(' '));
                    }
                });
                return [...seen.entries()].sort();
            }"""
        )
        print(f"共 {len(rows)} 个 testid：")
        for tid, cls in rows:
            print(f"  {tid:34} {cls}")

        # 带 key 的容器是否真的生成了 st-key- 类
        keys = page.evaluate(
            """() => [...document.querySelectorAll('[class*="st-key-"]')]
                    .map(el => el.className.toString().split(' ').find(c => c.startsWith('st-key-'))
                         + '  <' + el.tagName.toLowerCase() + '>')
                    .slice(0, 20)"""
        )
        print("\n带 st-key- 的元素：")
        for k in keys:
            print("  ", k)

        browser.close()


if __name__ == "__main__":
    main()
