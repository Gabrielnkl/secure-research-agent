# scripts/run_research.py
import asyncio
import sys
import uuid
import os
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from temporalio.client import Client
from app.workflows.research_workflow import ResearchWorkflow
from app.models import ResearchBrief, WorkflowResult


async def main():
    brief_text = " ".join(sys.argv[1:]) or "transformer architecture in modern LLMs"
    run_id = str(uuid.uuid4())[:8]

    client = await Client.connect("localhost:7233")

    # Start the workflow
    handle = await client.start_workflow(
        ResearchWorkflow.run,
        ResearchBrief(text=brief_text, run_id=run_id),
        id=f"research-{run_id}",
        task_queue="research-queue",
    )

    print(f"Workflow started: research-{run_id}")
    print(f"Temporal UI: http://localhost:8233/namespaces/default/workflows/research-{run_id}")
    print("Waiting for result (send approval signal to continue)...")

    result: WorkflowResult = await handle.result()
    print("\n--- Result ---")
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())