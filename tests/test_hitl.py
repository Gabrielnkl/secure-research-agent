# tests/test_hitl.py
import asyncio
import pytest
import uuid
from temporalio.client import Client
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from app.workflows.research_workflow import ResearchWorkflow
from app.activities.plan_activity import plan_activity
from app.activities.search_activity import search_activity
from app.activities.synthesize_activity import synthesize_activity
from app.activities.validate_activity import validate_output_activity
from app.activities.security_gate_activity import security_gate_activity
from app.models import ResearchBrief, WorkflowResult


@pytest.mark.asyncio
async def test_workflow_approves_on_signal():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[ResearchWorkflow],
            activities=[
                security_gate_activity, plan_activity,
                search_activity, synthesize_activity, validate_output_activity,
            ],
        ):
            run_id = str(uuid.uuid4())[:8]
            handle = await env.client.start_workflow(
                ResearchWorkflow.run,
                ResearchBrief(text="transformer architecture", run_id=run_id),
                id=f"test-{run_id}",
                task_queue="test-queue",
            )

            # Send approval signal
            await handle.signal("approve", True, "test approval")
            result: WorkflowResult = await handle.result()

            assert result.blocked is False
            assert result.approved is True
            assert result.synthesis is not None


@pytest.mark.asyncio
async def test_workflow_rejects_on_signal():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(env.client, task_queue="test-queue-2",
                          workflows=[ResearchWorkflow],
                          activities=[security_gate_activity, plan_activity,
                                      search_activity, synthesize_activity,
                                      validate_output_activity]):
            run_id = str(uuid.uuid4())[:8]
            handle = await env.client.start_workflow(
                ResearchWorkflow.run,
                ResearchBrief(text="transformer architecture", run_id=run_id),
                id=f"test-reject-{run_id}",
                task_queue="test-queue-2",
            )
            await handle.signal("approve", False, "bad output")
            result: WorkflowResult = await handle.result()

            assert result.blocked is True
            assert "bad output" in (result.block_reason or "")
