"""core —— 业务内核

分层约定：
    core.schemas   数据结构，不含逻辑
    core.parser    文档 → 章节树 + 元信息
    core.checker   规则检查，确定性，不调模型
    core.semantic  （后续）语义检查，调模型，必须经过 Pydantic 校验
    core.db        （后续）本地存储

依赖方向：pages / app → core，core 内部不反向依赖界面。
"""
