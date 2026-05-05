# app/workflows/eval_workflow.py
from datetime import timedelta, datetime
from temporalio import workflow, activity
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.models import ResearchBrief, SynthesisOutput
    from app.evals.models import EvalResult, QualityScore
    from app.evals.store import save_result, get_baseline_score
    from app.evals.quality_scorer import score_output
    from app.evals.regression_detector import check_regression
    from app.security.policy import check_output_policy


@activity.defn
async def run_eval_activity(
    run_id: str,
    workflow_id: str,
    focus_question: str,
    synthesis: SynthesisOutput,
) -> EvalResult:
    """Single activity that runs all eval checks."""
    activity.logger.info(f"Running eval for run_id={run_id}")

    # 1. Quality score
    quality = await score_output(
        focus_question=focus_question,
        synthesis_summary=synthesis.summary,
        key_points=synthesis.key_points,
    )

    # 2. Policy check
    policy_verdict = check_output_policy(synthesis.summary, synthesis.key_points)

    # 3. Regression check
    is_regression, delta = check_regression(run_id, quality.total)

    # 4. Determine verdict
    if not policy_verdict.safe:
        verdict = "fail"
    elif is_regression:
        verdict = "warn"
    elif quality.total < 0.5:
        verdict = "warn"
    else:
        verdict = "pass"

    result = EvalResult(
        run_id=run_id,
        workflow_id=workflow_id,
        quality_score=quality.total,
        score_breakdown=quality.model_dump(exclude={"total"}),
        policy_pass=policy_verdict.safe,
        regression_flag=is_regression,
        regression_delta=delta,
        timestamp=datetime.utcnow(),
        verdict=verdict,
    )

    save_result(result)
    activity.logger.info(f"Eval complete: verdict={verdict}, score={quality.total:.2f}")
    return result


@workflow.defn
class EvalWorkflow:
    @workflow.run
    async def run(
        self,
        run_id: str,
        workflow_id: str,
        focus_question: str,
        synthesis: SynthesisOutput,
    ) -> EvalResult:
        return await workflow.execute_activity(
            run_eval_activity,
            run_id, workflow_id, focus_question, synthesis,
            start_to_close_timeout=timedelta(minutes=3),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )