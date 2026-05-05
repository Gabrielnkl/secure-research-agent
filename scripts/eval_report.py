# scripts/eval_report.py
from app.evals.store import get_recent

results = get_recent(10)
print(f"\n{'Run ID':<12} {'Score':>6} {'Regression':>10} {'Verdict':>8} {'Timestamp'}")
print("─" * 60)
for r in results:
    reg = "⚠ YES" if r["regression_flag"] else "—"
    score = f"{r['quality_score']*100:.0f}%"
    ts = r["timestamp"][:16].replace("T", " ")
    print(f"{r['run_id']:<12} {score:>6} {reg:>10} {r['verdict']:>8} {ts}")
print()