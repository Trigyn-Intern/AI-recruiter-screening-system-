import io
import os
import time
import asyncio
import json
import uuid
import urllib.request
import urllib.error
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    from google import genai
except ImportError:
    genai = None

from dotenv import load_dotenv
import pathlib

_env_path = pathlib.Path(__file__).resolve().parent / "backend" / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

from backend import (  # noqa: E402
    AI_PROVIDER_OPTIONS,
    GEMINI_MODEL_OPTIONS,
    OLLAMA_MODEL_OPTIONS,
    analyze_candidate_detail,
    analyze_job_description_cached as analyze_job_description,
    clear_runtime_status,
    display_value,
    extract_text,
    ensure_candidate_grading,
    get_configuration,
    get_indexed_resume_analysis_records,
    get_or_create_resume_embedding,
    get_resume_database_records,
    get_resume_id,
    get_resume_skill_profile,
    get_runtime_status,
    initialize_project_storage_files,
    calculate_match_score,
    persist_analysis_session,
    reset_configuration,
    update_configuration,
    validate_upload,
)

api = FastAPI(title="Resume Analyzer API")

api.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://[::1]:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://[::1]:5174",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|\[::1\]):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

initialize_project_storage_files()

# Serve the reports directory so iframe can load HTML reports with their
# bundled CSS / JS assets (coverage HTML, Lighthouse, etc.).
_REPORTS_DIR = pathlib.Path(__file__).resolve().parent / "reports"
_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
api.mount("/reports-static", StaticFiles(directory=str(_REPORTS_DIR)), name="reports-static")

# Bound concurrent in-flight analyze calls per worker so one slow LLM
# call can't starve the rest. ANALYZE_MAX_INFLIGHT is read from env in
# start-app.ps1 (default 4) and ANALYZE_TIMEOUT_S caps each call.
ANALYZE_MAX_INFLIGHT = int(os.environ.get("ANALYZE_MAX_INFLIGHT", "4"))
ANALYZE_TIMEOUT_S = float(os.environ.get("ANALYZE_TIMEOUT_S", "90"))
_analyze_sem = asyncio.Semaphore(ANALYZE_MAX_INFLIGHT)


class CodeReviewRequest(BaseModel):
    code: str
    provider: Optional[str] = "Gemini"
    model_name: Optional[str] = "gemini-2.5-flash"
    background: Optional[bool] = False


class InMemoryUpload(io.BytesIO):
    def __init__(self, content, name):
        super().__init__(content)
        self.name = name


def build_fit_bucket(score):
    if score >= 70:
        return "Good Fit"
    if score >= 50:
        return "Moderate Fit"
    return "Bad Fit"


def serialize_jd_info(jd_info):
    return {
        "experience": display_value(jd_info.get("experience")),
        "primary_skills": display_value(jd_info.get("primary_skills")),
        "secondary_skills": display_value(jd_info.get("secondary_skills")),
        "education": display_value(jd_info.get("education")),
    }


@api.get("/health")
def health():
    return {"status": "ok"}


@api.get("/models")
def models():
    return {
        "providers": AI_PROVIDER_OPTIONS,
        "ollama_models": OLLAMA_MODEL_OPTIONS,
        "gemini_models": GEMINI_MODEL_OPTIONS,
    }


@api.get("/configuration")
def configuration():
    return {
        "configuration": get_configuration(),
        "providers": AI_PROVIDER_OPTIONS,
        "ollama_models": OLLAMA_MODEL_OPTIONS,
        "gemini_models": GEMINI_MODEL_OPTIONS,
    }


@api.get("/resume-db")
def resume_database():
    records = get_resume_database_records()
    return {
        "records": records,
        "total": len(records),
        "fully_indexed": sum(
            1
            for record in records
            if record["embedding_indexed"] and record["skills_indexed"]
        ),
        "embedding_indexed": sum(
            1 for record in records if record["embedding_indexed"]
        ),
    }


@api.put("/configuration")
def save_configuration(config: dict):
    return {"configuration": update_configuration(config)}


@api.post("/configuration/reset")
def reset_saved_configuration():
    return {"configuration": reset_configuration()}


@api.post("/analyze")
async def analyze(
    job_description: str = Form(...),
    provider: str = Form("Gemini"),
    model_name: str = Form("gemini-2.5-flash"),
    detail_limit: int = Form(5),
    resumes: list[UploadFile] | None = File(None),
):
    """Concurrency-safe analyze endpoint.

    The heavy analyzer pipeline runs on a worker thread via
    asyncio.to_thread so the event loop stays responsive. The
    _analyze_sem semaphore caps concurrent in-flight analyses per
    worker; ANALYZE_TIMEOUT_S is a hard wall-clock limit that turns
    runaway LLM calls into 504s instead of 60s+ waits.
    """
    started = time.perf_counter()
    try:
        async with asyncio.timeout(ANALYZE_TIMEOUT_S):
            async with _analyze_sem:
                result = await asyncio.to_thread(
                    _run_analyze_blocking,
                    job_description,
                    provider,
                    model_name,
                    detail_limit,
                    resumes,
                )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="analyze timed out")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"analyze failed: {exc}") from exc

    result = dict(result)
    result["_elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    return result


def _run_analyze_blocking(
    job_description: str,
    provider: str,
    model_name: str,
    detail_limit: int,
    resumes: list[UploadFile] | None,
) -> dict:
    """Synchronous analyzer pipeline. Runs in a worker thread so the
    FastAPI event loop is not blocked while LLM calls are in flight."""
    clear_runtime_status()

    if provider not in AI_PROVIDER_OPTIONS:
        raise HTTPException(status_code=400, detail="Unsupported provider.")

    if not job_description.strip():
        raise HTTPException(
            status_code=400,
            detail="Job description is required.",
        )

    detail_limit = max(1, min(int(detail_limit), 50))

    jd_info = analyze_job_description(
        job_description,
        model_name=model_name,
        provider=provider,
    )

    invalid_resumes = []
    uploaded_records = {}

    for resume in resumes or []:
        content = resume.file.read()
        resume_file = InMemoryUpload(content, resume.filename)
        is_valid, message = validate_upload(resume_file)

        if not is_valid:
            invalid_resumes.append({"resume_name": resume.filename, "error": message})
            continue

        resume_id = get_resume_id(resume_file)
        resume_text = extract_text(resume_file)

        if not resume_text.strip():
            invalid_resumes.append(
                {
                    "resume_name": resume.filename,
                    "error": (
                        "No readable text could be extracted. Use a text-based "
                        "PDF/DOCX or run OCR before uploading."
                    ),
                }
            )
            continue

        resume_embedding = get_or_create_resume_embedding(
            resume_id,
            resume.filename,
            resume_text,
        )
        resume_skill_profile = get_resume_skill_profile(
            resume_id,
            resume.filename,
            resume_text,
        )
        uploaded_records[resume_id] = {
            "resume_id": resume_id,
            "resume_name": resume.filename,
            "resume_text": resume_text,
            "resume_embedding": resume_embedding,
            "resume_skill_profile": resume_skill_profile,
        }

    file_cache = []
    indexed_resume_ids = set()

    for item in get_indexed_resume_analysis_records():
        indexed_resume_ids.add(item["resume_id"])
        uploaded_item = uploaded_records.get(item["resume_id"])
        resume_text = (
            uploaded_item["resume_text"] if uploaded_item else item["resume_text"]
        )
        resume_skill_profile = (
            uploaded_item["resume_skill_profile"]
            if uploaded_item
            else item["resume_skill_profile"]
        )
        score = calculate_match_score(item["resume_embedding"], job_description)
        record = {
            "resume_name": item["resume_name"],
            "resume_id": item["resume_id"],
            "match_score": score,
            "fit": build_fit_bucket(score),
        }
        file_cache.append(
            {
                "record": record,
                "resume_text": resume_text,
                "resume_skill_profile": resume_skill_profile,
            }
        )

    for resume_id, item in uploaded_records.items():
        if resume_id in indexed_resume_ids:
            continue
        score = calculate_match_score(item["resume_embedding"], job_description)
        record = {
            "resume_name": item["resume_name"],
            "resume_id": resume_id,
            "match_score": score,
            "fit": build_fit_bucket(score),
        }
        file_cache.append(
            {
                "record": record,
                "resume_text": item["resume_text"],
                "resume_skill_profile": item["resume_skill_profile"],
            }
        )

    if not file_cache:
        raise HTTPException(
            status_code=400,
            detail=(
                "Resume DB is empty. Upload at least one PDF or DOCX resume "
                "to create the index."
            ),
        )

    valid_records = [item["record"] for item in file_cache]
    ranking = sorted(valid_records, key=lambda item: item["match_score"], reverse=True)
    detail_records = ranking[:detail_limit]
    detail_ids = {record["resume_id"] for record in detail_records}
    detail_order = {
        record["resume_id"]: index for index, record in enumerate(detail_records)
    }
    top_details = []

    for item in file_cache:
        record = item["record"]
        if record["resume_id"] not in detail_ids:
            continue
        detail = analyze_candidate_detail(
            item["resume_text"],
            job_description,
            record["match_score"],
            model_name=model_name,
            resume_skill_profile=item["resume_skill_profile"],
            provider=provider,
            job_skill_requirements=jd_info,
            resume_name=record["resume_name"],
        )
        detail = ensure_candidate_grading(
            detail,
            resume_context=item["resume_text"],
            matching_skills=detail.get("matching_skills", []),
            missing_skills=detail.get("missing_skills", []),
        )
        top_details.append({**record, **detail})

    top_details = sorted(
        top_details,
        key=lambda item: detail_order.get(item["resume_id"], 0),
    )

    categories = {
        "good_fit": [r["resume_name"] for r in ranking if r["fit"] == "Good Fit"],
        "moderate_fit": [
            r["resume_name"] for r in ranking if r["fit"] == "Moderate Fit"
        ],
        "bad_fit": [r["resume_name"] for r in ranking if r["fit"] == "Bad Fit"],
    }

    payload = {
        "job_description": job_description,
        "provider": provider,
        "model_name": model_name,
        "jd_info": jd_info,
        "file_cache": file_cache,
    }
    persist_analysis_session(payload)

    return {
        "job_description": serialize_jd_info(jd_info),
        "ranking": ranking,
        "top_details": top_details,
        "detail_limit": detail_limit,
        "categories": categories,
        "invalid_resumes": invalid_resumes,
        "runtime_status": get_runtime_status(),
    }


JOBS_FILE = "review_jobs.json"
jobs_db = {}

if os.path.exists(JOBS_FILE):
    try:
        with open(JOBS_FILE, "r", encoding="utf-8") as f:
            jobs_db = json.load(f)
    except Exception:
        pass


def save_jobs():

    try:
        with open(JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump(jobs_db, f, indent=2)
    except Exception:
        pass


def run_review_bg(
    job_id: str,
    code: str,
    provider: str,
    model_name: str,
    system_prompt: str,
    invoke_path: str,
):
    def call_llm(user_prompt_text):
        # Try Gemini first (via direct REST API)
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
                payload_data = {
                    "contents": [
                        {"parts": [{"text": f"{system_prompt}\n\n{user_prompt_text}"}]}
                    ]
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload_data).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=120) as response:
                    result = json.loads(response.read().decode())
                    return result["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as gemini_exc:
                print(f"Gemini failed ({gemini_exc}), trying Ollama...")

        # Fallback to Ollama
        ollama_host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        try:
            req = urllib.request.Request(
                f"{ollama_host}/api/generate",
                data=json.dumps(
                    {
                        "model": "llama3.2",
                        "prompt": f"{system_prompt}\n\n{user_prompt_text}",
                        "stream": False,
                    }
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode())
                return result.get("response", "")
        except Exception as ollama_exc:
            raise Exception(
                f"Both Gemini and Ollama failed. Ollama error: {ollama_exc}"
            )

    try:
        files_to_review = []
        if os.path.exists(invoke_path):
            try:
                with open(invoke_path, "r", encoding="utf-8") as f:
                    invoke_lines = f.read().splitlines()
                in_files = False
                for line in invoke_lines:
                    line = line.strip()
                    if line.startswith("Files to review"):
                        in_files = True
                        continue
                    if in_files:
                        if not line or line.startswith("Diff hash:"):
                            in_files = False
                            break
                        if os.path.exists(line) and os.path.isfile(line):
                            files_to_review.append(line)
            except Exception as e:
                print(f"Failed to read invoke.txt: {e}")

        if files_to_review:
            full_review = ""
            for file_path in files_to_review:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    file_content = f.read()
                user_prompt_text = f"Please review the following file ({file_path}):\n\n```\n{file_content}\n```"
                try:
                    review_text = call_llm(user_prompt_text)
                    full_review += (
                        f"### Review for {file_path}\n{review_text}\n\n---\n\n"
                    )
                except Exception as e:
                    full_review += f"### Review for {file_path}\nFailed to review: {str(e)}\n\n---\n\n"
            jobs_db[job_id] = {
                "status": "completed",
                "review": full_review.strip(),
                "error": None,
            }
        else:
            user_prompt_text = f"Please review the following code:\n\n```\n{code}\n```"
            try:
                review_text = call_llm(user_prompt_text)
                jobs_db[job_id] = {
                    "status": "completed",
                    "review": review_text,
                    "error": None,
                }
            except Exception as e:
                jobs_db[job_id] = {"status": "failed", "review": None, "error": str(e)}
    except Exception as e:
        jobs_db[job_id] = {"status": "failed", "review": None, "error": str(e)}
    save_jobs()


@api.post("/api/review")
async def review_code(payload: CodeReviewRequest, background_tasks: BackgroundTasks):
    # 1. Load your local skill files
    try:
        with open("skills/code-review-policy/SKILL.md", "r", encoding="utf-8") as f:
            code_review_rules = f.read()
    except FileNotFoundError:
        code_review_rules = "Perform a general code review."

    try:
        with open("skills/SECURITY_REPORT.md", "r", encoding="utf-8") as f:
            security_rules = f.read()
    except FileNotFoundError:
        security_rules = "Perform a general security review."

    # 2. Construct the prompt with rules
    system_prompt = f"""
    You are an expert software engineer and security auditor.
    Your task is to review the code submitted by the user.
    
    Adhere strictly to these policies and guidelines:
    
    === CODE REVIEW POLICY ===
    {code_review_rules}
    
    === SECURITY REVIEW POLICY ===
    {security_rules}
    """

    job_id = str(uuid.uuid4())
    jobs_db[job_id] = {"status": "processing", "review": None, "error": None}
    save_jobs()

    if payload.background:
        background_tasks.add_task(
            run_review_bg,
            job_id,
            payload.code,
            payload.provider,
            payload.model_name,
            system_prompt,
            ".code-review/invoke.txt",
        )
        return {"job_id": job_id, "status": "processing"}
    else:
        # Run synchronously for CLI/test compatibility
        run_review_bg(
            job_id,
            payload.code,
            payload.provider,
            payload.model_name,
            system_prompt,
            ".code-review/invoke.txt",
        )
        result = jobs_db.get(job_id)
        if result and result["status"] == "completed":
            return {"review": result["review"]}
        else:
            raise HTTPException(
                status_code=500, detail=(result["error"] if result else "Review failed")
            )

# ============================================================
# Report Summary endpoints
# ============================================================
# The Report Summary dashboard on the testing app (port 5174) calls
# these endpoints to discover generated HTML reports, lazily produce an
# AI summary for each one, and stream the original report file back to
# the browser. The summary is generated once via the same Gemini-first,
# Ollama-fallback LLM call the existing /api/review endpoint uses, and
# the resulting JSON is cached on disk so the page never regenerates
# unless the user explicitly asks for a refresh.

import datetime as _datetime
import hashlib as _hashlib
import re as _re

from fastapi.responses import FileResponse as _FileResponse

_REPORT_SUMMARY_DIR = (
    pathlib.Path(__file__).resolve().parent / ".ai" / "temp" / "report-summaries"
)
_REPORT_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

# Directories to scan for already-generated HTML reports. Each entry
# labels the directory, the human-readable review type, and the "kind"
# the dashboard shows as the pill color. The order in this list is the
# order the dashboard will display.
_REPORT_SCAN_DIRS = [
    {
        "dir": ".code-review",
        "kind": "code",
        "review_type": "Code Review",
    },
    {
        "dir": "skills/reports",
        "kind": "security",
        "review_type": "Security Review",
    },
    {
        "dir": "reports",
        "kind": "perf",
        "review_type": "Performance Review",
    },
    {
        "dir": "reports/ci",
        "kind": "ci",
        "review_type": "CI Report",
    },
    {
        "dir": "reports/ci/dependency-check-report",
        "kind": "security",
        "review_type": "Security Review",
    },
    {
        "dir": "reports/ci/backend-python-reports/htmlcov-python",
        "kind": "code",
        "review_type": "Code Review (Coverage)",
    },
    # Extra surface: every directory referenced by the testing dashboard's
    # REPORT_CATALOG (frontend-test/src/reportCatalog.js). The optional
    # `include_globs` filter scopes the scan to a single file even when
    # the directory holds many unrelated files.
    {
        "dir": "reports",
        "kind": "ci",
        "review_type": "CI Pipeline Summary",
        "include_globs": ["ci-summary.html"],
    },
    {
        "dir": "reports/ci",
        "kind": "ci",
        "review_type": "CI Python Coverage",
        "include_globs": ["backend-python-reports/htmlcov-python/index.html"],
    },
    {
        "dir": "reports/ci",
        "kind": "ci",
        "review_type": "CI JUnit XML",
        "include_globs": ["backend-python-reports/junit-python.xml"],
    },
    {
        "dir": "reports/ci",
        "kind": "security",
        "review_type": "OWASP Dependency-Check",
        "include_globs": ["dependency-check-report/dependency-check-report.html"],
    },
    {
        "dir": "reports/zap",
        "kind": "security",
        "review_type": "OWASP ZAP Baseline",
        "include_globs": ["zap-baseline-report.html"],
    },
    {
        "dir": "reports",
        "kind": "perf",
        "review_type": "Lighthouse Audit",
        "include_globs": ["lighthouse-report.html"],
    },
]

REPORT_SUMMARY_SYSTEM_PROMPT = (
    "You are a senior engineering reviewer summarizing an existing report.\n"
    "Produce ONLY valid JSON. No markdown. No code blocks. No prose.\n"
    "Format:\n"
    "{\n"
    '    "overall_assessment": "1-2 sentence overview of the report quality.",\n'
    '    "key_findings": ["1-5 short bullet strings"],\n'
    '    "critical_issues": ["short bullets, only high-priority issues or empty array"],\n'
    '    "medium_issues": ["short bullets, medium severity findings or empty array"],\n'
    '    "recommendations": ["actionable fix bullets, 1-5 items or empty array"],\n'
    '    "positive_observations": ["things already implemented well, 1-5 items or empty array"],\n'
    '    "final_verdict": "1-2 sentence overall quality score and conclusion."\n'
    "}\n"
    "Rules:\n"
    "- Summarize ONLY what is in the report. Do not invent issues.\n"
    "- Use 1-5 bullets per section. Leave arrays empty when there is nothing to report.\n"
    "- Keep each bullet under 160 characters.\n"
    "- Do not include markdown, headings, or prose outside the JSON.\n"
)

_HTML_TAG_RE = _re.compile(r"<[^>]+>")
_HTML_ENTITY_RE = _re.compile(r"&(amp|lt|gt|quot|nbsp|#\d+|#x[0-9a-fA-F]+);")


def _strip_html(text):
    if not text:
        return ""
    text = _HTML_TAG_RE.sub(" ", text)
    text = _HTML_ENTITY_RE.sub(" ", text)
    text = _re.sub(r"\s+", " ", text)
    return text.strip()


def _report_id_for(relative_path):
    return _hashlib.md5(relative_path.encode("utf-8")).hexdigest()[:16]


def _scan_generated_reports():
    """Discover generated reports in the known report directories.

    Entries may carry an optional `include_globs` list. When present,
    only files whose path inside the directory matches one of the globs
    are returned. This lets us point at catalog paths like
    "reports/ci/backend-python-reports/junit-python.xml" without picking
    up unrelated files in the same directory.

    Returns a list of dicts with id, name, review_type, kind, path,
    generated_date, size, and summary_exists. Sorted newest-first.
    """
    import fnmatch

    project_root = pathlib.Path(__file__).resolve().parent
    seen_ids = set()
    rows = []
    for entry in _REPORT_SCAN_DIRS:
        directory = project_root / entry["dir"]
        if not directory.exists() or not directory.is_dir():
            continue
        globs = entry.get("include_globs")

        for html_path in directory.rglob("*.html"):
            try:
                stat = html_path.stat()
            except OSError:
                continue
            if not html_path.is_file():
                continue
            try:
                relative = html_path.relative_to(project_root).as_posix()
            except ValueError:
                relative = html_path.as_posix()
            relative_in_dir = html_path.relative_to(directory).as_posix()
            if globs and not any(
                fnmatch.fnmatch(relative_in_dir, g) for g in globs
            ):
                continue
            report_id = _report_id_for(relative)
            if report_id in seen_ids:
                continue
            seen_ids.add(report_id)
            cache_path = _REPORT_SUMMARY_DIR / f"{report_id}.json"
            summary_exists = cache_path.exists()
            rows.append(
                {
                    "id": report_id,
                    "name": html_path.stem.replace("-", " ").replace("_", " ").title()
                    or html_path.name,
                    "filename": html_path.name,
                    "review_type": entry["review_type"],
                    "kind": entry["kind"],
                    "type": entry["review_type"],
                    "path": relative,
                    "generated_at": _datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(
                        timespec="seconds"
                    ),
                    "generated_date": _datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(
                        timespec="seconds"
                    ),
                    "size": stat.st_size,
                    "summary_exists": summary_exists,
                }
            )

        # Catalog paths that point at JSON / XML / TXT files (e.g. JUnit
        # XML, dependency-check report, k6 results). These are real
        # "reports" the dashboard shows, so we surface them here too.
        EXTRA_EXTS = (".json", ".xml", ".txt")
        for other_path in directory.rglob("*"):
            if other_path.suffix.lower() not in EXTRA_EXTS:
                continue
            if not other_path.is_file():
                continue
            try:
                stat = other_path.stat()
            except OSError:
                continue
            try:
                relative = other_path.relative_to(project_root).as_posix()
            except ValueError:
                relative = other_path.as_posix()
            relative_in_dir = other_path.relative_to(directory).as_posix()
            if globs and not any(
                fnmatch.fnmatch(relative_in_dir, g) for g in globs
            ):
                continue
            report_id = _report_id_for(relative)
            if report_id in seen_ids:
                continue
            seen_ids.add(report_id)
            cache_path = _REPORT_SUMMARY_DIR / f"{report_id}.json"
            summary_exists = cache_path.exists()
            rows.append(
                {
                    "id": report_id,
                    "name": other_path.stem.replace("-", " ").replace("_", " ").title()
                    or other_path.name,
                    "filename": other_path.name,
                    "review_type": entry["review_type"],
                    "kind": entry["kind"],
                    "type": entry["review_type"],
                    "path": relative,
                    "generated_at": _datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(
                        timespec="seconds"
                    ),
                    "generated_date": _datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(
                        timespec="seconds"
                    ),
                    "size": stat.st_size,
                    "summary_exists": summary_exists,
                }
            )

    rows.sort(key=lambda r: r.get("generated_date", ""), reverse=True)
    return rows


def _call_llm_for_summary(user_prompt_text):
    """Reuse the existing Gemini-first, Ollama-fallback LLM call.

    The same call pattern lives inside run_review_bg for /api/review.
    Duplicated here so the report summary endpoint can stand alone
    without touching the existing review job store.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                "gemini-2.5-flash:generateContent?key=" + api_key
            )
            payload_data = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": (
                                    REPORT_SUMMARY_SYSTEM_PROMPT
                                    + "\n\n"
                                    + user_prompt_text
                                )
                            }
                        ]
                    }
                ]
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload_data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode())
                return result["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as gemini_exc:
            print(f"Gemini failed ({gemini_exc}), trying Ollama...")

    ollama_host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    req = urllib.request.Request(
        f"{ollama_host}/api/generate",
        data=json.dumps(
            {
                "model": "llama3.2",
                "prompt": (
                    REPORT_SUMMARY_SYSTEM_PROMPT + "\n\n" + user_prompt_text
                ),
                "stream": False,
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        result = json.loads(response.read().decode())
        return result.get("response", "")


def _safe_json_loads(raw):
    """Best-effort JSON parse: try direct, then extract a code block."""
    if not raw:
        return None
    text = raw.strip()
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    match = _re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, _re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except (ValueError, TypeError):
            return None
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except (ValueError, TypeError):
            return None
    return None


@api.get("/api/report-summary")
def list_report_summaries():
    """Return every generated HTML report the dashboard should show."""
    return {"reports": _scan_generated_reports()}


@api.get("/api/report-summary/{report_id}")
def get_report_summary(report_id: str, refresh: bool = False):
    """Return the cached AI summary for one report, or generate it once."""
    reports_by_id = {r["id"]: r for r in _scan_generated_reports()}
    if report_id not in reports_by_id:
        raise HTTPException(status_code=404, detail="Report not found")
    report = reports_by_id[report_id]
    cache_path = _REPORT_SUMMARY_DIR / f"{report_id}.json"

    if cache_path.exists() and not refresh:
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            cached["cached"] = True
            return cached
        except (OSError, ValueError, TypeError):
            try:
                cache_path.unlink()
            except OSError:
                pass

    project_root = pathlib.Path(__file__).resolve().parent
    file_path = project_root / report["path"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")

    try:
        raw_html = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        raise HTTPException(
            status_code=500, detail=f"Could not read report: {exc}"
        ) from exc

    text = _strip_html(raw_html)[:20000]
    user_prompt = (
        f"Summarize the following report titled '{report['name']}'"
        f" (review type: {report['review_type']}).\n\n{text}"
    )

    try:
        llm_text = _call_llm_for_summary(user_prompt)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Summary generation failed: {exc}",
        ) from exc

    summary = _safe_json_loads(llm_text)
    if not isinstance(summary, dict):
        raise HTTPException(
            status_code=502,
            detail="LLM returned a summary that could not be parsed as JSON.",
        )

    payload = {
        "id": report["id"],
        "name": report["name"],
        "review_type": report["review_type"],
        "kind": report["kind"],
        "path": report["path"],
        "generated_date": report["generated_date"],
        "size": report["size"],
        "summary": summary,
        "cached": False,
    }
    cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


@api.get("/api/report-download/{report_id}")
def download_report(report_id: str):
    """Stream the original HTML report back as a download attachment."""
    reports_by_id = {r["id"]: r for r in _scan_generated_reports()}
    if report_id not in reports_by_id:
        raise HTTPException(status_code=404, detail="Report not found")
    report = reports_by_id[report_id]
    project_root = pathlib.Path(__file__).resolve().parent
    file_path = project_root / report["path"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    return _FileResponse(
        path=str(file_path),
        media_type="text/html",
        filename=report["filename"],
    )


@api.get("/api/report-view/{report_id}")
def view_report(report_id: str):
    """Stream the original HTML report back inline for the browser tab."""
    reports_by_id = {r["id"]: r for r in _scan_generated_reports()}
    if report_id not in reports_by_id:
        raise HTTPException(status_code=404, detail="Report not found")
    report = reports_by_id[report_id]
    project_root = pathlib.Path(__file__).resolve().parent
    file_path = project_root / report["path"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    return _FileResponse(path=str(file_path), media_type="text/html")

@api.get("/api/review/status/{job_id}")
async def get_review_status(job_id: str):
    job = jobs_db.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job



# ---- Report Summary router (chunked summaries + cache) ----
try:
    from api_report_summary import router as _report_summary_router
    api.include_router(_report_summary_router)
except Exception as _exc:
    print(f"Report summary router not loaded: {_exc}")
