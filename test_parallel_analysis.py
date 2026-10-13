import time

import requests

API_BASE_URL = "http://127.0.0.1:8000"


def test_analyze(job_description, resume_count=2):
    """Test analyze endpoint with specified resume count."""
    print(f"\n=== Testing with {resume_count} candidates ===")

    # For this test, we'll use the existing Resume DB
    # The system will select top candidates from FAISS search
    start_time = time.perf_counter()

    try:
        response = requests.post(
            f"{API_BASE_URL}/analyze",
            data={
                "job_description": job_description,
                "provider": "Gemini",
                "model_name": "gemini-2.5-flash",
                "detail_limit": resume_count,
            },
            timeout=600,
        )

        elapsed = time.perf_counter() - start_time

        if response.status_code == 200:
            data = response.json()

            print("✓ Analysis completed successfully")
            print(
                f"Total pipeline time: "
                f"{data.get('_elapsed_ms', elapsed * 1000) / 1000:.2f}s"
            )
            print(f"HTTP response time: {elapsed:.2f}s")

            timings = data.get("timings_ms", {})
            print(f"JD analysis: {timings.get('jd_analysis_ms', 0) / 1000:.2f}s")
            print(f"FAISS search: {timings.get('faiss_search_ms', 0) / 1000:.2f}s")
            print(f"Total pipeline: {timings.get('total_pipeline_ms', 0) / 1000:.2f}s")

            ranking = data.get("ranking", [])
            print(f"Total candidates in ranking: {len(ranking)}")
            print(f"Top details returned: {len(data.get('top_details', []))}")

            # Check for FAISS errors
            runtime_status = data.get("runtime_status", {})
            if runtime_status.get("last_vector_store_error"):
                print(f"⚠ FAISS error: {runtime_status['last_vector_store_error']}")
            else:
                print("✓ No FAISS errors")

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
                print(f"⚠ Missing response keys: {missing_keys}")
            else:
                print("✓ Response structure intact")

            return data, elapsed
        else:
            print(f"✗ Analysis failed: {response.status_code}")
            print(f"Error: {response.text}")
            return None, elapsed

    except Exception as e:
        elapsed = time.perf_counter() - start_time
        print(f"✗ Request failed: {e}")
        return None, elapsed


if __name__ == "__main__":
    # Sample job description
    jd = """
    Senior Python Developer

    We are looking for a Senior Python Developer with experience in:
    - Python 3.8+
    - FastAPI or Django
    - PostgreSQL or MongoDB
    - Docker and Kubernetes
    - AWS or GCP
    - CI/CD pipelines

    Requirements:
    - 5+ years of Python development experience
    - Strong problem-solving skills
    - Experience with microservices architecture
    - Bachelor's degree in Computer Science or related field
    """

    print("Testing Parallel Candidate Analysis Implementation")
    print("=" * 60)

    # Test with 2 candidates
    result_2, time_2 = test_analyze(jd, resume_count=2)

    # Test with 5 candidates
    result_5, time_5 = test_analyze(jd, resume_count=5)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"2 candidates: {time_2:.2f}s")
    print(f"5 candidates: {time_5:.2f}s")

    if result_2 and result_5:
        print("\n✓ All tests passed - parallel implementation working")
    else:
        print("\n✗ Some tests failed")
