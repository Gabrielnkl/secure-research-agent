# app/api/main.py
import json
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from temporalio.client import Client

from app.evals.store import get_recent
from app.security.approvals import get_pending

app = FastAPI(title="Research Agent Dashboard")
_temporal: Client | None = None


async def get_client():
    global _temporal
    if not _temporal:
        _temporal = await Client.connect("localhost:7233")
    return _temporal


def read_events(limit: int = 200) -> list[dict]:
    path = Path("logs/events.jsonl")
    if not path.exists():
        return []
    lines = path.read_text().strip().split("\n")
    events = [json.loads(l) for l in lines if l]
    return events[-limit:]


@app.get("/")
async def dashboard():
    return HTMLResponse(Path("app/api/dashboard.html").read_text())


@app.get("/api/stats")
async def stats():
    events = read_events()
    evals = get_recent(100)
    total_cost = sum(e.get("cost_usd", 0) for e in events)
    avg_latency = (
        sum(e.get("latency_ms", 0) for e in events) / len(events) if events else 0
    )
    pass_rate = (
        sum(1 for e in evals if e["verdict"] == "pass") / len(evals) if evals else 0
    )
    return {
        "total_runs": len(set(e.get("step", "") for e in events)),
        "total_cost_usd": round(total_cost, 4),
        "avg_latency_ms": round(avg_latency),
        "eval_pass_rate": round(pass_rate, 2),
        "total_events": len(events),
    }


@app.get("/api/events")
async def events():
    return read_events(100)


@app.get("/api/evals")
async def evals():
    return get_recent(20)


@app.get("/api/approvals/pending")
async def pending_approvals():
    return get_pending()


class ApprovalRequest(BaseModel):
    verdict: bool
    note: str = ""


@app.post("/api/approve/{workflow_id}")
async def approve(workflow_id: str, body: ApprovalRequest):
    client = await get_client()
    try:
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal("approve", body.verdict, body.note)
        from app.security.approvals import resolve_approval
        resolve_approval(workflow_id, body.verdict, body.note)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))