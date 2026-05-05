# app/observability/event_log.py
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from functools import wraps
from typing import Callable

LOG_PATH = Path("logs/events.jsonl")
LOG_PATH.parent.mkdir(exist_ok=True)

# Token costs in USD per 1M tokens (update as pricing changes)
COSTS = {
    "gpt-4o":       {"in": 2.50,  "out": 10.00},
    "gpt-4o-mini":  {"in": 0.15,  "out": 0.60},
}


def compute_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    rates = COSTS.get(model, {"in": 2.50, "out": 10.00})
    return round((tokens_in * rates["in"] + tokens_out * rates["out"]) / 1_000_000, 6)


def log_event(event: dict):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(event) + "\n")