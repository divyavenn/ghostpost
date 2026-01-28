"""
Test script to create a desktop job and verify it works end-to-end
"""

import asyncio
from backend.desktop.desktop_jobs import create_desktop_job, desktop_jobs

async def test_create_job():
    print("Creating a test desktop job...")

    # Create a simple search job
    job_id = create_desktop_job(
        username="divya_venn",
        job_type="search_tweets",
        params={
            "query": "test query",
            "max_results": 5
        }
    )

    print(f"✅ Created job: {job_id}")
    print(f"   Type: search_tweets")
    print(f"   Status: pending")
    print()
    print("Job details:")
    job = desktop_jobs[job_id]
    print(f"  - ID: {job.id}")
    print(f"  - Username: {job.username}")
    print(f"  - Type: {job.job_type}")
    print(f"  - Params: {job.params}")
    print(f"  - Status: {job.status}")
    print()
    print("The desktop app should pick this up within 60 seconds!")
    print()
    print("To check job status:")
    print(f"  curl http://localhost:8000/desktop-jobs/divya_venn/status")
    print()
    print("Desktop app will poll:")
    print(f"  GET http://localhost:8000/desktop-jobs/divya_venn/pending")

if __name__ == "__main__":
    asyncio.run(test_create_job())
