"""Fresh benchmark for parallel candidate analysis with Ollama."""

import sys
import time

import requests

API_BASE_URL = "http://127.0.0.1:8000"

sys.path.insert(0, ".")
import backend  # noqa: E402

# Clear caches before benchmark
print("Clearing caches for fresh benchmark...")

backend._JD_ANALYSIS_CACHE.clear()
backend.RUNTIME_STATE["ai_analysis_cache"] = {}
print("✓ Caches cleared")

# Use a completely different job description to trigger fresh LLM calls
jd = """
Machine Learning Engineer - AI Research Team

We are looking for a Machine Learning Engineer to join our AI Research team.

Required Skills:
- Python 3.9+ with strong ML libraries (PyTorch, TensorFlow, scikit-learn)
- Deep learning model development and deployment
- Natural Language Processing (NLP) experience
- Computer Vision expertise
- MLOps and model serving
- Kubernetes and Docker
- Cloud platforms (AWS/GCP/Azure)
- SQL and NoSQL databases

Qualifications:
- MS or PhD in Computer Science, ML, or related field
- 3+ years of production ML engineering experience
- Published research papers preferred
- Experience with transformer architectures
- Strong mathematical background

Responsibilities:
- Develop and deploy state-of-the-art ML models
- Optimize model inference performance
- Build ML pipelines and infrastructure
- Collaborate with research scientists
- Contribute to open-source ML projects
"""

print("\n=== Fresh Benchmark: 2 Candidates with Ollama ===")
print("Using provider: Ollama")
print("Using model: llama3.2")
print("Detail limit: 2")
print("-" * 60)

start_time = time.perf_counter()
http_start = time.time()

try:
    response = requests.post(
        f"{API_BASE_URL}/analyze",
        data={
            "job_description": jd,
            "provider": "Ollama",
            "model_name": "llama3.2",
            "detail_limit": 2,
        },
        timeout=600,
    )

    http_elapsed = time.time() - http_start
    total_elapsed = time.perf_counter() - start_time

    if response.status_code == 200:
        data = response.json()

        print("✓ Analysis completed successfully")
        print("\n=== Timing Results ===")
        print(f"HTTP response time: {http_elapsed:.2f}s")
        print(f"Total elapsed time: {total_elapsed:.2f}s")
        print(f"API reported pipeline time: {data.get('_elapsed_ms', 0) / 1000:.2f}s")

        timings = data.get("timings_ms", {})
        print("\n=== Breakdown ===")
        print(f"JD analysis: {timings.get('jd_analysis_ms', 0) / 1000:.2f}s")
        print(f"FAISS search: {timings.get('faiss_search_ms', 0) / 1000:.2f}s")
        print(f"Total pipeline: {timings.get('total_pipeline_ms', 0) / 1000:.2f}s")

        ranking = data.get("ranking", [])
        top_details = data.get("top_details", [])

        print("\n=== Results ===")
        print(f"Total candidates in ranking: {len(ranking)}")
        print(f"Top details returned: {len(top_details)}")

        # Check for LLM errors
        runtime_status = data.get("runtime_status", {})
        if runtime_status.get("last_ai_error"):
            print(f"⚠ LLM error: {runtime_status['last_ai_error']}")
        else:
            print("✓ No LLM errors")

        # Check grading checkpoints to see LLM calls
        grading_checkpoints = runtime_status.get("grading_checkpoints", [])
        if grading_checkpoints:
            print(f"\n=== LLM Grading Calls ({len(grading_checkpoints)}) ===")
            for i, checkpoint in enumerate(grading_checkpoints, 1):
                print(f"{i}. {checkpoint.get('resume_name', 'Unknown')}")
                print(f"   Source: {checkpoint.get('source', 'unknown')}")
                print(f"   Cache: {checkpoint.get('cache', 'unknown')}")
                print(f"   Grade: {checkpoint.get('final_grade', 'N/A')}")
                if checkpoint.get("gemini_error"):
                    print(f"   Error: {checkpoint['gemini_error']}")

        # Verify structure
        required_keys = [
            "job_description",
            "ranking",
            "top_details",
            "detail_limit",
            "categories",
        ]
        missing_keys = [k for k in required_keys if k not in data]
        if missing_keys:
            print(f"\n⚠ Missing response keys: {missing_keys}")
        else:
            print("\n✓ Response structure intact")

        # Check FAISS
        if runtime_status.get("last_vector_store_error"):
            print(f"⚠ FAISS error: {runtime_status['last_vector_store_error']}")
        else:
            print("✓ No FAISS errors")

        print("\n=== Comparison with Baseline ===")
        baseline_time = 137.0  # Sequential baseline from FINAL_OPTIMIZATION_REPORT.md
        print(f"Sequential baseline (5 candidates): {baseline_time:.2f}s")
        print(f"Parallel execution (5 candidates): {total_elapsed:.2f}s")

        if total_elapsed > 0:
            speedup = baseline_time / total_elapsed
            improvement = ((baseline_time - total_elapsed) / baseline_time) * 100
            print(f"Speedup: {speedup:.2f}x")
            print(f"Improvement: {improvement:.1f}%")

        # Estimate LLM time
        estimated_llm_time = (
            total_elapsed
            - (timings.get("jd_analysis_ms", 0) / 1000)
            - (timings.get("faiss_search_ms", 0) / 1000)
        )
        print(f"\nEstimated LLM analysis time: {estimated_llm_time:.2f}s")

        # Check if grading calls were concurrent
        if grading_checkpoints:
            cache_hits = sum(
                1 for cp in grading_checkpoints if cp.get("cache") == "hit"
            )
            cache_misses = sum(
                1 for cp in grading_checkpoints if cp.get("cache") == "miss"
            )
            print("\n=== Cache Analysis ===")
            print(f"Grading cache hits: {cache_hits}")
            print(f"Grading cache misses: {cache_misses}")

            if cache_misses > 1:
                print("✓ Multiple fresh LLM grading calls detected")
                print(
                    "  These should have run concurrently with parallel implementation"
                )

    else:
        print(f"✗ Analysis failed: {response.status_code}")
        print(f"Error: {response.text}")

except Exception as e:
    total_elapsed = time.perf_counter() - start_time
    print(f"✗ Request failed: {e}")
    print(f"Elapsed time: {total_elapsed:.2f}s")
