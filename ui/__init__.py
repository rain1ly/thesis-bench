"""ui —— 表现层。

    ui.theme       设计 token + 全站 CSS（唯一允许出现颜色和字号的地方）
    ui.components  可复用组件（页头 / KPI / 徽章 / 章节 / 空状态）

纪律：页面里不写内联颜色和像素值。要改视觉，只改 ui/theme.py。
"""

from __future__ import annotations

__all__ = ["theme", "components"]
