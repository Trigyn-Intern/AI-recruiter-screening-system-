#!/usr/bin/env python3
"""Quick validation that the optimized pipeline works."""

from pathlib import Path

from fastapi.testclient import TestClient

import api

JOB_DESCRIPTION = "Python backend engineer with FastAPI experience"

client = TestClient(api.api)

# Test with 1 resume
resume_path = Path("tests/data/resumes/resume_strong_python.pdf")
if resume_path.exists():
    print("Running quick validation test...")
    with open(resume_path, "rb") as f:
        response = client.post(
            "/analyze",
            data={
                "job_description": JOB_DESCRIPTION,
                "provider": "Ollama",
                "model_name": "llama3.2",
                "detail_limit": "2",
            },
            files={"resumes": (resume_path.name, f, "application/pdf")},
        )

    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        timings = data.get("timings_ms", {})

        print("\nTimings:")
        for k, v in sorted(timings.items()):
            if not k.endswith("_ms"):
                continue
            print(f"  {k}: {v} ms")

        if "faiss_search_ms" in timings:
            print("\n✓ FAISS search optimization is active!")
        else:
            print("\n⚠ FAISS search not in timings (may not be triggered)")

        print(f"\nRanking: {len(data.get('ranking', []))} candidates")
        print(f"Top details: {len(data.get('top_details', []))} analyzed")
    else:
        print(f"Error: {response.text}")
else:
    print(f"Test resume not found: {resume_path}")
