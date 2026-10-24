"""预演记录存储 —— 每次作答都留一条，不覆盖。

为什么允许重答、不留唯一约束：
答辩前的改进过程本身就是证据。第一次命中 1/3、第二次 3/3，
这条曲线比「最终得分」更有说服力，也正好是省赛材料里能用的东西。

表依旧扁平：一人一题可以有多条记录，取最新一条看当前状态。
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "rehearsal.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS rehearsal (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student    TEXT NOT NULL,
    topic      TEXT NOT NULL DEFAULT '通用',
    question   TEXT NOT NULL,
    answer     TEXT NOT NULL DEFAULT '',
    hit        INTEGER NOT NULL DEFAULT 0,
    total      INTEGER NOT NULL DEFAULT 0,
    level      TEXT NOT NULL DEFAULT '',
    missing    TEXT NOT NULL DEFAULT '',
    source_ids TEXT NOT NULL DEFAULT '',
    ai_note    TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reh_student ON rehearsal(student);
CREATE INDEX IF NOT EXISTS idx_reh_topic   ON rehearsal(topic);
"""


@dataclass
class Attempt:
    id: int
    student: str
    topic: str
    question: str
    answer: str
    hit: int
    total: int
    level: str
    missing: str
    source_ids: str
    ai_note: str
    created_at: str

    @property
    def ratio(self) -> float:
        return self.hit / self.total if self.total else 0.0

    @property
    def passed(self) -> bool:
        """扎实才算过。基本和有缺口都还要再来一遍。"""
        return self.level == "扎实"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


@contextmanager
def session(db_path: str | Path | None = None):
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


def save(
    student: str,
    question: str,
    answer: str,
    hit: int,
    total: int,
    level: str,
    topic: str = "通用",
    missing: str = "",
    source_ids: str = "",
    ai_note: str = "",
    db_path: str | Path | None = None,
) -> int:
    with session(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO rehearsal (student, topic, question, answer, hit, total, level,"
            " missing, source_ids, ai_note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                student.strip(), topic, question.strip(), answer.strip(),
                hit, total, level, missing, source_ids, ai_note, _now(),
            ),
        )
        return int(cur.lastrowid)


def attach_ai_note(attempt_id: int, note: str, db_path: str | Path | None = None) -> None:
    """AI 追问写到已有记录上。和 AI 起草一样，它只是附加，不改变判分结果。"""
    with session(db_path) as conn:
        conn.execute("UPDATE rehearsal SET ai_note = ? WHERE id = ?", (note, attempt_id))


def list_attempts(
    student: str | None = None,
    topic: str | None = None,
    db_path: str | Path | None = None,
) -> list[Attempt]:
    sql = "SELECT * FROM rehearsal WHERE 1=1"
    args: list[object] = []
    if student:
        sql += " AND student = ?"
        args.append(student)
    if topic:
        sql += " AND topic = ?"
        args.append(topic)
    sql += " ORDER BY id DESC"
    with session(db_path) as conn:
        rows = conn.execute(sql, args).fetchall()
    return [Attempt(**dict(r)) for r in rows]


def latest_by_question(attempts: list[Attempt]) -> dict[str, Attempt]:
    """同一道题答过多次，看最后一次。attempts 已按 id 倒序，先到先得。"""
    out: dict[str, Attempt] = {}
    for a in attempts:
        out.setdefault(a.question, a)
    return out


def stats(student: str | None = None, db_path: str | Path | None = None) -> dict:
    rows = list_attempts(student=student, db_path=db_path)
    latest = latest_by_question(rows)
    total_q = len(latest)
    passed = sum(1 for a in latest.values() if a.passed)
    covered = sum(a.hit for a in latest.values())
    capacity = sum(a.total for a in latest.values())
    return {
        "attempts": len(rows),
        "questions": total_q,
        "passed": passed,
        "open": total_q - passed,
        "points_hit": covered,
        "points_total": capacity,
        "coverage": round(covered / capacity, 3) if capacity else 0.0,
    }


def improvement(student: str, question: str, db_path: str | Path | None = None) -> list[Attempt]:
    """单题的作答轨迹，按时间正序 —— 用来看「改没改好」。"""
    rows = [a for a in list_attempts(student=student, db_path=db_path) if a.question == question]
    return list(reversed(rows))
