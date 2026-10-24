"""预演台内核 —— 把「学生问过什么」变成「答辩会被问什么」。

这一层是本项目唯一复制不走的东西：
维普手里有论文，我们有学生的困惑史。论文看不出谁虚，提问记录看得出来。

整条链路都不调模型，换个人当场也能跑出题单：

    答疑记录  →  主题风险画像  →  题单  →  要点覆盖判分
    （语料）      （确定性公式）    （固定题库）  （关键词下限）

三个判断，写在这里免得以后自己都忘了为什么这么做：

1. **风险靠频次、跨阶段、有没有人答**，不靠语义相似。
   一个主题在开题、中期、定稿都被问，说明它不是「问一下」，是「一直没解决」。
   这个信号比任何 embedding 都直白，而且可解释——导师看一眼就认。

2. **判分只报「命中几个要点」，不给百分制。**
   给个 78 分是假的精确，学生只会盯着分数。告诉他「你漏了『数据局限』这一条」，
   他才知道下一版改哪。

3. **关键词匹配是保守下限，不是真理。**
   换一种说法就漏判，所以界面必须写明「表述不同可能漏判，导师可手动修正」。
   诚实的边界比虚假的全面值钱。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from core.qa_store import QARecord

# ------------------------------------------------------------------ 数据结构


@dataclass(frozen=True)
class KeyPoint:
    """一个答案要点：叫什么，以及学生说到哪些词就算碰到了。"""

    name: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class Question:
    topic: str
    text: str
    points: tuple[KeyPoint, ...]
    follow_up: str
    why: str

    @property
    def total(self) -> int:
        return len(self.points)


@dataclass(frozen=True)
class TopicRisk:
    """一个主题的风险画像。record_ids 保留溯源，题单要能点回原问题。"""

    topic: str
    count: int
    stages: tuple[str, ...]
    unanswered: int
    score: float
    level: str
    latest_question: str
    record_ids: tuple[int, ...]

    @property
    def spread(self) -> int:
        return len(self.stages)


@dataclass(frozen=True)
class PlannedQuestion:
    """题单里的一道题 —— 题本身 + 为什么挑它。"""

    question: Question
    risk: TopicRisk | None
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def source_ids(self) -> str:
        return ",".join(str(i) for i in (self.risk.record_ids if self.risk else ()))

    @property
    def priority(self) -> str:
        return self.risk.level if self.risk else "必答"


@dataclass(frozen=True)
class Grade:
    hit: int
    total: int
    missing: tuple[str, ...]
    level: str

    @property
    def ratio(self) -> float:
        return self.hit / self.total if self.total else 0.0


# ------------------------------------------------------------------ 题库
# 标签与 core.qa_seed 里的 tags 对齐；换选题时只需换这一张表。
# 每题都带 follow_up（追问）和 why（评委为什么问）——
# 学生怕的不是问题本身，是不知道对方在探什么。

BANK: dict[str, tuple[Question, ...]] = {
    "数据来源": (
        Question(
            topic="数据来源",
            text="你论文里用的数据是从哪来的？如果能重来一次，你会换一套数据吗？",
            points=(
                KeyPoint("来源交代到可核查", ("公开数据集", "自采", "实测", "采集", "开源", "UCI", "实验室数据", "数据来源")),
                KeyPoint("说清数据边界", ("局限", "不足", "不适用", "边界", "覆盖范围", "场景限制")),
                KeyPoint("对不齐怎么处理", ("映射", "对齐", "量纲", "单位", "字段", "换算", "剔除")),
            ),
            follow_up="你说的这套数据，适合回答你的研究问题吗？不适合的地方在哪？",
            why="评委看数据只看两件事：够不够支撑结论、有没有偷偷换过的痕迹。",
        ),
        Question(
            topic="数据来源",
            text="样本量为什么是这个数？换成一半，你的结论会变吗？",
            points=(
                KeyPoint("样本量有依据", ("经验法则", "5倍", "10倍", "公式", "置信", "检验", "参考", "标准")),
                KeyPoint("和模型复杂度匹配", ("自变量", "变量个数", "交叉验证", "简单线性", "复杂度", "降维")),
                KeyPoint("结论稳定性", ("稳定", "波动", "稳健", "重复", "区间", "再跑")),
            ),
            follow_up="如果只能加 50 条数据，你会加在哪个类别上？",
            why="问样本量其实是在问：你知不知道自己结论的置信边界在哪。",
        ),
    ),
    "数据处理": (
        Question(
            topic="数据处理",
            text="你的数据预处理做了哪几步？每一步为什么这么做？",
            points=(
                KeyPoint("缺失值处理", ("缺失", "填补", "插值", "删除", "均值填充")),
                KeyPoint("异常值判据", ("异常", "离群", "3σ", "箱线", "阈值", "剔除")),
                KeyPoint("归一化方式", ("归一化", "标准化", "缩放", "区间", "min-max", "z-score")),
            ),
            follow_up="异常值你是怎么判定为『异常』的？判据有没有反过来被数据影响？",
            why="预处理写不清，等于告诉评委结果不可复现。",
        ),
    ),
    "图表规范": (
        Question(
            topic="图表规范",
            text="你论文里最希望评委看的是哪张图？它想说明什么？",
            points=(
                KeyPoint("指向具体图表", ("图", "表", "第", "章")),
                KeyPoint("说得出结论", ("说明", "表明", "看出", "趋势", "对比", "关系", "优于")),
                KeyPoint("有数据支撑", ("数据", "样本", "实验", "结果")),
            ),
            follow_up="这张图如果删掉，你的结论会缺哪一块？",
            why="指不出重点图表，通常意味着自己也没想清哪张是核心证据。",
        ),
        Question(
            topic="图表规范",
            text="图注位置、坐标轴单位、图例，这三样你全文统一了吗？",
            points=(
                KeyPoint("图注位置有规矩", ("图注", "下方", "上方", "国标")),
                KeyPoint("单位标了", ("单位", "量纲", "坐标轴", "刻度")),
                KeyPoint("全文一致", ("统一", "一致", "全文", "规范")),
            ),
            follow_up="如果发现有一张图的单位和正文对不上，你打算怎么处理？",
            why="这类问题不致命，但评委一问，你就显得没通读过自己的稿子。",
        ),
    ),
    "实验设计": (
        Question(
            topic="实验设计",
            text="你的对比实验选了什么 baseline？为什么是它们，不是别的？",
            points=(
                KeyPoint("经典与近期各一个", ("经典", "baseline", "最新", "近年", "SOTA", "state-of-the-art")),
                KeyPoint("说明选择理由", ("理由", "代表", "可比", "同任务", "因为")),
                KeyPoint("数据和设置一致", ("同一数据集", "相同设置", "统一", "公开")),
            ),
            follow_up="你选的这个 baseline，有没有可能被评委认为『故意选弱的』？",
            why="baseline 选弱是最常见的质疑，也是导师最容易替你辩护的一条。",
        ),
        Question(
            topic="实验设计",
            text="如果去掉你方法里的某个模块，效果会掉多少？",
            points=(
                KeyPoint("做过消融", ("消融", "ablation", "单独", "去掉", "拆开")),
                KeyPoint("给得出数量", ("百分点", "下降", "提升", "%", "准确率")),
                KeyPoint("解释为什么掉", ("因为", "负责", "贡献", "作用", "机制")),
            ),
            follow_up="掉得最多的那个模块，是不是也可以说是你最大的不确定性？",
            why="消融是判断「这个改进是真的还是碰巧」的标准动作，没做会很被动。",
        ),
    ),
    "问卷方法": (
        Question(
            topic="问卷方法",
            text="你的问卷回收了多少份？信度和效度是怎么验的？",
            points=(
                KeyPoint("样本量有依据", ("题项", "5倍", "10倍", "有效样本", "回收")),
                KeyPoint("信度有指标", ("Cronbach", "α", "信度", "0.7", "alpha")),
                KeyPoint("效度有检验", ("KMO", "Bartlett", "效度", "因子")),
            ),
            follow_up="回收率多少？没回的那部分人和回了的人，可能有系统性差别吗？",
            why="问卷类论文最容易被问倒的就是「你凭什么叫它代表性样本」。",
        ),
    ),
    "文献规范": (
        Question(
            topic="文献规范",
            text="你列了这些参考文献，哪几篇真正改变了你的方法？",
            points=(
                KeyPoint("点得出具体篇目", ("第", "篇", "作者", "文献")),
                KeyPoint("说得出影响在哪", ("借鉴", "采用", "改进", "基于", "思路")),
                KeyPoint("和本文的差异", ("不同", "区别", "本文", "改进", "补充")),
            ),
            follow_up="有没有哪篇文献，你列了但其实没读完？",
            why="「只列不引、引了没读」是答辩现场翻车率最高的地方。",
        ),
    ),
    "结构安排": (
        Question(
            topic="结构安排",
            text="你的第三章和第四章，各自解决什么问题？一句话说清。",
            points=(
                KeyPoint("说清章节功能", ("设计", "实现", "方法", "实验", "分析", "需求")),
                KeyPoint("两章有区分", ("区别", "不同", "前者", "后者", "一个是")),
                KeyPoint("有承接关系", ("因此", "支撑", "承接", "为", "引出")),
            ),
            follow_up="如果第四章拿掉，第三章还成立吗？",
            why="问章节分工，实际在试探你知不知道各章之间的因果，而不是目录顺序。",
        ),
    ),
    "技术选型": (
        Question(
            topic="技术选型",
            text="为什么选这个技术栈？换成另一个方案会怎样？",
            points=(
                KeyPoint("约束条件", ("成本", "功耗", "部署", "时间", "数据量", "算力")),
                KeyPoint("考虑过替代方案", ("替代", "换成", "对比", "另一个", "备选")),
                KeyPoint("说得出取舍", ("取舍", "权衡", "牺牲", "折中", "代价")),
            ),
            follow_up="你放弃的那个方案，具体输在哪一条约束上？",
            why="技术选型问不出对错，只能问出你有没有真的比较过。",
        ),
    ),
    "测试": (
        Question(
            topic="测试",
            text="你怎么证明你的系统是对的？测了哪些，漏了哪些？",
            points=(
                KeyPoint("用例有设计", ("用例", "输入", "预期", "边界")),
                KeyPoint("覆盖了主要功能", ("模块", "功能", "覆盖", "场景")),
                KeyPoint("承认没测到的", ("未测", "没测", "局限", "极端", "并发", "压力")),
            ),
            follow_up="如果同时有 100 个人点这个按钮，你系统会怎么坏？",
            why="敢说「哪块没测」的人，比说「全测过了」的人可信得多。",
        ),
    ),
    "写作": (
        Question(
            topic="写作",
            text="这篇论文如果只留一句话，你希望评委记住什么？",
            points=(
                KeyPoint("说得出核心工作", ("提出", "设计", "实现", "改进", "验证", "构建")),
                KeyPoint("说得出具体场景或指标", ("具体", "指标", "场景", "数据", "准确率", "效率")),
                KeyPoint("说得出价值", ("解决", "价值", "意义", "问题")),
            ),
            follow_up="这句话和摘要第一句是同一句吗？不是的话，哪句是真的？",
            why="连自己论文的一句话结论都说不出来，说明还没写完，只是写完了字数。",
        ),
    ),
    "选题范围": (
        Question(
            topic="选题范围",
            text="这个题目是不是太大了？你怎么证明它在本科阶段做得完？",
            points=(
                KeyPoint("主动收窄过", ("收窄", "范围", "只做", "聚焦", "限定", "感知层")),
                KeyPoint("划了范围外", ("不在本文", "不涉及", "后续", "范围外")),
                KeyPoint("工作量可交付", ("工作量", "可行", "时间", "毕业设计", "完成")),
            ),
            follow_up="你划到范围外的那部分，评委如果偏要问呢？",
            why="题目太大不扣分，说不清边界才扣分。",
        ),
    ),
    "查重": (
        Question(
            topic="查重",
            text="查重率多少？重复集中在哪几段，你改了没有？",
            points=(
                KeyPoint("有具体数值", ("%", "查重", "重复率", "18", "20", "25")),
                KeyPoint("知道重复位置", ("段", "章", "集中", "标红", "连续")),
                KeyPoint("有改法", ("改写", "重写", "调整", "引用格式", "降重")),
            ),
            follow_up="你改的那几处，改完之后意思还准吗？",
            why="查重率是硬指标，但评委更在意你有没有为了降重把话说变形。",
        ),
    ),
    "答辩准备": (
        Question(
            topic="答辩准备",
            text="给你 8 分钟，你打算怎么讲？",
            points=(
                KeyPoint("有讲的框架", ("背景", "问题", "方案", "结果", "不足")),
                KeyPoint("控得住时间", ("分钟", "页", "控制", "留", "时间")),
                KeyPoint("知道讲哪里重点", ("重点", "突出", "核心", "多讲")),
            ),
            follow_up="如果评委在第 3 分钟就打断你问结果，你怎么接？",
            why="答辩不是念稿，是有限时间里的信息取舍。",
        ),
    ),
    "格式": (
        Question(
            topic="格式",
            text="格式这块，你对照学校模板逐条核过了吗？",
            points=(
                KeyPoint("以模板为准", ("模板", "学校", "规范", "格式")),
                KeyPoint("逐条核对过", ("对照", "核对", "逐条", "检查")),
                KeyPoint("知道遗留问题", ("还有", "没改", "待改", "已修")),
            ),
            follow_up="模板和国标冲突的那几处，你按哪个走的？",
            why="格式是纯执行问题，答不上来说明连模板都没打开过。",
        ),
    ),
}

# 每个答辩都会问的三道题。与主题无关，所以永远排在最后兜底。
ESSENTIALS: tuple[Question, ...] = (
    Question(
        topic="通用",
        text="用三句话说清：你做了什么、为什么这么做、结果怎么样。",
        points=(
            KeyPoint("做了什么", ("设计", "实现", "构建", "做", "搭建")),
            KeyPoint("为什么做", ("因为", "针对", "为了解决", "需求", "痛点")),
            KeyPoint("结果怎么样", ("结果", "效果", "达到", "提升", "准确率", "验证")),
        ),
        follow_up="第三句里那个结果，有具体数字吗？",
        why="每个答辩的第一个问题都是它。这个答不利索，后面全被动。",
    ),
    Question(
        topic="通用",
        text="你的创新点是什么？和已有工作比，具体差在哪一步？",
        points=(
            KeyPoint("说得出创新", ("创新", "改进", "提出", "首次", "不同")),
            KeyPoint("对照过已有工作", ("已有", "现有", "传统", "对比", "文献")),
            KeyPoint("差异具体到一步", ("具体", "这一步", "模块", "指标", "场景")),
        ),
        follow_up="如果评委说这只是工程组合、不算创新，你怎么答？",
        why="本科论文被问创新是常态，答「我的创新是用了新技术」会被追着打。",
    ),
    Question(
        topic="通用",
        text="这篇论文最大的不足是什么？",
        points=(
            KeyPoint("承认具体不足", ("不足", "局限", "没做", "受限于")),
            KeyPoint("说清原因", ("因为", "时间", "数据", "条件", "客观")),
            KeyPoint("有后续方向", ("后续", "将来", "如果", "改进", "下一步")),
        ),
        follow_up="这个不足，是你来不及做，还是做不到？",
        why="评委常用来试探你是不是真懂自己的活。说「没有不足」是最差的答案。",
    ),
)


# ------------------------------------------------------------------ 风险画像

HIGH, MID = 5.0, 3.0


def _score(count: int, spread: int, unanswered: int) -> float:
    """频次打底，跨阶段和没人答各有加成。

    权重是拍出来的，但方向有依据：
    - 频次 1.0 / 次：问得多就是卡得久
    - 跨阶段 1.5 / 个：从开题问到定稿，说明中间几次答复没真正解决
    - 未答复 1.2 / 条：没人答的，答辩时必然裸奔
    """
    return round(count * 1.0 + max(spread - 1, 0) * 1.5 + unanswered * 1.2, 1)


def _level(score: float) -> str:
    if score >= HIGH:
        return "高"
    if score >= MID:
        return "中"
    return "低"


def build_profile(records: list[QARecord]) -> list[TopicRisk]:
    """按标签汇总，风险高的排前面。

    没打标签的记录归到「未分类」，不让它凭空消失——
    漏掉的数据比排错的更麻烦。
    """
    buckets: dict[str, list[QARecord]] = defaultdict(list)
    for r in records:
        topic = (r.tags or "").split("、")[0].strip() or "未分类"
        buckets[topic].append(r)

    out: list[TopicRisk] = []
    for topic, rs in buckets.items():
        stages = tuple(sorted({r.stage for r in rs}, key=lambda s: ("开题", "中期", "定稿").index(s) if s in ("开题", "中期", "定稿") else 9))
        unanswered = sum(1 for r in rs if not r.final_answer)
        s = _score(len(rs), len(stages), unanswered)
        out.append(
            TopicRisk(
                topic=topic,
                count=len(rs),
                stages=stages,
                unanswered=unanswered,
                score=s,
                level=_level(s),
                latest_question=rs[0].question if rs else "",
                record_ids=tuple(r.id for r in rs),
            )
        )

    out.sort(key=lambda t: (-t.score, -t.count, t.topic))
    return out


def _reasons(risk: TopicRisk) -> tuple[str, ...]:
    """给每道题配一句「为什么问你这条」，学生看到才服气。"""
    rs = [f"该主题被问到 {risk.count} 次"]
    if risk.spread > 1:
        rs.append(f"横跨{'、'.join(risk.stages)} {risk.spread} 个阶段，属于反复卡点")
    if risk.unanswered:
        rs.append(f"其中 {risk.unanswered} 条至今没有答复，答辩前必须自己先想清楚")
    return tuple(rs)


def _pick(topic: str) -> tuple[Question, ...]:
    return BANK.get(topic, ())


def student_risk(records: list[QARecord]) -> list[tuple[str, float]]:
    """按「最该练」排序，而不按姓名字典序。

    预演台默认打开第一个学生。如果按拼音/编码排，最该练的那个可能排在最后，
    演示给评委看的第一屏就会落在风险最低的人身上 —— 那不是巧合问题，是排序错了。
    排序键取该生最高主题的风险分，同分再按提问条数。
    """
    per: dict[str, list[QARecord]] = defaultdict(list)
    for r in records:
        per[r.student].append(r)

    out = []
    for name, rs in per.items():
        profile = build_profile(rs)
        top = profile[0].score if profile else 0.0
        out.append((name, top, len(rs)))

    out.sort(key=lambda t: (-t[1], -t[2], t[0]))
    return [(name, score) for name, score, _n in out]


def draft(records: list[QARecord], limit: int = 6) -> list[PlannedQuestion]:
    """按风险出题单。

    规则：一个主题最多出 2 道（同一主题连问三道意义不大，还挤掉别的考点），
    高风险主题先出完再轮下一个，凑不满就用「通用必答题」补齐。
    任何主题在题库里没有对应题时跳过，不硬凑——硬凑出来的题学生会看出来。
    """
    plan: list[PlannedQuestion] = []
    if limit <= 0:
        return plan

    for risk in build_profile(records):
        pool = _pick(risk.topic)
        if not pool:
            continue
        for q in pool[:2]:
            if len(plan) >= limit:
                return plan
            plan.append(PlannedQuestion(question=q, risk=risk, reasons=_reasons(risk)))

    for q in ESSENTIALS:
        if len(plan) >= limit:
            break
        plan.append(PlannedQuestion(question=q, risk=None, reasons=("每个答辩都会问",)))

    return plan


# ------------------------------------------------------------------ 判分


def grade(answer: str, question: Question) -> Grade:
    """只算要点覆盖，不给分数。

    空答直接标「未作答」，不算 0 分——「没答」和「答错」是两回事，
    混在一起会让学生误以为已经在准备了。
    """
    text = (answer or "").strip().lower()
    if not text:
        return Grade(hit=0, total=question.total, missing=tuple(p.name for p in question.points), level="未作答")

    missing: list[str] = []
    hit = 0
    for p in question.points:
        if any(k.lower() in text for k in p.keywords):
            hit += 1
        else:
            missing.append(p.name)

    ratio = hit / question.total if question.total else 0.0
    if ratio >= 0.8:
        level = "扎实"
    elif ratio >= 0.5:
        level = "基本"
    else:
        level = "有缺口"

    return Grade(hit=hit, total=question.total, missing=tuple(missing), level=level)
