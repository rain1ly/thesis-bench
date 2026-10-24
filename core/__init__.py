"""core —— 业务内核

分层约定：
    core.schemas          数据结构，不含逻辑
    core.parser           文档 → 章节树 + 元信息
    core.checker          ② 规则检查，确定性，不调模型
    core.qa_store         ① 答疑存储 + 重复问题检测
    core.qa_seed          模拟答疑数据（冷启动）
    core.rehearsal        ③ 风险画像 + 题库 + 出题 + 要点覆盖判分，纯确定性
    core.rehearsal_store  ③ 预演记录存储
    core.ai_client        模型封装，唯一允许出现 API 调用的地方

依赖方向：pages / app → core，core 内部不反向依赖界面。

一条纪律：**规则先于模型。** 能确定性判断的（引用对不对、章节平不平衡、
要点提没提到、风险该不该排序）一律写纯函数，不调 API。
理由不是省钱，是可复现——评委当场换一个学生，结果必须一样，不能看运气。
模型只在"必须理解语义"的地方出场：起草答复、生成追问。
"""
