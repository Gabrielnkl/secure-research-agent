# app/activities/validate_activity.py
from temporalio import activity
from app.models import SynthesisOutput, SecurityVerdict
from app.security.policy import check_output_policy


@activity.defn
async def validate_output_activity(output: SynthesisOutput) -> SecurityVerdict:
    activity.logger.info("Validating output against output policy")
    verdict = check_output_policy(output.summary, output.key_points)
    activity.logger.info(f"Output validation: safe={verdict.safe}")
    return verdict