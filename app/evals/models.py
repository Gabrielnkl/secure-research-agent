# app/evals/models.py
from pydantic import BaseModel
from datetime import datetime


class QualityScore(BaseModel):
    relevance: float      # 0–1: does the summary answer the question?
    accuracy: float       # 0–1: are the key points factually consistent?
    completeness: float   # 0–1: does it cover the main aspects?
    clarity: float        # 0–1: is it well-written and readable?
    total: float          # weighted average

    @classmethod
    def from_breakdown(cls, breakdown: dict[str, float]) -> "QualityScore":
        total = sum(breakdown.values()) / len(breakdown)
        return cls(total=round(total, 3), **breakdown)


class EvalResult(BaseModel):
    run_id: str
    workflow_id: str
    quality_score: float
    score_breakdown: dict[str, float]
    policy_pass: bool
    regression_flag: bool
    regression_delta: float | None = None
    timestamp: datetime
    verdict: str   # "pass" | "warn" | "fail"