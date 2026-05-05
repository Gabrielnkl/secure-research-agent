# app/security/approvals.py
import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path("logs/approvals.db")
DB_PATH.parent.mkdir(exist_ok=True)


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS approvals (
                workflow_id TEXT PRIMARY KEY,
                run_id TEXT,
                synthesis_summary TEXT,
                status TEXT DEFAULT 'pending',
                note TEXT,
                created_at TEXT,
                resolved_at TEXT
            )
        """)


def request_approval(workflow_id: str, run_id: str, synthesis_summary: str):
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO approvals VALUES (?,?,?,?,?,?,?)",
            (workflow_id, run_id, synthesis_summary[:500],
             "pending", None, datetime.utcnow().isoformat(), None)
        )


def resolve_approval(workflow_id: str, verdict: bool, note: str):
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE approvals SET status=?, note=?, resolved_at=? WHERE workflow_id=?",
            ("approved" if verdict else "rejected", note,
             datetime.utcnow().isoformat(), workflow_id)
        )


def get_pending():
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT workflow_id, run_id, synthesis_summary, created_at "
            "FROM approvals WHERE status='pending' ORDER BY created_at DESC"
        ).fetchall()
    return [
        {"workflow_id": r[0], "run_id": r[1], "summary": r[2], "created_at": r[3]}
        for r in rows
    ]