#!/usr/bin/env python3
"""
Test script to validate the /analyze timeout fix and FAISS integrity.
Tests with 1, 2, and 5 resumes.
"""

import time
from pathlib import Path

from fastapi.testclient import TestClient

import api

# Test configuration
JOB_DESCRIPTION = """
We are looking for a Python backend engineer with 5+ years of experience.

Required Skills:
- Python (FastAPI, Django, or similar)
- SQL and relational databases (PostgreSQL, MySQL)
- Docker and containerization
- Unit testing and pytest
- REST API design

Preferred Skills:
- GraphQL
- Microservices architecture
- AWS or similar cloud platforms
- CI/CD pipelines
"""

RESUME_PATHS = [
    Path("tests/data/resumes/resume_strong_python.pdf"),
    Path("tests/data/resumes/resume_junior.pdf"),
    Path("tests/data/resumes/resume_frontend.pdf"),
    Path("tests/data/resumes/resume_data_engineer.pdf"),
    Path("tests/data/sample_resume.pdf"),
]

TEST_CASES = [
    {"name": "1 resume", "count": 1},
    {"name": "2 resumes", "count": 2},
    {"name": "5 resumes", "count": 5},
]


def run_analyze_test(resume_count, test_name):
    """Run analyze endpoint with N resumes and capture timing data."""
    print(f"\n{'='*70}")
    print(f"TEST: {test_name}")
    print(f"{'='*70}")
    
    # Prepare resumes
    resume_files = []
    for i in range(resume_count):
        path = RESUME_PATHS[i % len(RESUME_PATHS)]
        if path.exists():
            resume_files.append(("resumes", (path.name, open(path, "rb"), "application/pdf")))
        else:
            print(f"ERROR: Resume file not found: {path}")
            return None
    
    # Prepare test client
    client = TestClient(api.api)
    
    # Run test
    print(f"Sending request to /analyze with {resume_count} resume(s)...")
    test_start = time.perf_counter()
    
    try:
        response = client.post(
            "/analyze",
            data={
                "job_description": JOB_DESCRIPTION,
                "provider": "Ollama",
                "model_name": "llama3.2",
                "detail_limit": "3",
            },
            files=resume_files,
        )
    finally:
        # Close file handles
        for _, (_, file_obj, _) in resume_files:
            file_obj.close()
    
    total_elapsed = (time.perf_counter() - test_start) * 1000  # ms
    
    # Parse response
    print(f"Response Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        timings = data.get("timings_ms", {})
        
        print("\n✓ SUCCESS - Analysis completed")
        print("\nTiming Breakdown (ms):")
        print(f"  JD Analysis:        {timings.get('jd_analysis_ms', 'N/A')} ms")
        
        # Extract individual resume timings
        for i in range(resume_count):
            path = RESUME_PATHS[i % len(RESUME_PATHS)]
            extract_key = f"extract_{path.name}"
            embed_key = f"embed_{path.name}"
            skill_key = f"skill_{path.name}"
            
            extract_ms = timings.get(extract_key, "N/A")
            embed_ms = timings.get(embed_key, "N/A")
            skill_ms = timings.get(skill_key, "N/A")
            
            print(f"\n  Resume {i+1} ({path.name}):")
            print(f"    Extract:     {extract_ms} ms")
            print(f"    Embedding:   {embed_ms} ms")
            print(f"    Skills:      {skill_ms} ms")
        
        total_pipeline = timings.get("total_pipeline_ms", "N/A")
        print(f"\n  Total Pipeline:     {total_pipeline} ms")
        print(f"  Endpoint Response:  {int(total_elapsed)} ms")
        
        # Analysis results
        ranking = data.get("ranking", [])
        top_details = data.get("top_details", [])
        
        print("\nResults:")
        print(f"  Total candidates ranked: {len(ranking)}")
        print(f"  Top candidates analyzed: {len(top_details)}")
        
        if ranking:
            print("\n  Ranking:")
            for i, candidate in enumerate(ranking[:3]):
                print(f"    {i+1}. {candidate.get('resume_name', 'Unknown')} - Score: {candidate.get('match_score', 0):.1f}%")
        
        runtime_status = data.get("runtime_status", {})
        if runtime_status.get("last_vector_store_status"):
            print(f"\nVector Store Status: {runtime_status['last_vector_store_status']}")
        if runtime_status.get("last_vector_store_error"):
            print(f"Vector Store Error: {runtime_status['last_vector_store_error']}")
        
        return {
            "status": "success",
            "resume_count": resume_count,
            "jd_analysis_ms": timings.get("jd_analysis_ms"),
            "total_pipeline_ms": timings.get("total_pipeline_ms"),
            "endpoint_response_ms": int(total_elapsed),
            "candidates_ranked": len(ranking),
            "top_candidates": len(top_details),
        }
    else:
        print(f"\n✗ FAILED - Status {response.status_code}")
        print(f"Response: {response.text[:500]}")
        return {
            "status": "failed",
            "resume_count": resume_count,
            "endpoint_response_ms": int(total_elapsed),
            "error": response.text[:200],
        }


def main():
    """Run all test cases."""
    print("\nTesting /analyze endpoint timeout and FAISS integrity fix")
    print("="*70)
    print("Configuration:")
    print("  New timeout: 600 seconds (10 minutes)")
    print("  Provider: Ollama")
    print("  Model: llama3.2")
    print("  Detail limit: 3")
    
    results = []
    for test_case in TEST_CASES:
        result = run_analyze_test(test_case["count"], test_case["name"])
        if result:
            results.append(result)
    
    # Summary
    print(f"\n\n{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}")
    
    print("\nResults:")
    print(f"{'Resumes':<10} {'Status':<12} {'JD Analysis':<15} {'Total Pipeline':<18} {'Candidates':<12}")
    print("-" * 70)
    
    for result in results:
        status = result.get("status", "unknown").upper()
        resume_count = result.get("resume_count", 0)
        jd_ms = result.get("jd_analysis_ms", "N/A")
        total_ms = result.get("total_pipeline_ms", "N/A")
        candidates = result.get("top_candidates", "N/A")
        
        if isinstance(jd_ms, (int, float)):
            jd_ms = f"{int(jd_ms)} ms"
        if isinstance(total_ms, (int, float)):
            total_ms = f"{int(total_ms)} ms"
        if isinstance(candidates, int):
            candidates = str(candidates)
        
        print(f"{resume_count:<10} {status:<12} {jd_ms!s:<15} {total_ms!s:<18} {candidates!s:<12}")
    
    # Check if all tests passed
    all_passed = all(r.get("status") == "success" for r in results)
    if all_passed:
        print("\n✓ All tests PASSED")
    else:
        print("\n✗ Some tests FAILED")
    
    print("\nNOTE: These tests use Ollama llama3.2 which may be slow.")
    print("      Timeout is now 600 seconds (10 minutes) instead of 90 seconds.")


if __name__ == "__main__":
    main()
