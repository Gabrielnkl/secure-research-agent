# app/activities/plan_activity.py
from temporalio import activity
from app.models import ResearchBrief, ResearchPlan
from app.llm import call_llm_structured

PLAN_SYSTEM = """You are a research planning assistant. 
Given a research brief, produce a structured research plan.

Rules:
- Generate 2 to 4 focused search queries. More specific is better.
- The focus should be the single clearest question the research answers.
- Use depth "deep" only if the brief asks for comprehensive analysis.
"""


@activity.defn
async def plan_activity(brief: ResearchBrief) -> ResearchPlan:
    activity.logger.info(f"Planning for: {brief.text[:80]}")

    return await call_llm_structured(
        system=PLAN_SYSTEM,
        user=f"Research brief: {brief.text}",
        schema=ResearchPlan,
        model="gpt-4o-mini",   # Fast and cheap for planning
        attempt_label="plan",
    )