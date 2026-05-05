# app/workflows/research_workflow.py
import asyncio
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.models import (
        ResearchBrief, ResearchPlan, SearchResult,
        SynthesisInput, SynthesisOutput, WorkflowResult, SecurityVerdict, ApprovalInput,
    )
    from app.activities.security_gate_activity import security_gate_activity
    from app.activities.plan_activity import plan_activity
    from app.activities.search_activity import search_activity
    from app.activities.synthesize_activity import synthesize_activity
    from app.activities.validate_activity import validate_output_activity
    from datetime import datetime


# Retry policy shared by all activities
RETRY_POLICY = RetryPolicy(
    maximum_attempts=3,
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    non_retryable_error_types=["PolicyViolationError"],
)

ACTIVITY_OPTIONS = dict(
    start_to_close_timeout=timedelta(minutes=2),
    retry_policy=RETRY_POLICY,
)


@workflow.defn
class ResearchWorkflow:
    def __init__(self):
        self._approved: bool | None = None
        self._approval_note: str = ""

    @workflow.signal
    def approve(self, approval: ApprovalInput) -> None:
        """Human-in-the-loop signal — sent externally to resume the workflow."""
        self._approved = approval.verdict
        self._approval_note = approval.note
        workflow.logger.info(f"Received approval signal: {approval.verdict} — {approval.note}")

    @workflow.run
    async def run(self, brief: ResearchBrief) -> WorkflowResult:
        workflow.logger.info(f"Starting research workflow: {brief.run_id}")

        # Step 0: Security gate — must pass before anything else
        gate_verdict: SecurityVerdict = await workflow.execute_activity(
            security_gate_activity,
            brief,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                maximum_attempts=1,  # Don't retry security checks
                non_retryable_error_types=["PolicyViolationError"],
            ),
        )

        if not gate_verdict.safe:
            workflow.logger.warning(f"Input blocked: {gate_verdict.reason}")
            return WorkflowResult(
                run_id=brief.run_id,
                blocked=True,
                block_reason=gate_verdict.reason,
            )

        # Step 1: Plan
        plan: ResearchPlan = await workflow.execute_activity(
            plan_activity, brief, **ACTIVITY_OPTIONS
        )
        workflow.logger.info(f"Plan created: {len(plan.queries)} queries")

        # Step 2: Parallel search (fan-out / fan-in)
        search_tasks = [
            workflow.execute_activity(search_activity, q, **ACTIVITY_OPTIONS)
            for q in plan.queries
        ]
        results: list[SearchResult] = list(await asyncio.gather(*search_tasks))
        workflow.logger.info(f"Search complete: {len(results)} results")

        # Step 3: Synthesize
        synthesis: SynthesisOutput = await workflow.execute_activity(
            synthesize_activity, SynthesisInput(plan=plan, results=results), **ACTIVITY_OPTIONS
        )
        workflow.logger.info(f"Synthesis done, confidence={synthesis.confidence}")

        # Step 3.5: Launch eval as child workflow
        with workflow.unsafe.imports_passed_through():
            from app.workflows.eval_workflow import EvalWorkflow

        # Fire eval as child workflow — runs independently, doesn't block main flow
        eval_handle = await workflow.start_child_workflow(
            EvalWorkflow.run,
            args=[brief.run_id, workflow.info().workflow_id, plan.focus, synthesis],
            id=f"eval-{brief.run_id}",
            task_queue="research-queue",
        )
        # Don't await — the eval runs in parallel with the rest of the workflow

        # Step 4: Record approval request and wait for signal
        with workflow.unsafe.imports_passed_through():
            from app.security.approvals import request_approval, resolve_approval

        # Record in DB so the dashboard can show it
        # Note: in Temporal workflows, side effects must use workflow.now() for time
        request_approval(
            workflow_id=workflow.info().workflow_id,
            run_id=brief.run_id,
            synthesis_summary=synthesis.summary,
        )

        workflow.logger.info("Waiting for human approval (timeout: 10 min)...")
        timed_out = not await workflow.wait_condition(
            lambda: self._approved is not None,
            timeout=timedelta(minutes=10),
        )

        if timed_out:
            # Auto-approve with warning after timeout
            workflow.logger.warning("Approval timed out — auto-approving with warning")
            self._approved = True
            self._approval_note = "auto-approved after timeout"

        if self._approved is False:
            resolve_approval(
                workflow.info().workflow_id, False, self._approval_note
            )
            return WorkflowResult(
                run_id=brief.run_id,
                blocked=True,
                block_reason=f"Rejected by reviewer: {self._approval_note}",
            )

        resolve_approval(workflow.info().workflow_id, True, self._approval_note)

        # Step 5: Validate output
        verdict: SecurityVerdict = await workflow.execute_activity(
            validate_output_activity, synthesis, **ACTIVITY_OPTIONS
        )

        if not verdict.safe:
            return WorkflowResult(
                run_id=brief.run_id,
                blocked=True,
                block_reason=f"Output failed policy check: {verdict.reason}",
            )

        return WorkflowResult(
            run_id=brief.run_id,
            synthesis=synthesis,
            approved=True,
            completed_at=workflow.now().replace(tzinfo=None),
        )