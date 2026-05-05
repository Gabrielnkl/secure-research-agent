# app/evals/quality_scorer.py
import json
from pydantic import BaseModel
from app.llm import call_llm_structured
from app.evals.models import QualityScore


class _ScoreResponse(BaseModel):
    relevance: float
    accuracy: float
    completeness: float
    clarity: float
    reasoning: str


SCORER_SYSTEM = """You are an impartial research quality evaluator.
Score the provided research output on four dimensions, each from 0.0 to 1.0:

- relevance: does the summary directly answer the original question?
- accuracy: are the key points internally consistent and plausible given the sources?
- completeness: does it cover the main aspects of the topic?
- clarity: is it well-written, specific, and free of vague filler?

Be strict. A score of 0.8+ means genuinely excellent. 0.5 is mediocre. Below 0.4 is poor.
Include a brief reasoning field explaining your scores.
"""


async def score_output(
    focus_question: str,
    synthesis_summary: str,
    key_points: list[str],
) -> QualityScore:
    user_content = (
        f"Original question: {focus_question}\n\n"
        f"Summary: {synthesis_summary}\n\n"
        f"Key points:\n" + "\n".join(f"- {p}" for p in key_points)
    )

    response = await call_llm_structured(
        system=SCORER_SYSTEM,
        user=user_content,
        schema=_ScoreResponse,
        model="gpt-4o-mini",  # Use fast model for evals
        attempt_label="eval-scorer",
    )

    return QualityScore.from_breakdown({
        "relevance": response.relevance,
        "accuracy": response.accuracy,
        "completeness": response.completeness,
        "clarity": response.clarity,
    })