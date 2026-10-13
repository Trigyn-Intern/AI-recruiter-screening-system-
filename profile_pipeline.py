#!/usr/bin/env python3
"""
Detailed profiling script to identify bottlenecks in the analyze pipeline.
Tests with 1, 2, 5, 10 resumes.
"""

import time
from pathlib import Path

from fastapi.testclient import TestClient

import api

JOB_DESCRIPTION = """
Senior Python Backend Engineer (5+ years)

Required:
- FastAPI, Django, or similar frameworks
- PostgreSQL, MySQL, or similar databases
- Docker and containerization
- pytest and unit testing
- REST API design

Preferred:
- GraphQL, gRPC
- Microservices, event-driven systems
- AWS/GCP/Azure
- CI/CD pipelines (GitHub Actions, GitLab CI)
"""

RESUME_PATHS = [
    Path("tests/data/resumes/resume_strong_python.pdf"),
    Path("tests/data/resumes/resume_junior.pdf"),
    Path("tests/data/resumes/resume_frontend.pdf"),
    Path("tests/data/resumes/resume_data_engineer.pdf"),
    Path("tests/data/sample_resume.pdf"),
    Path("tests/data/resumes/resume_strong_python.pdf"),  # Re-test caching
    Path("tests/data/resumes/resume_junior.pdf"),
    Path("tests/data/resumes/resume_frontend.pdf"),
    Path("tests/data/resumes/resume_data_engineer.pdf"),
    Path("tests/data/sample_resume.pdf"),
]


def run_profile_test(resume_count, test_name):
    """Run analyze and capture detailed timing."""
    print(f"\n{'='*80}")
    print(
        f"TEST: {test_name} ({resume_count} resume{'s' if resume_count != 1 else ''})"
    )
    print(f"{'='*80}")

    # Prepare resumes
    resume_files = []
    for i in range(resume_count):
        path = RESUME_PATHS[i % len(RESUME_PATHS)]
        if path.exists():
            resume_files.append(
                ("resumes", (path.name, open(path, "rb"), "application/pdf"))
            )
        else:
            print(f"ERROR: Resume file not found: {path}")
            return None

    client = TestClient(api.api)

    print(f"Sending request with {resume_count} resume(s)...")
    test_start = time.perf_counter()

    try:
        response = client.post(
            "/analyze",
            data={
                "job_description": JOB_DESCRIPTION,
                "provider": "Ollama",
                "model_name": "llama3.2",
                "detail_limit": "5",
            },
            files=resume_files,
        )
    finally:
        for _, (_, file_obj, _) in resume_files:
            file_obj.close()

    total_elapsed = (time.perf_counter() - test_start) * 1000  # ms

    if response.status_code == 200:
        data = response.json()
        timings = data.get("timings_ms", {})

        # Extract and display all timings
        print(f"\n✓ SUCCESS (Status: {response.status_code})")
        print("\nDetailed Timing Breakdown:")
        print(
            f"  JD Analysis:                {timings.get('jd_analysis_ms', 0):>10} ms"
        )

        # Resume extraction and processing
        total_extract = 0
        total_embed = 0
        total_skill = 0
        resume_count_actual = 0

        for key in sorted(timings.keys()):
            if key.startswith("extract_"):
                val = timings[key]
                total_extract += val
                resume_count_actual += 1
            elif key.startswith("embed_"):
                val = timings[key]
                total_embed += val
            elif key.startswith("skill_"):
                val = timings[key]
                total_skill += val

        print(f"\n  Per-Resume Averages (for {resume_count_actual} uploaded):")
        if resume_count_actual > 0:
            print(
                f"    Extraction:               "
                f"{total_extract/resume_count_actual:>10.1f} ms/resume"
            )
            print(
                f"    Embedding:                "
                f"{total_embed/resume_count_actual:>10.1f} ms/resume"
            )
            print(
                f"    Skill Profile:            "
                f"{total_skill/resume_count_actual:>10.1f} ms/resume"
            )

        print(
            f"\n  Subtotal (Extraction+Embedding+Skills): "
            f"{total_extract+total_embed+total_skill:>10} ms"
        )

        # Search and scoring (implicit in pipeline)
        jd_and_extraction = (
            timings.get("jd_analysis_ms", 0) + total_extract + total_embed + total_skill
        )

        pipeline_total = timings.get("total_pipeline_ms", 0)
        llm_grading_time = pipeline_total - jd_and_extraction

        print(f"  LLM Candidate Analysis:    {llm_grading_time:>10} ms")
        print("  ──────────────────────────────────────────")
        print(
            f"  TOTAL PIPELINE:            {pipeline_total:>10} ms "
            f"({pipeline_total/1000:.1f}s)"
        )
        print(
            f"  Endpoint Response:         {int(total_elapsed):>10} ms "
            f"({total_elapsed/1000:.1f}s)"
        )

        # Results
        ranking = data.get("ranking", [])
        top_details = data.get("top_details", [])
        invalid = len(data.get("invalid_resumes", []))

        print("\nResults:")
        print(f"  Total candidates ranked:  {len(ranking):>10}")
        print(f"  Top candidates analyzed:  {len(top_details):>10}")
        if invalid:
            print(f"  Invalid resumes:          {invalid:>10}")

        # Vector store status
        runtime_status = data.get("runtime_status", {})
        if runtime_status.get("last_vector_store_status"):
            print(f"\nVector Store: {runtime_status['last_vector_store_status']}")

        return {
            "status": "success",
            "resume_count": resume_count,
            "jd_analysis_ms": timings.get("jd_analysis_ms", 0),
            "extraction_total_ms": total_extract,
            "embedding_total_ms": total_embed,
            "skill_total_ms": total_skill,
            "llm_analysis_ms": llm_grading_time,
            "pipeline_total_ms": pipeline_total,
            "endpoint_response_ms": int(total_elapsed),
            "candidates_ranked": len(ranking),
            "top_analyzed": len(top_details),
        }
    else:
        print(f"\n✗ FAILED (Status: {response.status_code})")
        print(f"Response: {response.text[:500]}")
        return {
            "status": "failed",
            "resume_count": resume_count,
            "error": response.text[:200],
        }


def main():
    """Profile with 1, 2, 5, 10 resumes."""
    print("\nAI Recruiter Screening System - Pipeline Profiling")
    print("=" * 80)
    print("Identifying bottlenecks in the /analyze pipeline\n")

    results = []
    for count in [1, 2, 5, 10]:
        result = run_profile_test(count, "Profile Test")
        if result:
            results.append(result)

    # Summary table
    print(f"\n\n{'='*80}")
    print("PROFILING SUMMARY")
    print(f"{'='*80}\n")

    print(
        f"{'Resumes':<10} {'JD':<10} {'Extract':<10} {'Embed':<10} "
        f"{'Skills':<10} {'LLM':<12} {'Total':<10}"
    )
    print("-" * 82)

    for result in results:
        if result.get("status") == "success":
            resumes = result.get("resume_count")
            jd = result.get("jd_analysis_ms", 0)
            extract = result.get("extraction_total_ms", 0)
            embed = result.get("embedding_total_ms", 0)
            skills = result.get("skill_total_ms", 0)
            llm = result.get("lllm_analysis_ms", 0)
            total = result.get("pipeline_total_ms", 0)

            print(
                f"{resumes:<10} {jd/1000:>8.1f}s {extract/1000:>8.1f}s "
                f"{embed/1000:>8.1f}s {skills/1000:>8.1f}s "
                f"{llm/1000:>10.1f}s {total/1000:>8.1f}s"
            )

    print("\n" + "=" * 80)
    print("BOTTLENECK ANALYSIS")
    print("=" * 80)

    # Identify bottlenecks
    if results:
        largest = max(results, key=lambda r: r.get("pipeline_total_ms", 0))
        timings = largest

        components = {
            "JD Analysis": timings.get("jd_analysis_ms", 0),
            "Extraction": timings.get("extraction_total_ms", 0),
            "Embedding": timings.get("embedding_total_ms", 0),
            "Skills": timings.get("skill_total_ms", 0),
            "LLM Analysis": timings.get("lllm_analysis_ms", 0),
        }

        total_ms = sum(components.values())
        print(f"\nFor the largest test ({largest.get('resume_count')} resumes):")
        print(f"Total pipeline time: {total_ms/1000:.1f}s\n")

        sorted_components = sorted(components.items(), key=lambda x: x[1], reverse=True)
        for name, ms in sorted_components:
            pct = (ms / total_ms * 100) if total_ms > 0 else 0
            bar = "█" * int(pct / 2)
            print(f"  {name:<20} {ms/1000:>8.1f}s ({pct:>5.1f}%) {bar}")


if __name__ == "__main__":
    main()
