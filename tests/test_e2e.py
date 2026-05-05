# tests/test_e2e.py
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from app.workflows.research_workflow import ResearchWorkflow
from app.activities.plan_activity import plan_activity
from app.activities.search_activity import search_activity
from app.activities.synthesize_activity import synthesize_activity
from app.activities.validate_activity import validate_output_activity
from app.activities.security_gate_activity import security_gate_activity
from app.models import ResearchBrief, WorkflowResult


MOCK_PLAN = '{"queries": ["test query 1", "test query 2"], "focus": "test focus", "depth": "shallow"}'
MOCK_SYNTHESIS = '{"summary": "Test summary.", "key_points": ["Point 1", "Point 2"], "sources": ["https://example.com"], "confidence": 0.8}'
MOCK_GATE = '{"safe": true, "reason": "clean input"}'


def _mock_openai_response(text: str, model: str = "gpt-4o-mini"):
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    usage = MagicMock()
    usage.prompt_tokens = 100
    usage.completion_tokens = 50
    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    response.model = model
    return response


@pytest.mark.asyncio
async def test_full_workflow_e2e():
    """Full workflow with mocked LLM calls — no real API calls made."""
    with patch("app.llm._client") as mock_llm, \
         patch("app.security.quarantine_llm._client") as mock_gate_llm:

        mock_gate_llm.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(MOCK_GATE)
        )
        mock_llm.chat.completions.create = AsyncMock(side_effect=[
            _mock_openai_response(MOCK_PLAN),        # plan_activity
            _mock_openai_response(MOCK_SYNTHESIS),   # synthesize_activity
        ])

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client, task_queue="e2e-queue",
                workflows=[ResearchWorkflow],
                activities=[security_gate_activity, plan_activity,
                            search_activity, synthesize_activity,
                            validate_output_activity],
            ):
                run_id = str(uuid.uuid4())[:8]
                handle = await env.client.start_workflow(
                    ResearchWorkflow.run,
                    ResearchBrief(text="transformer architecture", run_id=run_id),
                    id=f"e2e-{run_id}",
                    task_queue="e2e-queue",
                )
                await handle.signal("approve", True, "test")
                result: WorkflowResult = await handle.result()

    assert not result.blocked
    assert result.synthesis is not None
    assert result.synthesis.confidence == 0.8