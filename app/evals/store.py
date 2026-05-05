# app/evals/store.py
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from app.evals.models import EvalResult

DB_PATH = Path("logs/evals.db")
DB_PATH.parent.mkdir(exist_ok=True)


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evals (
                run_id TEXT PRIMARY KEY,
                workflow_id TEXT,
                quality_score REAL,
                score_breakdown TEXT,
                policy_pass INTEGER,
                regression_flag INTEGER,
                regression_delta REAL,
                timestamp TEXT,
                verdict TEXT
            )
        """)


def save_result(result: EvalResult):
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO evals VALUES (?,?,?,?,?,?,?,?,?)",
            (result.run_id, result.workflow_id, result.quality_score,
             json.dumps(result.score_breakdown), int(result.policy_pass),
             int(result.regression_flag), result.regression_delta,
             result.timestamp.isoformat(), result.verdict)
        )


def get_baseline_score(run_id_prefix: str) -> float | None:
    """Get the average quality score from the last 5 similar runs."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT quality_score FROM evals ORDER BY timestamp DESC LIMIT 5"
        ).fetchall()
    if not rows:
        return None
    return sum(r[0] for r in rows) / len(rows)


def get_recent(limit: int = 20) -> list[dict]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT run_id, quality_score, regression_flag, verdict, timestamp "
            "FROM evals ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [
        {"run_id": r[0], "quality_score": r[1], "regression_flag": bool(r[2]),
         "verdict": r[3], "timestamp": r[4]}
        for r in rows
    ]