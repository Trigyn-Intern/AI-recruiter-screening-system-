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
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|\[::1\]):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

initialize_project_storage_files()

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
            1 for record in records
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
            invalid_resumes.append({
                "resume_name": resume.filename,
                "error": (
                    "No readable text could be extracted. Use a text-based "
                    "PDF/DOCX or run OCR before uploading."
                ),
            })
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
            if uploaded_item else item["resume_skill_profile"]
        )
        score = calculate_match_score(item["resume_embedding"], job_description)
        record = {
            "resume_name": item["resume_name"],
            "resume_id": item["resume_id"],
            "match_score": score,
            "fit": build_fit_bucket(score),
        }
        file_cache.append({
            "record": record,
            "resume_text": resume_text,
            "resume_skill_profile": resume_skill_profile,
        })

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
        file_cache.append({
            "record": record,
            "resume_text": item["resume_text"],
            "resume_skill_profile": item["resume_skill_profile"],
        })

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
        record["resume_id"]: index
        for index, record in enumerate(detail_records)
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
        "moderate_fit": [r["resume_name"] for r in ranking if r["fit"] == "Moderate Fit"],
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

def run_review_bg(job_id: str, code: str, provider: str, model_name: str, system_prompt: str, invoke_path: str):
    def call_llm(user_prompt_text):
        # Try Gemini first (via direct REST API)
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
                payload_data = {
                    "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt_text}"}]}]
                }
                req = urllib.request.Request(
                    url, 
                    data=json.dumps(payload_data).encode("utf-8"), 
                    headers={"Content-Type": "application/json"}
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
                data=json.dumps({
                    "model": "llama3.2",
                    "prompt": f"{system_prompt}\n\n{user_prompt_text}",
                    "stream": False
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode())
                return result.get("response", "")
        except Exception as ollama_exc:
            raise Exception(f"Both Gemini and Ollama failed. Ollama error: {ollama_exc}")

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
                    full_review += f"### Review for {file_path}\n{review_text}\n\n---\n\n"
                except Exception as e:
                    full_review += f"### Review for {file_path}\nFailed to review: {str(e)}\n\n---\n\n"
            jobs_db[job_id] = {"status": "completed", "review": full_review.strip(), "error": None}
        else:
            user_prompt_text = f"Please review the following code:\n\n```\n{code}\n```"
            try:
                review_text = call_llm(user_prompt_text)
                jobs_db[job_id] = {"status": "completed", "review": review_text, "error": None}
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
            ".code-review/invoke.txt"
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
            ".code-review/invoke.txt"
        )
        result = jobs_db.get(job_id)
        if result and result["status"] == "completed":
            return {"review": result["review"]}
        else:
            raise HTTPException(status_code=500, detail=(result["error"] if result else "Review failed"))


@api.get("/api/review/status/{job_id}")
async def get_review_status(job_id: str):
    job = jobs_db.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
