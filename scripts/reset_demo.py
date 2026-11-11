"""录制前重置示例数据 —— 回到 30 条干净的初始状态。

为什么需要这个脚本
------------------
录像要求「同一句话第一次问，提示相似 62%」。
但一旦有人用同一句话试过提交，库里就有了完全相同的记录，
再问就是「问过 2 次，相似 100%」——画面对不上，得重录。

手动删文件有两个坑：一是要记得 qa.db 和 rehearsal.db 两个都删，
二是路径记错会删到别的地方。所以做成脚本，只认自己算出来的路径。

用法
----
    python scripts/reset_demo.py          # 只查看当前状态，不动数据
    python scripts/reset_demo.py --yes    # 真的重置
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import bootstrap, qa_seed, qa_store, rehearsal_store  # noqa: E402

QA_DB = qa_store.DB_PATH
REH_DB = rehearsal_store.DB_PATH


def snapshot() -> tuple[int, int, list[tuple[str, int]]]:
    """当前库里有多少东西。用只读方式打开，避免顺手触发迁移。"""
    def count(path: Path, table: str) -> int:
        if not path.exists():
            return -1
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                return conn.execute(f"select count(*) from {table}").fetchone()[0]
            finally:
                conn.close()
        except sqlite3.Error:
            return -1

    n_qa = count(Path(QA_DB), "qa")
    n_reh = count(Path(REH_DB), "rehearsal")

    per_student: list[tuple[str, int]] = []
    if Path(QA_DB).exists():
        try:
            conn = sqlite3.connect(f"file:{QA_DB}?mode=ro", uri=True)
            try:
                per_student = conn.execute(
                    "select student, count(*) from qa group by student order by count(*) desc"
                ).fetchall()
            finally:
                conn.close()
        except sqlite3.Error:
            pass
    return n_qa, n_reh, per_student


def main() -> int:
    ap = argparse.ArgumentParser(description="重置示例数据到 30 条干净状态")
    ap.add_argument("--yes", action="store_true", help="真的执行（不加只查看）")
    args = ap.parse_args()

    n_qa, n_reh, per_student = snapshot()

    print("=" * 54)
    print("当前状态")
    print("=" * 54)
    print(f"  答疑数据库　{QA_DB}")
    print(f"    记录数　　{n_qa if n_qa >= 0 else '不存在'}")
    print(f"  预演数据库　{REH_DB}")
    print(f"    作答数　　{n_reh if n_reh >= 0 else '不存在'}")
    if per_student:
        print("  按学生分布：")
        for name, n in per_student:
            print(f"    {name}　{n} 条")
    print()

    # 目标状态：陈同学 15 条（这是录像脚本里引用的数字）
    clean = n_qa == 15 and n_reh <= 0
    if clean:
        print("已经是干净状态（陈同学 15 条、无预演记录），不用重置。")
        return 0

    if not args.yes:
        print("要重置就加参数再跑一次：")
        print("  python scripts/reset_demo.py --yes")
        print()
        print("会删掉上面这两个库文件，然后重新写入 30 条示例数据。")
        print("预演记录、试录留下的问答，全部清空 —— 这些本来就是用来试的。")
        return 0

    # 删之前先备份，删错了还能捞回来
    for path in (Path(QA_DB), Path(REH_DB)):
        if path.exists():
            bak = path.with_suffix(path.suffix + ".bak")
            if bak.exists():
                bak.unlink()
            path.rename(bak)
            print(f"已备份 {path.name} → {bak.name}")

    n = qa_seed.load_seed()
    bootstrap.ensure_demo()
    n_qa2, n_reh2, per2 = snapshot()

    print()
    print("=" * 54)
    print("重置完成")
    print("=" * 54)
    print(f"  写入示例数据　{n} 条")
    print(f"  答疑记录　　　{n_qa2} 条")
    print(f"  预演记录　　　{max(n_reh2, 0)} 条")
    if per2:
        print("  按学生分布：")
        for name, m in per2:
            print(f"    {name}　{m} 条")
    print()
    print("下一步：埋钩子 —— 预演台第 1 题答「数据来自公开数据集，但和我的传感器对不上。」")
    print("得到 1/3 后关掉页面，再开始录。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
