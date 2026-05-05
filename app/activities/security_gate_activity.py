# app/activities/security_gate_activity.py
from temporalio import activity
from app.models import ResearchBrief, SecurityVerdict
from app.security.quarantine_llm import classify_input
from app.security.policy import check_input_policy, PolicyViolationError

import os

print("ACTIVITY KEY:", os.getenv("OPENAI_API_KEY"))

@activity.defn
async def security_gate_activity(brief: ResearchBrief) -> SecurityVerdict:
    """
    Run before any other activity. Blocks the workflow if input is unsafe.
    This activity should NOT be retried on PolicyViolationError.
    """
    activity.logger.info(f"Running security gate for run_id={brief.run_id}")

    # Step 1: quarantine LLM classification
    verdict = await classify_input(brief.text)
    activity.logger.info(f"Quarantine verdict: safe={verdict.safe}")

    # Step 2: static + combined policy check
    try:
        check_input_policy(brief.text, verdict)
    except PolicyViolationError as e:
        # Return a blocked verdict — workflow will handle it
        return SecurityVerdict(safe=False, reason=str(e))

    return SecurityVerdict(safe=True, reason="Input passed all security checks.")