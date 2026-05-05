# scripts/send_approval.py
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from temporalio.client import Client
from app.models import ApprovalInput


async def main():
    workflow_id = sys.argv[1]
    verdict = sys.argv[2].lower() == "approve"
    note = " ".join(sys.argv[3:]) or ""

    client = await Client.connect("localhost:7233")
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal("approve", ApprovalInput(verdict=verdict, note=note))
    print(f"Signal sent: {'approved' if verdict else 'rejected'}")


if __name__ == "__main__":
    asyncio.run(main())