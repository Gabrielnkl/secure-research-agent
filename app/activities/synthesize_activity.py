# app/activities/synthesize_activity.py
import asyncio
import logging
from temporalio import activity
from pydantic import ValidationError
from app.models import ResearchPlan, SearchResult, SynthesisOutput
from app.llm import call_llm_structured

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.55

SYNTHESIZE_SYSTEM = """You are a research synthesis assistant.
Given a research plan and search results, write a structured synthesis.

Rules:
- summary: 2–4 sentence overview answering the focus question
- key_points: 3–6 specific, concrete findings (not vague platitudes)
- sources: include only URLs that actually appeared in the search results
- confidence: your honest estimate of answer quality given the sources (0.0–1.0)
  Use 0.3–0.5 if sources are sparse or off-topic. Use 0.7–0.9 if sources directly answer the question.
"""

FALLBACK_SYSTEM = """You are a research assistant. Summarize the provided text snippets.
Return JSON with: summary (string), key_points (list of strings), sources (list of strings), confidence (float 0.0–1.0).
Keep it short and honest. Set confidence to 0.4 if sources are weak.
"""


def _build_search_context(plan: ResearchPlan, results: list[SearchResult]) -> str:
    lines = [f"Focus question: {plan.focus}\n"]
    for r in results:
        lines.append(f"\nQuery: {r.query}")
        for i, snippet in enumerate(r.snippets, 1):
            lines.append(f"  [{i}] {snippet[:400]}")
        for url in r.sources[:3]:
            lines.append(f"  Source: {url}")
    return "\n".join(lines)


@activity.defn
async def synthesize_activity(
    plan: ResearchPlan,
    results: list[SearchResult],
) -> SynthesisOutput:
    activity.logger.info(f"Synthesizing {sum(len(r.snippets) for r in results)} snippets")

    context = _build_search_context(plan, results)

    # Attempt 1: full synthesis
    try:
        output = await call_llm_structured(
            system=SYNTHESIZE_SYSTEM,
            user=context,
            schema=SynthesisOutput,
            model="gpt-4o",
            attempt_label="synthesize-primary",
        )

        if output.confidence >= CONFIDENCE_THRESHOLD:
            activity.logger.info(f"Primary synthesis succeeded, confidence={output.confidence:.2f}")
            return output

        activity.logger.warning(
            f"Primary synthesis confidence too low ({output.confidence:.2f} < {CONFIDENCE_THRESHOLD}), falling back"
        )

    except (ValidationError, ValueError) as e:
        activity.logger.warning(f"Primary synthesis failed to parse: {e}")

    # Attempt 2: simpler fallback prompt
    try:
        fallback_context = f"Summarize these search results about: {plan.focus}\n\n{context[:2000]}"
        output = await call_llm_structured(
            system=FALLBACK_SYSTEM,
            user=fallback_context,
            schema=SynthesisOutput,
            model="gpt-4o-mini",
            attempt_label="synthesize-fallback",
        )
        activity.logger.info(f"Fallback synthesis succeeded, confidence={output.confidence:.2f}")
        return output

    except (ValidationError, ValueError) as e:
        activity.logger.error(f"Fallback synthesis also failed: {e}")

    # Graceful degradation — return a structured but honest response
    all_snippets = [s for r in results for s in r.snippets]
    return SynthesisOutput(
        summary=f"Research on '{plan.focus}' completed but synthesis quality was insufficient for a confident answer.",
        key_points=[s[:150] for s in all_snippets[:3]],
        sources=list({url for r in results for url in r.sources})[:5],
        confidence=0.2,
    )