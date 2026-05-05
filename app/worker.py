# app/worker.py
import asyncio
import logging
from dotenv import load_dotenv
import os
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

print("CWD:", os.getcwd())
print("ENV FILE EXISTS:", os.path.exists(".env"))
print("KEY:", os.getenv("OPENAI_API_KEY"))

from temporalio.client import Client
from temporalio.worker import Worker

from app.workflows.research_workflow import ResearchWorkflow
from app.workflows.eval_workflow import EvalWorkflow
from app.activities.security_gate_activity import security_gate_activity
from app.activities.plan_activity import plan_activity
from app.activities.search_activity import search_activity
from app.activities.synthesize_activity import synthesize_activity
from app.activities.validate_activity import validate_output_activity
from app.workflows.eval_workflow import run_eval_activity

logging.basicConfig(level=logging.INFO)


async def main():
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="research-queue",
        workflows=[ResearchWorkflow, EvalWorkflow],
        activities=[
            security_gate_activity,
            plan_activity,
            search_activity,
            synthesize_activity,
            validate_output_activity,
            run_eval_activity,
        ],
    )

    print("Worker started. Listening on task queue: research-queue")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
