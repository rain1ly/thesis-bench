"""答疑记录存储 —— 单文件 SQLite，零外部依赖。

为什么值得单独一层：
1. 答疑要长期沉淀，需要按学生、阶段、状态检索；
2. 导师审核要改状态，需要事务保证不出现「半改」；
3. SQLite 是文件级数据库，评委 clone 下来直接能跑，不用装服务。

表结构刻意保持扁平：这一阶段一个学生名就是字符串，不做用户体系。
等真的要多角色登录了再拆表——现在拆就是给自己挖坑。
"""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "qa.db"

STAGES = ("开题", "中期", "定稿")
STATUSES = ("待审核", "已通过", "已退回")

CATEGORIES = ("论文写作", "数据分析", "代码实现", "系统使用", "格式规范", "其他")
VISIBILITIES = ("公开", "隐私")

SCHEMA = """
CREATE TABLE IF NOT EXISTS qa (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student       TEXT NOT NULL,
    stage         TEXT NOT NULL DEFAULT '开题',
    question      TEXT NOT NULL,
    ai_draft      TEXT NOT NULL DEFAULT '',
    answer        TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT '待审核',
    tags          TEXT NOT NULL DEFAULT '',
    reviewer_note TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    reviewed_at   TEXT NOT NULL DEFAULT '',
    category      TEXT NOT NULL DEFAULT '论文写作',
    visibility    TEXT NOT NULL DEFAULT '公开',
    assigned_to   TEXT NOT NULL DEFAULT '',
    thesis_title  TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_qa_student ON qa(student);
CREATE INDEX IF NOT EXISTS idx_qa_status  ON qa(status);
CREATE TABLE IF NOT EXISTS students (
    name         TEXT PRIMARY KEY,
    thesis_title TEXT NOT NULL DEFAULT '',
    advisor      TEXT NOT NULL DEFAULT '',
    major        TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS teachers (
    name       TEXT PRIMARY KEY,
    title      TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
"""

# 老库补列：加用户体系之前建的 qa 表没有这四列，直接 ALTER 会报错，
# 所以先查 PRAGMA 缺哪补哪。迁移必须幂等 —— 应用每次启动都会走到这里。
MIGRATE_COLUMNS = (
    ("category", "TEXT NOT NULL DEFAULT '论文写作'"),
    ("visibility", "TEXT NOT NULL DEFAULT '公开'"),
    ("assigned_to", "TEXT NOT NULL DEFAULT ''"),
    ("thesis_title", "TEXT NOT NULL DEFAULT ''"),
)


def _migrate(conn: sqlite3.Connection) -> None:
    have = {row["name"] for row in conn.execute("PRAGMA table_info(qa)")}
    for name, ddl in MIGRATE_COLUMNS:
        if name not in have:
            conn.execute(f"ALTER TABLE qa ADD COLUMN {name} {ddl}")


@dataclass
class QARecord:
    id: int
    student: str
    stage: str
    question: str
    ai_draft: str
    answer: str
    status: str
    tags: str
    reviewer_note: str
    created_at: str
    reviewed_at: str
    category: str = "论文写作"
    visibility: str = "公开"
    assigned_to: str = ""
    thesis_title: str = ""

    @property
    def final_answer(self) -> str:
        """导师修订过就用导师的，否则用 AI 草稿。"""
        return self.answer or self.ai_draft

    @property
    def answered(self) -> bool:
        return self.status == "已通过" and bool(self.final_answer)

    @property
    def is_private(self) -> bool:
        return self.visibility == "隐私"

    @property
    def audience(self) -> str:
        """给界面看的一句话：这条问题归谁管。"""
        if self.assigned_to:
            return f"指定 {self.assigned_to}"
        return "公开池（任何老师可接）"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


@contextmanager
def session(db_path: str | Path | None = None):
    """统一处理建表、提交、关闭，避免每处都写 try/finally。"""
    path = Path(db_path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        _migrate(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def add_question(
    student: str,
    question: str,
    stage: str = "开题",
    ai_draft: str = "",
    tags: str = "",
    category: str = "论文写作",
    visibility: str = "公开",
    assigned_to: str = "",
    thesis_title: str = "",
    db_path: str | Path | None = None,
) -> int:
    if visibility not in VISIBILITIES:
        raise ValueError(f"未知可见性：{visibility}")
    if category not in CATEGORIES:
        raise ValueError(f"未知分类：{category}")
    with session(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO qa (student, stage, question, ai_draft, tags, category,"
            " visibility, assigned_to, thesis_title, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                student.strip(),
                stage,
                question.strip(),
                ai_draft,
                tags,
                category,
                visibility,
                assigned_to.strip(),
                thesis_title.strip(),
                _now(),
            ),
        )
        return int(cur.lastrowid)


def review(
    record_id: int,
    status: str,
    answer: str = "",
    note: str = "",
    db_path: str | Path | None = None,
) -> None:
    if status not in STATUSES:
        raise ValueError(f"未知状态：{status}")
    with session(db_path) as conn:
        conn.execute(
            "UPDATE qa SET status = ?, answer = ?, reviewer_note = ?, reviewed_at = ? WHERE id = ?",
            (status, answer, note, _now(), record_id),
        )


def list_records(
    student: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    category: str | None = None,
    visibility: str | None = None,
    assigned_to: str | None = None,
    db_path: str | Path | None = None,
) -> list[QARecord]:
    sql = "SELECT * FROM qa WHERE 1=1"
    args: list[object] = []
    if student:
        sql += " AND student = ?"
        args.append(student)
    if status:
        sql += " AND status = ?"
        args.append(status)
    if category:
        sql += " AND category = ?"
        args.append(category)
    if visibility:
        sql += " AND visibility = ?"
        args.append(visibility)
    if assigned_to:
        sql += " AND assigned_to = ?"
        args.append(assigned_to)
    if keyword:
        sql += " AND (question LIKE ? OR answer LIKE ? OR ai_draft LIKE ? OR tags LIKE ?)"
        args.extend([f"%{keyword}%"] * 4)
    sql += " ORDER BY id DESC"
    with session(db_path) as conn:
        rows = conn.execute(sql, args).fetchall()
    return [QARecord(**dict(r)) for r in rows]


def students(db_path: str | Path | None = None) -> list[str]:
    with session(db_path) as conn:
        rows = conn.execute("SELECT DISTINCT student FROM qa ORDER BY student").fetchall()
    return [r["student"] for r in rows]


def stats(db_path: str | Path | None = None) -> dict:
    with session(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM qa").fetchone()["c"]
        rows = conn.execute("SELECT status, COUNT(*) AS c FROM qa GROUP BY status").fetchall()
        n_students = conn.execute("SELECT COUNT(DISTINCT student) AS c FROM qa").fetchone()["c"]
    by_status = {r["status"]: r["c"] for r in rows}
    return {
        "total": total,
        "students": n_students,
        "待审核": by_status.get("待审核", 0),
        "已通过": by_status.get("已通过", 0),
        "已退回": by_status.get("已退回", 0),
    }


# ---------------------------------------------------------------- 学生与教师档案
def upsert_student(
    name: str,
    thesis_title: str = "",
    advisor: str = "",
    major: str = "",
    db_path: str | Path | None = None,
) -> None:
    """学生档案。论文题目和指导老师是导师反馈里第一条要补的东西。

    没有它，「老师那边看不到论文题目」；也没有它，预演台在学生
    只问过一句格式问题时无题可出。
    """
    with session(db_path) as conn:
        conn.execute(
            "INSERT INTO students (name, thesis_title, advisor, major, created_at)"
            " VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(name) DO UPDATE SET thesis_title = excluded.thesis_title,"
            " advisor = excluded.advisor, major = excluded.major",
            (name.strip(), thesis_title.strip(), advisor.strip(), major.strip(), _now()),
        )


def get_student(name: str, db_path: str | Path | None = None) -> dict:
    with session(db_path) as conn:
        row = conn.execute("SELECT * FROM students WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else {}


def all_students(db_path: str | Path | None = None) -> list[dict]:
    """学生档案，按指导老师、姓名排。没建档的学生不在这个列表里 —— 用 names() 兜底。"""
    with session(db_path) as conn:
        rows = conn.execute("SELECT * FROM students ORDER BY advisor, name").fetchall()
    return [dict(r) for r in rows]


def thesis_of(name: str, db_path: str | Path | None = None) -> str:
    return get_student(name, db_path).get("thesis_title", "")


def upsert_teacher(name: str, title: str = "", db_path: str | Path | None = None) -> None:
    with session(db_path) as conn:
        conn.execute(
            "INSERT INTO teachers (name, title, created_at) VALUES (?, ?, ?)"
            " ON CONFLICT(name) DO UPDATE SET title = excluded.title",
            (name.strip(), title.strip(), _now()),
        )


def all_teachers(db_path: str | Path | None = None) -> list[dict]:
    with session(db_path) as conn:
        rows = conn.execute("SELECT * FROM teachers ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def teacher_names(db_path: str | Path | None = None) -> list[str]:
    return [t["name"] for t in all_teachers(db_path)]


def student_names(db_path: str | Path | None = None) -> list[str]:
    """档案里有的 + 只在答疑记录里出现过的，合并去重。

    先有记录后建档是常态（学生先提问，档案后补），
    只读 students 表会漏人。
    """
    seen: list[str] = []
    for row in all_students(db_path):
        seen.append(row["name"])
    for name in students(db_path):
        if name not in seen:
            seen.append(name)
    return seen


# ---------------------------------------------------------------- 元信息与清空
def set_meta(key: str, value: str, db_path: str | Path | None = None) -> None:
    """键值表，只存「这份库是什么」这类事实，不当业务数据用。

    目前只有一个键：demo=1，表示库里是示例数据而不是真实学生记录。
    分不清真假数据，演示时就没法诚实地标注来源。
    """
    with session(db_path) as conn:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_meta(key: str, default: str = "", db_path: str | Path | None = None) -> str:
    with session(db_path) as conn:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def clear_all(db_path: str | Path | None = None) -> int:
    """删空答疑表，返回删除条数。

    这里不加保护条件 —— 判断「能不能删」是业务层的事（见 core.bootstrap），
    存储层只负责把事做干净，别在这里藏规则。
    """
    with session(db_path) as conn:
        n = conn.execute("SELECT COUNT(*) AS c FROM qa").fetchone()["c"]
        conn.execute("DELETE FROM qa")
        conn.execute("DELETE FROM meta")
        return int(n)


# ---------------------------------------------------------------- 重复问题检测
def _bigrams(text: str) -> set[str]:
    t = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", text or "")
    return {t[i : i + 2] for i in range(len(t) - 1)}


def find_similar(
    question: str,
    records: list[QARecord],
    threshold: float = 0.3,
    limit: int = 3,
) -> list[tuple[float, QARecord]]:
    """找出历史上问过的近似问题。

    用字符 bigram 的**重叠系数**（交集 / 较短集合大小），不用 Jaccard：
    学生追问时往往只说半句「那数据量不够怎么办」，
    长度差一大截，Jaccard 会被稀释到很低，重叠系数还能认出来。

    这个检测不需要模型 —— 导师最想要的第一件事就是
    「这个问题我答过」，而判断"答过没"本来就该是确定性的。
    """
    target = _bigrams(question)
    if not target:
        return []

    hits: list[tuple[float, QARecord]] = []
    for r in records:
        other = _bigrams(r.question)
        if not other:
            continue
        score = len(target & other) / min(len(target), len(other))
        if score >= threshold:
            hits.append((score, r))

    hits.sort(key=lambda x: -x[0])
    return hits[:limit]
