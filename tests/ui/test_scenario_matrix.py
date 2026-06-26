"""Single Playwright test that drives every scenario in ``scenarios.yaml``.

This file consolidates every test that used to ship separately:

* the data-driven scenario matrix (1 Playwright run per row of
  ``tests/data/scenarios.yaml``)
* backend unit tests (extraction, validation, scoring, JSON, skills
  registry, Ollama adapter, configuration)
* integration probes that hit FastAPI directly, replacing the legacy
  ``tests/ui/test_upload.py``, ``test_jd_input.py``, ``test_rank_flow.py``.

The runner script (``tests/ui/run_scenario_matrix.py``) starts Ollama,
FastAPI, and the React dev server, then invokes pytest against this
file. CI runs pytest once and collects a single JUnit XML.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

import pytest


WEB_BASE_URL = os.environ.get("WEB_BASE_URL", "http://localhost:5173")
API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
AUTH_API_URL = os.environ.get("AUTH_API_URL", "http://localhost:4000")

DEMO_EMAIL = os.environ.get("RECRUITER_EMAIL", "qa-recruiter@example.com")
DEMO_PASSWORD = os.environ.get("RECRUITER_PASSWORD", "Recruiter!1")
DEMO_NAME = os.environ.get("RECRUITER_NAME", "QA Recruiter")

SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots"


# ============================================================
# Shared helpers
# ============================================================

def _http_json(url: str, method: str = "GET", body: Dict[str, Any] | None = None,
               token: str | None = None) -> Dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _multipart(fields: Dict[str, Any], files: List[Any]) -> tuple[bytes, str]:
    boundary = "----TestBoundary7MA4YWxkTrZu0gW"
    buffer = bytearray()
    for name, value in fields.items():
        buffer += f"--{boundary}\r\n".encode()
        buffer += f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        encoded = value.encode("utf-8") if isinstance(value, str) else value
        buffer += encoded + b"\r\n"
    for field_name, filename, content in files:
        buffer += f"--{boundary}\r\n".encode()
        buffer += (
            f'Content-Disposition: form-data; name="{field_name}"; '
            f'filename="{filename}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        buffer += content + b"\r\n"
    buffer += f"--{boundary}--\r\n".encode()
    return bytes(buffer), boundary


def _seed_recruiter_account() -> str:
    """Ensure the demo recruiter exists and return a fresh token.

    The Node auth API rejects logins with a 401 when the account doesn't
    exist yet and a 400 when the email is malformed. Treat any non-2xx on
    the first login attempt as "no account", then create one. Re-raising
    the original error if signup also fails makes debugging easier.
    """
    try:
        response = _http_json(
            f"{AUTH_API_URL}/api/auth/login",
            method="POST",
            body={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
        )
        return response["token"]
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        if error.code not in (400, 401):
            raise AssertionError(
                f"Unexpected status from /api/auth/login: {error.code} {body}"
            )

    signup_body = {
        "name": DEMO_NAME,
        "email": DEMO_EMAIL,
        "password": DEMO_PASSWORD,
        "confirmPassword": DEMO_PASSWORD,
    }
    signup_response = _http_json(
        f"{AUTH_API_URL}/api/auth/signup",
        method="POST",
        body=signup_body,
    )
    if signup_response.get("token"):
        return signup_response["token"]

    # Account was created by another run between our login and signup.
    response = _http_json(
        f"{AUTH_API_URL}/api/auth/login",
        method="POST",
        body={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
    )
    return response["token"]


def _wait_for_api(timeout_seconds: int = 60) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{API_BASE_URL}/health", timeout=5) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last_error = exc
            time.sleep(1)
    raise AssertionError(
        f"FastAPI never became reachable at {API_BASE_URL}/health "
        f"within {timeout_seconds}s. Last error: {last_error!r}"
    )


def _wait_for_web(timeout_seconds: int = 60) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{WEB_BASE_URL}/", timeout=5) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last_error = exc
            time.sleep(1)
    raise AssertionError(
        f"React web never became reachable at {WEB_BASE_URL}/ "
        f"within {timeout_seconds}s. Last error: {last_error!r}"
    )


def _switch_tab(page, tab_label: str) -> None:
    page.get_by_role("button", name=re.compile(rf"^{re.escape(tab_label)}$")).first.click()


def _set_provider_model(page, model: str) -> None:
    selects = page.locator("select")
    provider_index = None
    for i in range(selects.count()):
        options = {
            (selects.nth(i).locator("option").nth(j).inner_text() or "").strip()
            for j in range(selects.nth(i).locator("option").count())
        }
        if "Ollama" in options:
            provider_index = i
            break
    if provider_index is None:
        pytest.skip("Provider dropdown not found on the page.")
    selects.nth(provider_index).select_option("Ollama")
    page.wait_for_timeout(500)
    selects = page.locator("select")
    for i in range(selects.count()):
        options = [
            (selects.nth(i).locator("option").nth(j).get_attribute("value") or "")
            for j in range(selects.nth(i).locator("option").count())
        ]
        if model in options:
            selects.nth(i).select_option(model)
            return
    pytest.skip(f"Model '{model}' is not available in the UI dropdown.")


def _upload_resumes(page, resume_paths: List[Path]) -> None:
    page.locator("input[type='file']").set_input_files([str(p) for p in resume_paths])
    page.wait_for_timeout(500)


def _paste_job_description(page, jd_path: Path) -> None:
    page.locator("textarea").first.fill(jd_path.read_text(encoding="utf-8"))


def _read_ranking(page) -> List[Dict[str, Any]]:
    """Read rows from the ranking table. The React dashboard renders a
    ``<section>`` per card, so we locate the table inside the section that
    has both an ``<h2>Ranking</h2>`` heading and a tbody of ranking rows."""
    table = page.locator("section:has(h2:text-is('Ranking')) table tbody tr")
    count = table.count()
    results: List[Dict[str, Any]] = []
    for index in range(count):
        cells = table.nth(index).locator("td")
        results.append({
            "resume": (cells.nth(0).inner_text() or "").strip(),
            "score": (cells.nth(1).inner_text() or "").strip(),
            "fit": (cells.nth(2).inner_text() or "").strip(),
        })
    return results


def _score_value(score_text: str) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)", score_text or "")
    return float(match.group(1)) if match else 0.0


# ============================================================
# The single browser scenario-matrix test
# ============================================================

@pytest.mark.ui
def test_scenario_matrix(page, scenario, data_root):
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    jd_path = (data_root / scenario["jd_file"]).resolve()
    resume_paths = [(data_root / name).resolve() for name in scenario["resume_files"]]
    for path in [jd_path, *resume_paths]:
        if not path.exists():
            pytest.skip(f"Required data file missing: {path}")

    _wait_for_api()
    _wait_for_web()
    token = _seed_recruiter_account()

    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(WEB_BASE_URL, wait_until="domcontentloaded")
    page.evaluate(
        "([token, user]) => {"
        "  localStorage.setItem('recruiter.token', token);"
        "  localStorage.setItem('recruiter.user', JSON.stringify(user));"
        "}",
        [token, {"name": DEMO_NAME, "email": DEMO_EMAIL}],
    )
    page.goto(f"{WEB_BASE_URL}/dashboard", wait_until="networkidle")

    _switch_tab(page, "Configurations")
    _set_provider_model(page, scenario["model"])
    _switch_tab(page, "Analyzer")
    _set_provider_model(page, scenario["model"])
    _upload_resumes(page, resume_paths)
    _paste_job_description(page, jd_path)

    page.get_by_role("button", name=re.compile(r"^Analyze$")).click()

    # Wait for the Ranking table to actually have rows; this avoids the
    # strict-mode collision between the wrapper results panel and the
    # inner <section> that contains the <h2>Ranking</h2> + table.
    ranking_table = page.locator(
        "section:has(h2:text-is('Ranking')) table tbody tr"
    )
    ranking_table.first.wait_for(timeout=180_000)
    page.wait_for_timeout(500)

    ranking = _read_ranking(page)
    assert ranking, "Ranking table was empty after analysis."

    top = ranking[0]
    top_score = _score_value(top["score"])
    page.screenshot(
        path=str(SCREENSHOT_DIR / f"{scenario['id']}.png"),
        full_page=True,
    )

    expected_min = scenario.get("expected_min_score")
    if expected_min is not None:
        assert top_score >= float(expected_min), (
            f"Scenario '{scenario['id']}': top score {top_score} "
            f"< expected minimum {expected_min}. Ranking: {ranking}"
        )

    expected_resume = scenario.get("expected_resume")
    if expected_resume:
        expected_name = Path(expected_resume).name
        assert top["resume"] == expected_name, (
            f"Scenario '{scenario['id']}': expected top resume '{expected_name}', "
            f"got '{top['resume']}'. Ranking: {ranking}"
        )


# ============================================================
# Backend unit tests
# ============================================================

@pytest.mark.backend
def test_safe_json_extract_parses_embedded_json():
    from backend import safe_json_extract

    assert safe_json_extract('hello {"a": 1} world') == {"a": 1}
    assert safe_json_extract('not json') is None


@pytest.mark.backend
def test_validate_upload_accepts_pdf_and_rejects_exe_and_oversized():
    import io
    from backend import validate_upload

    pdf = io.BytesIO(b"%PDF-1.4 test content")
    pdf.name = "resume.pdf"
    assert validate_upload(pdf)[0] is True

    fake_pdf = io.BytesIO(b"NOTPDF")
    fake_pdf.name = "resume.pdf"
    assert validate_upload(fake_pdf)[0] is False

    exe = io.BytesIO(b"random")
    exe.name = "malware.exe"
    ok, msg = validate_upload(exe)
    assert ok is False and "Unsupported" in msg

    big = io.BytesIO(b"x" * (11 * 1024 * 1024))
    big.name = "large.pdf"
    assert validate_upload(big)[0] is False


@pytest.mark.backend
def test_extract_text_returns_empty_for_unsupported_extension():
    import io
    from backend import extract_text

    fake = io.BytesIO(b"abc")
    fake.name = "test.exe"
    assert extract_text(fake) == ""


@pytest.mark.backend
def test_calculate_match_score_is_float_in_range(mocker):
    """Stub the embedding encoder and cosine similarity so we exercise
    ``calculate_match_score`` offline (no model loaded)."""
    import numpy as np

    def fake_encode(text, prefix):
        seed = abs(hash(text)) % 1000
        return np.asarray([[seed, seed + 1, seed + 2, seed + 3]], dtype="float32")

    mocker.patch("backend.encode_text_embedding", side_effect=fake_encode)
    mocker.patch("backend.cosine_similarity", return_value=[[0.8]])

    from backend import calculate_match_score

    score = calculate_match_score("Python ML resume", "Python ML job")
    assert isinstance(score, float)
    assert 0 <= score <= 100


@pytest.mark.backend
def test_get_or_create_resume_embedding_uses_cached_faiss_row(mocker):
    """When FAISS already has the resume the function returns the cached
    (1, 1024) ndarray and must not call the embedding encoder."""
    import numpy as np
    from backend import EMBEDDING_DIMENSION, get_or_create_resume_embedding

    cached_vector = np.asarray([0.1] * EMBEDDING_DIMENSION, dtype="float32")
    index = mocker.Mock()
    index.reconstruct.return_value = cached_vector
    mocker.patch(
        "backend.load_resume_vector_store",
        return_value=(index, [{
            "resume_id": "resume-1",
            "resume_name": "resume.pdf",
            "faiss_row": 4,
        }]),
    )
    mock_encode = mocker.patch("backend.encode_text_embedding")

    result = get_or_create_resume_embedding("resume-1", "resume.pdf", "resume text")

    np.testing.assert_array_equal(
        result,
        np.asarray([cached_vector], dtype="float32"),
    )
    index.reconstruct.assert_called_once_with(4)
    mock_encode.assert_not_called()


@pytest.mark.backend
def test_skills_registry_discovers_expected_skills():
    from backend_skills import discover, get_skill, list_skills

    skills = discover()
    assert {
        "jd-analyzer",
        "skill-gap-analyzer",
        "candidate-explainer",
        "resume-skill-extractor",
    }.issubset(skills.keys())

    jd_skill = get_skill("jd-analyzer")
    assert jd_skill.config_key == "jd_prompt_template"
    assert any(input.name == "job_text" for input in jd_skill.inputs)
    assert list_skills(), "list_skills() should return at least one summary"


@pytest.mark.backend
def test_safe_ollama_json_success_and_fallback(mocker):
    from backend import JD_SCHEMA, safe_ollama_json

    content = json.dumps({
        "experience": "3 years",
        "primary_skills": ["Python"],
        "secondary_skills": ["SQL"],
        "education": "BTech",
    })
    mocker.patch(
        "backend.ollama.chat",
        return_value={"message": {"content": content}},
    )
    result = safe_ollama_json("prompt", JD_SCHEMA, {})
    assert result["experience"] == "3 years"
    assert "primary_skills" in result

    mocker.patch(
        "backend.ollama.chat",
        return_value={"message": {"content": '{"wrong": "format"}'}},
    )
    fallback = {"fallback": True}
    assert safe_ollama_json("prompt", JD_SCHEMA, fallback) == fallback


@pytest.mark.backend
def test_get_model_options_handles_ollama_and_gemini(mocker):
    from backend import (
        DEFAULT_OLLAMA_MODEL,
        GEMINI_MODEL_OPTIONS,
        OLLAMA_MODEL_OPTIONS,
        get_model_options,
    )

    mocker.patch(
        "backend.get_available_ollama_models",
        return_value=["custom-local-model", DEFAULT_OLLAMA_MODEL],
    )
    options = get_model_options("Ollama")
    assert options[0] == "custom-local-model"
    assert DEFAULT_OLLAMA_MODEL in options
    assert len(options) == len(set(options))

    mocker.patch("backend.get_available_ollama_models", return_value=[])
    assert get_model_options("Ollama") == OLLAMA_MODEL_OPTIONS

    assert get_model_options("Gemini") == GEMINI_MODEL_OPTIONS


@pytest.mark.backend
def test_analyze_candidate_detail_uses_cache_when_present(mocker):
    from backend import analyze_candidate_detail

    cached = {
        "matching_skills": ["Python"],
        "missing_skills": [],
        "justification": "Cached.",
    }
    mocker.patch("backend.get_selected_provider", return_value="Gemini")
    mocker.patch("backend.get_selected_model", return_value="gemini-2.5-flash")
    mocker.patch("backend.get_ai_cache", return_value={
        "candidate_detail|Gemini|gemini-2.5-flash|90|resume|job": cached,
    })
    mock_ai = mocker.patch("backend.safe_ai_json")

    result = analyze_candidate_detail(
        "resume", "job", 90, model_name="gemini-2.5-flash",
    )
    assert result == cached
    mock_ai.assert_not_called()


@pytest.mark.backend
def test_normalize_configuration_prefills_blank_prompts():
    from backend import DEFAULT_JD_PROMPT_TEMPLATE, normalize_configuration

    normalized = normalize_configuration({
        "ai_provider": "Gemini",
        "jd_prompt_template": "",
    })
    assert normalized["ai_provider"] == "Gemini"
    assert normalized["jd_prompt_template"] == DEFAULT_JD_PROMPT_TEMPLATE


# ============================================================
# Integration probes (FastAPI direct, no React dev server required)
# ============================================================

@pytest.mark.integration
def test_api_health_is_reachable():
    with urllib.request.urlopen(f"{API_BASE_URL}/health", timeout=5) as response:
        assert response.status == 200


@pytest.mark.integration
def test_models_endpoint_lists_providers():
    with urllib.request.urlopen(f"{API_BASE_URL}/models", timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
    assert "providers" in payload
    assert "Gemini" in payload["providers"]
    assert "Ollama" in payload["providers"]
    assert payload["ollama_models"]
    assert payload["gemini_models"]


@pytest.mark.integration
def test_resume_upload_via_analyze_endpoint(scenario, data_root):
    """Replaces tests/ui/test_upload.py."""
    jd_text = (data_root / scenario["jd_file"]).read_text(encoding="utf-8")
    files = []
    for resume_name in scenario["resume_files"]:
        resume_path = data_root / resume_name
        files.append(("resumes", resume_path.name, resume_path.read_bytes()))

    body, boundary = _multipart(
        {
            "job_description": jd_text,
            "provider": "Ollama",
            "model_name": scenario["model"],
        },
        files,
    )
    request = urllib.request.Request(
        f"{API_BASE_URL}/analyze",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))

    assert payload["ranking"], "Ranking should contain at least one candidate."
    assert all("match_score" in row for row in payload["ranking"])
    assert sum("error" not in row for row in payload["ranking"]) >= 1


@pytest.mark.integration
def test_jd_input_required_field_via_analyze():
    """Replaces tests/ui/test_jd_input.py: empty JD must be rejected.

    FastAPI returns 422 (Unprocessable Content) when a required form
    field is missing entirely, and the ``/analyze`` handler returns 400
    when the field is present but empty. Accept either - the important
    thing is that a recruiter gets a clear error instead of a successful
    analysis with a blank job description.
    """
    body, boundary = _multipart(
        {"job_description": "", "provider": "Ollama", "model_name": "llama3.2"},
        [("resumes", "resume.pdf", b"%PDF-1.4 stub")],
    )
    request = urllib.request.Request(
        f"{API_BASE_URL}/analyze",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        urllib.request.urlopen(request, timeout=10)
    except urllib.error.HTTPError as error:
        assert error.code in (400, 422), (
            f"Expected 400/422 for empty JD, got {error.code}"
        )
        error_body = error.read()
        assert (
            b"job_description" in error_body
            or b"Job description" in error_body
        ), f"Error body should mention the job_description field: {error_body!r}"
    else:
        raise AssertionError("Empty JD should have produced an error response.")


@pytest.mark.integration
def test_ranking_flow_orders_candidates_by_score(scenario, data_root):
    """Replaces tests/ui/test_rank_flow.py."""
    jd_text = (data_root / scenario["jd_file"]).read_text(encoding="utf-8")
    files = [
        ("resumes", path.name, path.read_bytes())
        for path in (data_root / name for name in scenario["resume_files"])
    ]
    body, boundary = _multipart(
        {
            "job_description": jd_text,
            "provider": "Ollama",
            "model_name": scenario["model"],
        },
        files,
    )
    request = urllib.request.Request(
        f"{API_BASE_URL}/analyze",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))

    scores = [row["match_score"] for row in payload["ranking"] if "match_score" in row]
    assert scores == sorted(scores, reverse=True), (
        f"Ranking not sorted descending: {scores}"
    )
