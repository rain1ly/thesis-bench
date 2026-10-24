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
    reviewed_at   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_qa_student ON qa(student);
CREATE INDEX IF NOT EXISTS idx_qa_status  ON qa(status);
"""


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

    @property
    def final_answer(self) -> str:
        """导师修订过就用导师的，否则用 AI 草稿。"""
        return self.answer or self.ai_draft

    @property
    def answered(self) -> bool:
        return self.status == "已通过" and bool(self.final_answer)


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
    db_path: str | Path | None = None,
) -> int:
    with session(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO qa (student, stage, question, ai_draft, tags, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (student.strip(), stage, question.strip(), ai_draft, tags, _now()),
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
