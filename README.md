# Secure Research Agent

A production-grade agentic pipeline demonstrating Temporal-orchestrated multi-step LLM workflows with hardened security, parallel evaluation, and full observability.

```
User input
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Security gate — quarantined LLM (gpt-4o-mini)                      │
│  prompt injection scan · static blocklist · policy check            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ safe
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Temporal durable workflow                                           │
│                                                                      │
│  [Plan]──▶ [Search ×N]──▶ [Synthesize]──▶ [HITL checkpoint]        │
│              ╎  ╎  ╎         │                    │                 │
│         parallel fan-out   fallback             signal              │
│              ╎  ╎  ╎       routing              API                 │
│              └──┴──┘                                                 │
│                    ╎──────────────────────────────────▶ [Eval child]│
│                                                          LLM-judge   │
│                                                          regression  │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Observability                                                       │
│  events.jsonl · cost per call · latency spans · Temporal UI         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key design decisions

**Why Temporal:** durable execution means the workflow survives process crashes. State is persisted after every activity. Long-running agents with human-in-the-loop steps need this guarantee — `asyncio` alone doesn't provide it.

**Why dual-LLM:** prompt injection is best handled by never letting the privileged agent see untrusted input unchecked. The quarantine model is intentionally restricted — no tools, no context, single classification task. Even if it's injected, it can't do anything harmful.

**Why parallel evals:** quality assessment can't block the user-facing response. Child workflows run alongside production traffic and write verdicts independently. Regression detection catches prompt changes before they degrade user experience.

---

## Stack

| Layer | Technology |
|---|---|
| Orchestration | [Temporal](https://temporal.io) |
| LLM | OpenAI (`gpt-4o`, `gpt-4o-mini`) |
| Web framework | FastAPI + uvicorn |
| Data validation | Pydantic v2 |
| Search | DuckDuckGo (default) or Tavily |
| Storage | SQLite (evals + approvals) |
| Observability | JSONL event log + Chart.js dashboard |
| Testing | pytest + pytest-asyncio |

---

## Project structure

```
secure-research-agent/
├── app/
│   ├── llm.py                          # structured generation helper
│   ├── models.py                       # shared Pydantic models
│   ├── worker.py                       # Temporal worker entrypoint
│   ├── workflows/
│   │   ├── research_workflow.py        # main durable workflow
│   │   └── eval_workflow.py            # parallel eval child workflow
│   ├── activities/
│   │   ├── security_gate_activity.py   # dual-LLM input check
│   │   ├── plan_activity.py            # structured research planning
│   │   ├── search_activity.py          # parallel web search (fan-out)
│   │   ├── synthesize_activity.py      # constrained generation + fallback
│   │   └── validate_activity.py        # output policy check
│   ├── security/
│   │   ├── quarantine_llm.py           # isolated classifier LLM
│   │   ├── policy.py                   # input + output policy rules
│   │   └── approvals.py                # HITL approval store
│   ├── evals/
│   │   ├── models.py                   # EvalResult, QualityScore
│   │   ├── store.py                    # SQLite eval persistence
│   │   ├── quality_scorer.py           # LLM-as-judge rubric scorer
│   │   └── regression_detector.py     # baseline comparison
│   ├── observability/
│   │   └── event_log.py                # per-call cost + latency logging
│   └── api/
│       ├── main.py                     # FastAPI app + approval endpoint
│       └── dashboard.html              # Chart.js observability dashboard
├── scripts/
│   ├── run_research.py                 # trigger a workflow run
│   ├── send_approval.py                # send HITL signal via CLI
│   └── eval_report.py                  # print last N eval results
├── tests/
│   ├── test_security.py
│   ├── test_hitl.py
│   └── test_e2e.py
├── logs/                               # events.jsonl, *.db (gitignored)
├── requirements.txt
├── Makefile
└── .env                                # OPENAI_API_KEY (gitignored)
```

---

## Run locally

```bash
# 1. Clone and install
git clone https://github.com/gabrielnkl/secure-research-agent
cd secure-research-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Add API key
echo "OPENAI_API_KEY=your_key" > .env

# 3. Start Temporal dev server, worker, and API in one command
make dev

# 4. Submit a research brief
python scripts/run_research.py "history of transformer models"

# 5. Approve via dashboard (or CLI)
xdg-open http://localhost:8000
# or: python scripts/send_approval.py research-<id> approve
```

### Temporal CLI (Linux)

```bash
curl -sSf https://temporal.download/cli.sh | sh
echo 'export PATH="$HOME/.temporalio/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

The Temporal UI is available at `http://localhost:8233` — inspect every workflow's full event history, activity timings, and retry attempts.

---

## How the pipeline works

**1. Security gate (dual-LLM pattern)**
Every input passes through a quarantined `gpt-4o-mini` instance before anything else. This model has no tools, no prior context — only a classification task: is the input safe? If blocked, the workflow terminates immediately. Static regex patterns run first (no LLM call needed for obvious injections).

**2. Planning**
A structured LLM call (Pydantic-validated JSON output) turns the brief into a `ResearchPlan`: 2–4 focused search queries plus a `focus` question.

**3. Parallel search (fan-out/fan-in)**
All queries are dispatched simultaneously as Temporal activities. `asyncio.gather()` fans them out; Temporal handles retries per-activity if any fail. Total latency equals the slowest single search, not the sum of all.

**4. Synthesis with fallback routing**
The synthesizer attempts a high-quality structured response. If confidence < 0.55 or JSON parsing fails, it falls back to a simpler prompt. If that also fails, it returns a graceful degraded response. The caller always receives a valid `SynthesisOutput`.

**5. Human-in-the-loop checkpoint**
The workflow suspends and waits for a Temporal signal (HTTP POST to `/api/approve/<workflow_id>`). No polling — the workflow is event-driven. Times out and auto-approves after 10 minutes if no signal arrives.

**6. Parallel evaluation (child workflow)**
Fired immediately after synthesis, independent of the HITL step. An LLM-as-judge scores the output on four rubric dimensions (relevance, accuracy, completeness, clarity). Compares against recent baseline; flags regression if score drops > 15 points. Writes an `EvalResult` to SQLite.

**7. Observability**
Every LLM call logs a structured JSON event: model, token counts, cost in USD, latency in ms. The FastAPI dashboard at `http://localhost:8000` plots these over time and shows the live approval queue.

---

## Make targets

```bash
make dev          # start Temporal server + worker + API (background)
make worker       # start worker only
make api          # start API server only
make test         # run all tests
make eval-report  # print last 10 eval results as a table
```

---

## Tests

```bash
# Run all
pytest tests/ -v

# Individual suites
pytest tests/test_security.py -v     # security gate unit + integration tests
pytest tests/test_hitl.py -v         # signal + timeout tests (time-skipping)
pytest tests/test_e2e.py -v          # full workflow with mocked LLM calls
```

Tests use `WorkflowEnvironment.start_time_skipping()` — Temporal's test environment skips timer waits instantly, so the 10-minute HITL timeout resolves in milliseconds during CI.

---

## Job spec coverage

| Requirement | Implementation |
|---|---|
| Agentic workflow engineering + Temporal | `ResearchWorkflow` — retries, state, parallelism, HITL |
| Dual-LLM / prompt injection defense | `quarantine_llm.py` + `policy.py` — fail-closed, layered |
| Human-in-the-loop steps | Temporal signal API with timeout + auto-escalation |
| Parallel activities (fan-out/fan-in) | `asyncio.gather` on `search_activity` calls |
| Parallel + live evaluation | `EvalWorkflow` child + LLM-as-judge + regression detection |
| Structured generation + fallback routing | `call_llm_structured` + confidence-gated retry chain |
| Output steering + constrained decoding | OpenAI JSON mode + Pydantic schema enforcement |
| Observability + cost tracking | `event_log.py` — tokens, USD, latency per call |
| Audit trail | `events.jsonl` + Temporal event history UI |
| Policy engine integration | `policy.py` — input + output policy with `PolicyViolationError` |
