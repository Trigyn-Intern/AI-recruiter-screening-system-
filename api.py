import asyncio
import hashlib
import html
import io
import json
import logging
import math
import os
import re
import threading
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

try:
    from google import genai
except ImportError:
    genai = None

import pathlib

from dotenv import load_dotenv

_env_path = pathlib.Path(__file__).resolve().parent / "backend" / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

logger = logging.getLogger("api")

from assessment_auth import (
    issue_assessment_token,
    require_assessment_access,
    require_recruiter,
    validate_identifier,
)
from backend import (
    AI_PROVIDER_OPTIONS,
    GEMINI_MODEL_OPTIONS,
    LINKEDIN_VERIFICATION_FALLBACK,
    OLLAMA_MODEL_OPTIONS,
    RESUME_CHUNKS_PATH,
    add_candidate_to_shortlist,
    analyze_candidate_detail,
    calculate_match_score,
    clear_runtime_status,
    compare_selected_candidates,
    compare_selected_candidates_gpt4,
    create_shortlist,
    delete_shortlist,
    display_value,
    encode_text_embedding,
    ensure_candidate_grading,
    extract_text,
    faiss_index_lookup,
    faiss_semantic_search,
    fetch_captapi_linkedin_profile,
    generate_evidence_assessment,
    get_active_resume_db_records,
    get_configuration,
    get_github_evidence,
    get_or_create_resume_embedding,
    get_resume_database_records,
    get_resume_id,
    get_resume_skill_profile,
    get_runtime_status,
    get_shortlist,
    get_shortlists,
    get_user_shortlists,
    initialize_project_storage_files,
    persist_analysis_session,
    read_json_file,
    remove_candidate_from_shortlist,
    reset_configuration,
    update_configuration,
    update_shortlist_status,
    validate_upload,
    verify_candidate_exists,
    verify_github_evidence_against_resume,
    verify_linkedin_evidence_against_resume,
    verify_shortlist_ownership,
)
from backend import (
    analyze_job_description_cached as analyze_job_description,
)

ASSESSMENT_EVIDENCE_DIR = (
    pathlib.Path(__file__).resolve().parent / "assessment_evidence"
)
ASSESSMENT_EVIDENCE_METADATA_PATH = ASSESSMENT_EVIDENCE_DIR / "metadata.json"
EVIDENCE_EVENT_TYPES = {
    "tab_hidden",
    "looking_away",
    "multiple_faces_detected",
    "copy_attempt",
    "paste_attempt",
}
MAX_EVIDENCE_BYTES = 8 * 1024 * 1024
MAX_EVENTS_PER_MINUTE = 120
_evidence_lock = threading.Lock()
_event_rate_state = {}


def _read_evidence_metadata():
    if not ASSESSMENT_EVIDENCE_METADATA_PATH.exists():
        return {}
    try:
        with ASSESSMENT_EVIDENCE_METADATA_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_evidence_metadata(metadata):
    ASSESSMENT_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = ASSESSMENT_EVIDENCE_METADATA_PATH.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
    temp_path.replace(ASSESSMENT_EVIDENCE_METADATA_PATH)


def _assessment_record_for(assessment_id):
    from backend_question_generator import get_assessment_questions

    return get_assessment_questions(assessment_id)


def _user_owns_assessment(user_id, assessment_id):
    record = _assessment_record_for(assessment_id)
    candidate_id = record.get("candidate_id") if record else None
    if not candidate_id:
        return False

    for shortlist in get_shortlists():
        if str(shortlist.get("user_id")) != str(user_id):
            continue
        candidates = (
            shortlist.get("candidates") or shortlist.get("shortlisted_candidates") or []
        )
        if any(
            str(candidate.get("resume_id")) == str(candidate_id)
            for candidate in candidates
        ):
            return True
    return False


def _validate_event_timestamp(timestamp):
    try:
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid event timestamp.") from exc
    if parsed.tzinfo is None:
        raise HTTPException(
            status_code=400, detail="Event timestamp must include a timezone."
        )
    age_seconds = (datetime.now(parsed.tzinfo) - parsed).total_seconds()
    if age_seconds < -300 or age_seconds > 86400:
        raise HTTPException(
            status_code=400, detail="Event timestamp is outside the allowed window."
        )
    return parsed.isoformat()


def _validate_duration(duration_seconds, maximum=14400):
    if (
        duration_seconds is None
        or not math.isfinite(duration_seconds)
        or not 0 <= duration_seconds <= maximum
    ):
        raise HTTPException(status_code=400, detail="Invalid event duration.")
    return round(duration_seconds, 2)


def _validate_evidence_bytes(evidence_type, content_type, clip_bytes):
    expected_type = (
        "image/png" if evidence_type == "screen_screenshot" else "video/webm"
    )
    if content_type.split(";", 1)[0].strip().lower() != expected_type:
        raise HTTPException(
            status_code=400, detail="Evidence content type is not allowed."
        )
    if evidence_type == "screen_screenshot" and not clip_bytes.startswith(
        b"\x89PNG\r\n\x1a\n"
    ):
        raise HTTPException(
            status_code=400, detail="Evidence is not a valid PNG image."
        )
    if evidence_type == "screen_video" and not clip_bytes.startswith(
        b"\x1a\x45\xdf\xa3"
    ):
        raise HTTPException(
            status_code=400, detail="Evidence is not a valid WebM video."
        )


def _enforce_event_rate(rate_key, event_count):
    now = time.monotonic()
    with _evidence_lock:
        recent = [
            timestamp
            for timestamp in _event_rate_state.get(rate_key, [])
            if now - timestamp < 60
        ]
        if len(recent) + event_count > MAX_EVENTS_PER_MINUTE:
            raise HTTPException(
                status_code=429, detail="Behavior event rate limit exceeded."
            )
        recent.extend([now] * event_count)
        _event_rate_state[rate_key] = recent


def _assert_evidence_path(assessment_id, evidence_id, extension):
    assessment_id = validate_identifier(assessment_id, "assessment ID")
    evidence_id = validate_identifier(evidence_id, "evidence ID")
    if extension not in {"png", "webm"}:
        raise HTTPException(status_code=400, detail="Invalid evidence file extension.")

    # Strict basename defense-in-depth: filenames and directories must not have path separators or parent traversal
    clean_assessment_dir = os.path.basename(assessment_id.strip())
    clean_evidence_name = os.path.basename(evidence_id.strip())
    if clean_assessment_dir != assessment_id or clean_evidence_name != evidence_id:
        raise HTTPException(status_code=400, detail="Invalid evidence path.")
    if not clean_assessment_dir or clean_assessment_dir in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid evidence path.")
    clean_filename = f"{clean_evidence_name}.{extension}"
    if not clean_filename or clean_filename.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid evidence path.")

    # Canonical base directory check
    root_str = os.path.realpath(str(ASSESSMENT_EVIDENCE_DIR.resolve()))
    target_dir_str = os.path.realpath(os.path.join(root_str, clean_assessment_dir))
    if not target_dir_str.startswith(root_str + os.sep) or target_dir_str == root_str:
        raise HTTPException(status_code=400, detail="Invalid evidence path.")
    if os.path.commonpath([root_str, target_dir_str]) != root_str:
        raise HTTPException(status_code=400, detail="Invalid evidence path.")

    file_path_str = os.path.realpath(os.path.join(target_dir_str, clean_filename))
    if not file_path_str.startswith(target_dir_str + os.sep):
        raise HTTPException(status_code=400, detail="Invalid evidence path.")
    if os.path.commonpath([target_dir_str, file_path_str]) != target_dir_str:
        raise HTTPException(status_code=400, detail="Invalid evidence path.")

    # Return validated Path object contained strictly inside target_dir
    path = pathlib.Path(file_path_str)
    root = pathlib.Path(root_str)
    target_dir = pathlib.Path(target_dir_str)
    if not path.is_relative_to(target_dir) or not path.is_relative_to(root):
        raise HTTPException(status_code=400, detail="Invalid evidence path.")
    return path


# Helper function for PDF generation (local to avoid backend dependency)
def _pdf_display_value(value):
    """Safe display value helper for PDF generation."""
    if value is None:
        return "Not specified"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


# PDF generation function defined locally to avoid backend import issues
def generate_comparison_report_pdf(
    evidence_assessment, gpt4_result, gpt5_result, job_description
):
    """Generate a PDF report for candidate comparison."""
    try:
        from io import BytesIO

        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer
    except ImportError as e:
        print(f"[PDF GENERATION ERROR] ReportLab import failed: {e}")
        return b""

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#2c3e50"),
        spaceAfter=30,
    )

    section_style = ParagraphStyle(
        "CustomSection",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor("#34495e"),
        spaceAfter=12,
    )

    subsection_style = ParagraphStyle(
        "CustomSubsection",
        parent=styles["Heading3"],
        fontSize=12,
        textColor=colors.HexColor("#7f8c8d"),
        spaceAfter=8,
    )

    body_style = ParagraphStyle(
        "CustomBody",
        parent=styles["BodyText"],
        fontSize=10,
        spaceAfter=6,
    )

    content = []

    # Title
    content.append(Paragraph("Candidate Comparison Report", title_style))
    content.append(Spacer(1, 0.2 * inch))

    # Candidates being compared
    if gpt5_result and gpt5_result.get("candidates"):
        candidates = gpt5_result["candidates"]
        candidate_names = [c.get("candidate_name", "Unknown") for c in candidates]
        content.append(
            Paragraph(f"Candidates Compared: {', '.join(candidate_names)}", body_style)
        )
        content.append(Spacer(1, 0.2 * inch))
    elif gpt4_result and gpt4_result.get("candidates"):
        candidates = gpt4_result["candidates"]
        candidate_names = [c.get("candidate_name", "Unknown") for c in candidates]
        content.append(
            Paragraph(f"Candidates Compared: {', '.join(candidate_names)}", body_style)
        )
        content.append(Spacer(1, 0.2 * inch))

    # Job Description Summary
    if job_description:
        content.append(Paragraph("Job Description", section_style))
        jd_text = (
            f"Experience: {_pdf_display_value(job_description.get('experience'))}<br/>"
        )
        jd_text += f"Primary Skills: {_pdf_display_value(job_description.get('primary_skills'))}<br/>"
        jd_text += f"Secondary Skills: {_pdf_display_value(job_description.get('secondary_skills'))}<br/>"
        jd_text += f"Education: {_pdf_display_value(job_description.get('education'))}"
        content.append(Paragraph(jd_text, body_style))
        content.append(Spacer(1, 0.3 * inch))

    # AI Evidence Assessment
    if evidence_assessment:
        content.append(Paragraph("AI Evidence Assessment", section_style))

        if evidence_assessment.get("strongest_candidate"):
            content.append(Paragraph("Strongest Candidate", subsection_style))
            content.append(
                Paragraph(
                    f"<b>{_pdf_display_value(evidence_assessment['strongest_candidate'])}</b>",
                    body_style,
                )
            )
            content.append(Spacer(1, 0.1 * inch))

        if evidence_assessment.get("assessment_summary"):
            content.append(Paragraph("Assessment Summary", subsection_style))
            content.append(
                Paragraph(
                    _pdf_display_value(evidence_assessment["assessment_summary"]),
                    body_style,
                )
            )
            content.append(Spacer(1, 0.1 * inch))

        if evidence_assessment.get("supporting_points"):
            content.append(Paragraph("Supporting Points", subsection_style))
            for point in evidence_assessment["supporting_points"]:
                content.append(Paragraph(f"• {_pdf_display_value(point)}", body_style))
            content.append(Spacer(1, 0.3 * inch))

    # GPT-4 Assessment
    if gpt4_result:
        content.append(PageBreak())
        content.append(Paragraph("GPT-4 Assessment", section_style))

        if gpt4_result.get("comparison_summary"):
            content.append(Paragraph("Comparison Summary", subsection_style))
            content.append(
                Paragraph(
                    _pdf_display_value(gpt4_result["comparison_summary"]), body_style
                )
            )
            content.append(Spacer(1, 0.2 * inch))

        # Candidate details
        if gpt4_result.get("candidates"):
            for candidate in gpt4_result["candidates"]:
                candidate_name = candidate.get("candidate_name", "Unknown")
                content.append(
                    Paragraph(f"Candidate: {candidate_name}", subsection_style)
                )

                if candidate.get("strengths"):
                    content.append(Paragraph("Strengths:", body_style))
                    for strength in candidate["strengths"]:
                        content.append(
                            Paragraph(f"  • {_pdf_display_value(strength)}", body_style)
                        )

                if candidate.get("gaps"):
                    content.append(Paragraph("Gaps:", body_style))
                    for gap in candidate["gaps"]:
                        content.append(
                            Paragraph(f"  • {_pdf_display_value(gap)}", body_style)
                        )

                if candidate.get("jd_coverage"):
                    content.append(Paragraph("JD Coverage:", body_style))
                    for coverage in candidate["jd_coverage"]:
                        content.append(
                            Paragraph(f"  • {_pdf_display_value(coverage)}", body_style)
                        )

                if candidate.get("evidence"):
                    content.append(Paragraph("Evidence:", body_style))
                    for evidence in candidate["evidence"]:
                        content.append(
                            Paragraph(f"  • {_pdf_display_value(evidence)}", body_style)
                        )

                content.append(Spacer(1, 0.2 * inch))

        # Comparisons
        if gpt4_result.get("comparisons"):
            content.append(Paragraph("Detailed Comparisons", subsection_style))
            for comparison in gpt4_result["comparisons"]:
                if comparison.get("criterion"):
                    content.append(
                        Paragraph(
                            f"Criterion: {_pdf_display_value(comparison['criterion'])}",
                            body_style,
                        )
                    )

                if comparison.get("candidate_observations"):
                    for obs in comparison["candidate_observations"]:
                        obs_text = f"  {obs.get('candidate_id', 'Unknown')}: {obs.get('status', 'Unknown')}"
                        if obs.get("evidence"):
                            obs_text += f" - {_pdf_display_value(obs['evidence'])}"
                        content.append(Paragraph(obs_text, body_style))

                if comparison.get("summary"):
                    content.append(
                        Paragraph(
                            f"Summary: {_pdf_display_value(comparison['summary'])}",
                            body_style,
                        )
                    )

                content.append(Spacer(1, 0.1 * inch))

    # GPT-5 Assessment
    if gpt5_result:
        content.append(PageBreak())
        content.append(Paragraph("GPT-5 Assessment", section_style))

        if gpt5_result.get("comparison_summary"):
            content.append(Paragraph("Comparison Summary", subsection_style))
            content.append(
                Paragraph(
                    _pdf_display_value(gpt5_result["comparison_summary"]), body_style
                )
            )
            content.append(Spacer(1, 0.2 * inch))

        # Candidate details
        if gpt5_result.get("candidates"):
            for candidate in gpt5_result["candidates"]:
                candidate_name = candidate.get("candidate_name", "Unknown")
                content.append(
                    Paragraph(f"Candidate: {candidate_name}", subsection_style)
                )

                if candidate.get("strengths"):
                    content.append(Paragraph("Strengths:", body_style))
                    for strength in candidate["strengths"]:
                        content.append(
                            Paragraph(f"  • {_pdf_display_value(strength)}", body_style)
                        )

                if candidate.get("gaps"):
                    content.append(Paragraph("Gaps:", body_style))
                    for gap in candidate["gaps"]:
                        content.append(
                            Paragraph(f"  • {_pdf_display_value(gap)}", body_style)
                        )

                if candidate.get("jd_coverage"):
                    content.append(Paragraph("JD Coverage:", body_style))
                    for coverage in candidate["jd_coverage"]:
                        content.append(
                            Paragraph(f"  • {_pdf_display_value(coverage)}", body_style)
                        )

                if candidate.get("evidence"):
                    content.append(Paragraph("Evidence:", body_style))
                    for evidence in candidate["evidence"]:
                        content.append(
                            Paragraph(f"  • {_pdf_display_value(evidence)}", body_style)
                        )

                content.append(Spacer(1, 0.2 * inch))

        # Comparisons
        if gpt5_result.get("comparisons"):
            content.append(Paragraph("Detailed Comparisons", subsection_style))
            for comparison in gpt5_result["comparisons"]:
                if comparison.get("criterion"):
                    content.append(
                        Paragraph(
                            f"Criterion: {_pdf_display_value(comparison['criterion'])}",
                            body_style,
                        )
                    )

                if comparison.get("candidate_observations"):
                    for obs in comparison["candidate_observations"]:
                        obs_text = f"  {obs.get('candidate_id', 'Unknown')}: {obs.get('status', 'Unknown')}"
                        if obs.get("evidence"):
                            obs_text += f" - {_pdf_display_value(obs['evidence'])}"
                        content.append(Paragraph(obs_text, body_style))

                if comparison.get("summary"):
                    content.append(
                        Paragraph(
                            f"Summary: {_pdf_display_value(comparison['summary'])}",
                            body_style,
                        )
                    )

                content.append(Spacer(1, 0.1 * inch))

    # Build PDF
    doc.build(content)
    buffer.seek(0)
    return buffer.getvalue()


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
# call can't starve the rest.
ANALYZE_MAX_INFLIGHT = int(os.environ.get("ANALYZE_MAX_INFLIGHT", "4"))
# Timeout increased to 600s (10 min) to accommodate slow local Ollama pipeline.
# Observed runs on llama3.2 with 5 resumes: ~560s total (51s JD analysis + ~509s for embeddings, skills, grading).
# This timeout ensures legitimate multi-resume analyses complete without false 504 errors.
ANALYZE_TIMEOUT_S = float(os.environ.get("ANALYZE_TIMEOUT_S", "600"))
_analyze_sem = asyncio.Semaphore(ANALYZE_MAX_INFLIGHT)


def restore_candidate_profile_fields(resume_skill_profile, jd_structured=None):
    profile = resume_skill_profile if isinstance(resume_skill_profile, dict) else {}
    skills = profile.get("skills", profile)
    skills = skills if isinstance(skills, dict) else {}
    contact_info = skills.get("contact_info", {})
    contact_info = contact_info if isinstance(contact_info, dict) else {}

    restored = {"contact_info": contact_info}
    linkedin_url = contact_info.get("linkedin")
    linkedin_profile = None

    if linkedin_url:
        linkedin_profile = fetch_captapi_linkedin_profile(linkedin_url)
        if linkedin_profile:
            restored["linkedin_profile"] = linkedin_profile

    try:
        restored["linkedin_verification"] = verify_linkedin_evidence_against_resume(
            skills,
            linkedin_profile,
            jd_structured,
        )
    except Exception:
        restored["linkedin_verification"] = dict(LINKEDIN_VERIFICATION_FALLBACK)

    github_url = contact_info.get("github")
    if github_url:
        github_evidence = get_github_evidence(github_url)
        restored["github_verification"] = verify_github_evidence_against_resume(
            skills,
            github_evidence,
        )

    return restored


class CodeReviewRequest(BaseModel):
    code: Optional[str] = ""
    provider: Optional[str] = "Gemini"
    model_name: Optional[str] = "gemini-2.5-flash"
    background: Optional[bool] = False


class CandidateComparisonRequest(BaseModel):
    candidate_ids: List[str]
    jd_info: Dict[str, Any]


class InMemoryUpload(io.BytesIO):
    def __init__(self, content: bytes, name: str):
        super().__init__(content)
        self.name = name


def build_fit_bucket(score: float) -> str:
    if score >= 70:
        return "Good Fit"
    if score >= 50:
        return "Moderate Fit"
    return "Bad Fit"


def serialize_jd_info(jd_info: Dict[str, Any]) -> Dict[str, str]:
    return {
        "job_title": display_value(jd_info.get("job_title")),
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
            if record.get("embedding_indexed") and record.get("skills_indexed")
        ),
        "embedding_indexed": sum(
            1 for record in records if record.get("embedding_indexed")
        ),
        "skills_indexed": sum(1 for record in records if record.get("skills_indexed")),
    }


@api.get("/resume/{resume_id}")
def resume_detail(resume_id: str):
    chunks_store = read_json_file(RESUME_CHUNKS_PATH, [])

    if isinstance(chunks_store, dict):
        chunks = chunks_store.get(resume_id, [])
    elif isinstance(chunks_store, list):
        chunks = [
            chunk
            for chunk in chunks_store
            if isinstance(chunk, dict) and chunk.get("resume_id") == resume_id
        ]
    else:
        chunks = []

    if not isinstance(chunks, list) or not chunks:
        raise HTTPException(status_code=404, detail="Resume not found.")

    ordered_chunks = sorted(
        chunks,
        key=lambda chunk: chunk.get("chunk_index", 0) if isinstance(chunk, dict) else 0,
    )
    resume_text = "\n\n".join(
        chunk.get("text", "")
        for chunk in ordered_chunks
        if isinstance(chunk, dict) and chunk.get("text")
    )

    return {
        "resume_text": resume_text,
        "chunks": chunks,
    }


@api.put("/configuration")
def save_configuration(config: dict):
    return {"configuration": update_configuration(config)}


@api.post("/configuration/reset")
def reset_saved_configuration():
    return {"configuration": reset_configuration()}


@api.get("/session")
async def get_last_analysis_session():
    """Get the last saved analysis session for restoration after refresh."""
    try:
        import json
        import os

        base_dir = "vector_store"
        path = os.path.join(base_dir, "analysis_sessions.json")

        if not os.path.isfile(path):
            return {"session": None}

        with open(path, "r", encoding="utf-8") as f:
            sessions = json.load(f) or []

        if not sessions or not isinstance(sessions, list) or len(sessions) == 0:
            return {"session": None}

        # Return the most recent session (last in array)
        last_session = sessions[-1] if isinstance(sessions[-1], dict) else None

        return {"session": last_session}
    except Exception as e:
        print(f"[SESSION] Error loading session: {e}")
        return {"session": None}


class EvidenceAlignmentRequest(BaseModel):
    resume_id: str
    resume_name: str
    job_description: str
    linkedin_verification: Optional[dict] = None
    github_verification: Optional[dict] = None


@api.get("/test-evidence-alignment")
async def test_evidence_alignment():
    """Test route to verify routing works."""
    return {"status": "ok", "message": "Route is registered"}


@api.post("/analyze")
async def analyze(
    job_description: str = Form(...),
    provider: str = Form("Gemini"),
    model_name: str = Form("gemini-2.5-flash"),
    detail_limit: int = Form(5),
    resumes: Optional[List[UploadFile]] = File(None),
):
    """Concurrency-safe analyze endpoint.

    The heavy analyzer pipeline runs on a worker thread via asyncio.to_thread so the event loop stays responsive.
    """
    started = time.perf_counter()
    try:
        async with _analyze_sem:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    _run_analyze_blocking,
                    job_description,
                    provider,
                    model_name,
                    detail_limit,
                    resumes,
                ),
                timeout=ANALYZE_TIMEOUT_S,
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


@api.post("/evidence-alignment")
async def get_evidence_alignment(request: EvidenceAlignmentRequest):
    """Generate evidence alignment for resume highlighting."""
    try:
        from backend import RESUME_CHUNKS_PATH, read_json_file

        # Load resume chunks using resume_id
        chunks_store = read_json_file(RESUME_CHUNKS_PATH, {})

        # Filter chunks for this resume
        resume_chunks = []
        if isinstance(chunks_store, list):
            resume_chunks = [
                c for c in chunks_store if c.get("resume_id") == request.resume_id
            ]
        elif isinstance(chunks_store, dict):
            resume_chunks = [
                c
                for c in chunks_store.values()
                if c.get("resume_id") == request.resume_id
            ]

        if not resume_chunks:
            return {
                "resume_id": request.resume_id,
                "matches": [],
                "skipped": True,
                "reason": "No resume chunks found.",
            }

        # Generate evidence alignment
        try:
            import sys

            sys.path.insert(0, ".")
            from backend import generate_evidence_alignment

            result = generate_evidence_alignment(
                resume_chunks=resume_chunks,
                job_description=request.job_description,
                linkedin_verification=request.linkedin_verification,
                github_verification=request.github_verification,
                resume_id=request.resume_id,
            )
        except ImportError:
            logger.warning(
                "[EVIDENCE ALIGNMENT] Failed to import evidence alignment function",
                exc_info=True,
            )
            return {
                "resume_id": request.resume_id,
                "matches": [],
                "skipped": True,
                "reason": "Evidence alignment service unavailable.",
            }

        return result
    except Exception:
        logger.exception(
            "[EVIDENCE ALIGNMENT] Unexpected error generating evidence alignment"
        )
        return {
            "resume_id": request.resume_id,
            "matches": [],
            "skipped": True,
            "reason": "Failed to generate evidence alignment.",
        }


def _build_persistable_file_cache(file_cache):
    """Remove transient embedding arrays before analysis-session persistence."""
    persistable_cache = []
    for item in file_cache:
        persistable_item = dict(item)
        persistable_item.pop("resume_embedding", None)
        chunk_data = persistable_item.get("chunk_data")
        if isinstance(chunk_data, dict):
            persistable_item["chunk_data"] = {
                key: value for key, value in chunk_data.items() if key != "embeddings"
            }
        persistable_cache.append(persistable_item)
    return persistable_cache


def _run_analyze_blocking(
    job_description: str,
    provider: str,
    model_name: str,
    detail_limit: int,
    resumes: Optional[List[UploadFile]],
) -> dict:
    """Synchronous analyzer pipeline."""
    clear_runtime_status()
    pipeline_started = time.perf_counter()
    timings = {}

    print("[ANALYZE] Pipeline START")

    if provider not in AI_PROVIDER_OPTIONS:
        raise HTTPException(status_code=400, detail="Unsupported provider.")

    if not job_description.strip():
        raise HTTPException(
            status_code=400,
            detail="Job description is required.",
        )

    detail_limit = max(1, min(int(detail_limit), 50))

    print("[ANALYZE] JD analysis START")
    jd_started = time.perf_counter()
    jd_info = analyze_job_description(
        job_description,
        model_name=model_name,
        provider=provider,
    )
    timings["jd_analysis_ms"] = int((time.perf_counter() - jd_started) * 1000)
    print(f"[ANALYZE] JD analysis END duration={timings['jd_analysis_ms']/1000:.2f}s")

    invalid_resumes = []
    uploaded_records = {}

    print("[ANALYZE] Uploaded resume processing START")
    upload_processing_started = time.perf_counter()

    for resume in resumes or []:
        content = resume.file.read()
        resume_file = InMemoryUpload(content, resume.filename)
        is_valid, message = validate_upload(resume_file)

        if not is_valid:
            invalid_resumes.append({"resume_name": resume.filename, "error": message})
            continue

        resume_id = get_resume_id(resume_file)
        extract_started = time.perf_counter()
        resume_text_items = extract_text(resume_file, preserve_structure=True)
        resume_text = extract_text(
            resume_file, preserve_structure=False
        )  # Keep legacy text for compatibility
        timings[f"extract_{resume.filename}"] = int(
            (time.perf_counter() - extract_started) * 1000
        )

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

        embed_started = time.perf_counter()
        # Use chunk-based embeddings (Phase 1)
        chunk_data = get_or_create_resume_embedding(
            resume_id,
            resume.filename,
            resume_text_items,
            use_chunking=True,
        )
        # For backward compatibility, also create legacy embedding
        resume_embedding = get_or_create_resume_embedding(
            resume_id,
            resume.filename,
            resume_text,
            use_chunking=False,
        )
        timings[f"embed_{resume.filename}"] = int(
            (time.perf_counter() - embed_started) * 1000
        )

        skill_started = time.perf_counter()
        resume_skill_profile = get_resume_skill_profile(
            resume_id,
            resume.filename,
            resume_text,
        )
        timings[f"skill_{resume.filename}"] = int(
            (time.perf_counter() - skill_started) * 1000
        )
        uploaded_records[resume_id] = {
            "resume_id": resume_id,
            "resume_name": resume.filename,
            "resume_text": resume_text,
            "resume_text_items": resume_text_items,  # New: preserve structure
            "resume_embedding": resume_embedding,  # Legacy: for backward compatibility
            "chunk_data": chunk_data,  # New: chunk-based embeddings
            "resume_skill_profile": resume_skill_profile,
        }

    upload_processing_duration = time.perf_counter() - upload_processing_started
    print(
        f"[ANALYZE] Uploaded resume processing END duration={upload_processing_duration:.2f}s"
    )

    # Step 1: Load active Resume DB independently of FAISS (source of truth)
    print("[ANALYZE] Active Resume DB load START")
    active_resume_db = get_active_resume_db_records()
    print(f"[ANALYZE] Active Resume DB loaded: {len(active_resume_db)} resumes")

    # Step 2: Combine candidate pool (existing Resume DB + new uploads)
    print("[ANALYZE] Candidate pool merge START")
    merge_started = time.perf_counter()

    file_cache = []
    indexed_resume_ids = set()

    # Add existing Resume DB candidates
    for resume_id, record in active_resume_db.items():
        if resume_id in uploaded_records:
            # Will be handled in uploaded records section
            continue

        # Try to get embedding from FAISS (optimization layer)
        embedding = faiss_index_lookup(resume_id)
        if embedding is not None:
            # Resume has embedding in FAISS - add to candidate pool
            score = calculate_match_score(embedding, job_description)
            file_cache.append(
                {
                    "record": {
                        "resume_name": record["resume_name"],
                        "resume_id": resume_id,
                        "match_score": score,
                        "fit": build_fit_bucket(score),
                    },
                    "resume_text": "",  # Not stored in Resume DB
                    "resume_skill_profile": record["resume_skill_profile"],
                }
            )
            indexed_resume_ids.add(resume_id)
        else:
            # Resume in DB but no embedding - skip (will need re-upload)
            print(
                f"[ANALYZE] Resume {record['resume_name']} in DB but no embedding, skipping"
            )

    # Add uploaded resumes to candidate pool
    for resume_id, item in uploaded_records.items():
        if resume_id in indexed_resume_ids:
            # Already added from Resume DB
            continue
        # Use legacy embedding for backward compatibility
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
                # Store chunk data for future use (Phase 2+)
                "chunk_data": item.get("chunk_data"),
            }
        )
        indexed_resume_ids.add(resume_id)

    merge_duration = time.perf_counter() - merge_started
    print(f"[ANALYZE] Candidate pool merge END duration={merge_duration:.2f}s")
    print(f"[ANALYZE] Total candidate pool size: {len(file_cache)}")

    # Step 3: FAISS pre-filtering (optimization layer)
    if file_cache:
        print("[ANALYZE] JD embedding START")
        jd_embedding_started = time.perf_counter()

        # Create JD embedding for semantic search
        jd_embedding = encode_text_embedding(
            job_description,
            "Represent this description for matching:",
        )

        jd_embedding_duration = time.perf_counter() - jd_embedding_started
        print(f"[ANALYZE] JD embedding END duration={jd_embedding_duration:.2f}s")

        print("[ANALYZE] FAISS search START")
        search_started = time.perf_counter()

        # Use FAISS to find top candidates (optimization)
        faiss_search_k = max(10, detail_limit * 3)
        try:
            top_candidates_from_search = faiss_semantic_search(
                jd_embedding, top_k=faiss_search_k
            )
            top_candidate_ids = {
                resume_id for resume_id, _ in top_candidates_from_search
            }

            timings["faiss_search_ms"] = int(
                (time.perf_counter() - search_started) * 1000
            )
            print(
                f"[ANALYZE] FAISS search END duration={timings['faiss_search_ms']/1000:.2f}s"
            )
            print(f"[ANALYZE] FAISS returned {len(top_candidate_ids)} candidates")

            # Prioritize FAISS results, but keep all candidates as fallback
            if top_candidate_ids:
                prioritized = [
                    c
                    for c in file_cache
                    if c["record"]["resume_id"] in top_candidate_ids
                ]
                others = [
                    c
                    for c in file_cache
                    if c["record"]["resume_id"] not in top_candidate_ids
                ]
                file_cache = prioritized + others
                print(
                    f"[ANALYZE] Candidate pool prioritized: {len(prioritized)} FAISS, {len(others)} fallback"
                )
            else:
                print(
                    "[ANALYZE] FAISS search returned empty, using full candidate pool"
                )
        except Exception as e:
            print(f"[ANALYZE] FAISS search failed, using full candidate pool: {e}")
            # Fall back to full candidate pool (no filtering)

    # Step 4: Check if candidate pool is empty
    if not file_cache:
        raise HTTPException(
            status_code=400,
            detail="No resumes available. Upload at least one PDF or DOCX resume.",
        )

    print("[analyze-timing]", timings)

    print("[ANALYZE] Ranking START")
    ranking_started = time.perf_counter()
    valid_records = [item["record"] for item in file_cache]
    ranking = sorted(valid_records, key=lambda item: item["match_score"], reverse=True)
    detail_records = ranking[:detail_limit]
    detail_ids = {record["resume_id"] for record in detail_records}
    detail_order = {
        record["resume_id"]: index for index, record in enumerate(detail_records)
    }
    ranking_duration = time.perf_counter() - ranking_started
    print(f"[ANALYZE] Ranking END duration={ranking_duration:.2f}s")

    def _process_candidate_detail(item):
        """Process a single candidate's detail analysis and grading."""
        import time

        candidate_start = time.perf_counter()
        thread_id = threading.get_ident()
        record = item["record"]
        resume_name = record["resume_name"]

        print(f"[CANDIDATE {resume_name}] PROCESS START thread={thread_id}")

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
        restored_profile_fields = restore_candidate_profile_fields(
            item["resume_skill_profile"],
            jd_structured=jd_info,
        )
        for field, value in restored_profile_fields.items():
            detail.setdefault(field, value)

        candidate_duration = time.perf_counter() - candidate_start
        print(
            f"[CANDIDATE {resume_name}] PROCESS END duration={candidate_duration:.2f}s thread={thread_id}"
        )

        return {**record, **detail}

    # Filter candidates that need detail analysis
    candidates_to_process = [
        item for item in file_cache if item["record"]["resume_id"] in detail_ids
    ]

    print(
        f"[ANALYZE] Parallel candidate analysis START candidates={len(candidates_to_process)}"
    )
    parallel_analysis_started = time.perf_counter()

    # Process candidates concurrently using ThreadPoolExecutor
    # Limit concurrency to ANALYZE_MAX_INFLIGHT to respect system limits
    with ThreadPoolExecutor(max_workers=ANALYZE_MAX_INFLIGHT) as executor:
        top_details = list(
            executor.map(_process_candidate_detail, candidates_to_process)
        )

    parallel_analysis_duration = time.perf_counter() - parallel_analysis_started
    print(
        f"[ANALYZE] Parallel candidate analysis END duration={parallel_analysis_duration:.2f}s"
    )

    print("[ANALYZE] Result sorting START")
    sorting_started = time.perf_counter()
    top_details = sorted(
        top_details,
        key=lambda item: detail_order.get(item["resume_id"], 0),
    )
    sorting_duration = time.perf_counter() - sorting_started
    print(f"[ANALYZE] Result sorting END duration={sorting_duration:.2f}s")

    print("[ANALYZE] Category building START")
    categories_started = time.perf_counter()
    categories = {
        "good_fit": [r["resume_name"] for r in ranking if r["fit"] == "Good Fit"],
        "moderate_fit": [
            r["resume_name"] for r in ranking if r["fit"] == "Moderate Fit"
        ],
        "bad_fit": [r["resume_name"] for r in ranking if r["fit"] == "Bad Fit"],
    }
    categories_duration = time.perf_counter() - categories_started
    print(f"[ANALYZE] Category building END duration={categories_duration:.2f}s")

    print("[ANALYZE] Session persistence START")
    persistence_started = time.perf_counter()
    persistable_file_cache = _build_persistable_file_cache(file_cache)
    payload = {
        "job_description": job_description,
        "provider": provider,
        "model_name": model_name,
        "detail_limit": detail_limit,
        "jd_info": jd_info,
        "file_cache": persistable_file_cache,
        "result": {
            "job_description": serialize_jd_info(jd_info),
            "ranking": ranking,
            "top_details": top_details,
            "detail_limit": detail_limit,
            "categories": categories,
            "invalid_resumes": invalid_resumes,
            "runtime_status": get_runtime_status(),
            "timings_ms": timings,
        },
    }
    persist_analysis_session(payload)
    persistence_duration = time.perf_counter() - persistence_started
    print(f"[ANALYZE] Session persistence END duration={persistence_duration:.2f}s")

    timings["total_pipeline_ms"] = int((time.perf_counter() - pipeline_started) * 1000)
    print(
        f"[ANALYZE] Pipeline END total_duration={timings['total_pipeline_ms']/1000:.2f}s"
    )
    print("[analyze-timing] pipeline", timings)

    return {
        "job_description": serialize_jd_info(jd_info),
        "ranking": ranking,
        "top_details": top_details,
        "detail_limit": detail_limit,
        "categories": categories,
        "invalid_resumes": invalid_resumes,
        "runtime_status": get_runtime_status(),
        "timings_ms": timings,
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
        # Try Gemini first (via REST API)
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


@api.get("/api/review/status/{job_id}")
async def get_review_status(job_id: str):
    job = jobs_db.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@api.post("/api/compare-candidates")
async def compare_candidates(request: CandidateComparisonRequest):
    """Compare multiple selected candidates using GPT-5.

    This endpoint uses the isolated GPT-5 comparison engine to compare
    candidates against a job description using existing stored evidence.
    """
    # Validation: Need at least 2 candidates
    if not request.candidate_ids or len(request.candidate_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 candidate IDs are required for comparison",
        )

    # Validation: Need job description info
    if not request.jd_info or not isinstance(request.jd_info, dict):
        raise HTTPException(
            status_code=400, detail="Job description information (jd_info) is required"
        )

    # Load existing resume database to validate candidate IDs
    active_resume_db = get_active_resume_db_records()

    # Validate candidate IDs and build candidate data
    candidates_data = []
    missing_candidate_ids = []

    for candidate_id in request.candidate_ids:
        if candidate_id not in active_resume_db:
            missing_candidate_ids.append(candidate_id)
            continue

        record = active_resume_db[candidate_id]
        resume_skill_profile = record.get("resume_skill_profile", {})

        # Build candidate data structure for comparison
        candidate_data = {
            "candidate_id": candidate_id,
            "candidate_name": record.get("resume_name", "Unknown Candidate"),
            "resume_skill_profile": resume_skill_profile,
        }

        # Add existing analysis data if available
        # Try to get from recent analysis session or cached data
        # For now, we use the skill profile as the primary evidence source

        # Extract skills from profile
        if isinstance(resume_skill_profile, dict):
            skills = resume_skill_profile.get("skills", {})
            if isinstance(skills, dict):
                technical_skills = skills.get("technical_skills", [])
                if isinstance(technical_skills, list):
                    candidate_data["matching_skills"] = technical_skills

        candidates_data.append(candidate_data)

    # Check if any candidate IDs were not found
    if missing_candidate_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate IDs not found in database: {', '.join(missing_candidate_ids)}",
        )

    # Validation: Ensure we have enough valid candidates
    if len(candidates_data) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 valid candidates are required for comparison",
        )

    try:
        # Call the isolated GPT-5 comparison function
        comparison_result = compare_selected_candidates(
            job_description=request.jd_info, candidates_data=candidates_data
        )

        # Check if comparison failed due to validation
        if "error" in comparison_result:
            error_type = comparison_result["error"]
            if error_type == "insufficient_candidates":
                raise HTTPException(
                    status_code=400,
                    detail="Comparison requires at least 2 valid candidates",
                )
            elif error_type == "missing_candidate_id":
                raise HTTPException(
                    status_code=400, detail="Candidate data is missing required IDs"
                )
            elif error_type == "invalid_candidate_data":
                raise HTTPException(
                    status_code=400, detail="Invalid candidate data format"
                )

        return comparison_result

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as exc:
        # Handle other errors safely
        raise HTTPException(
            status_code=500, detail=f"Candidate comparison failed: {str(exc)}"
        )


@api.post("/api/compare-candidates-gpt4")
async def compare_candidates_gpt4(request: CandidateComparisonRequest):
    """Compare multiple selected candidates using GPT-4.

    This endpoint uses the isolated GPT-4 comparison engine to compare
    candidates against a job description using existing stored evidence.
    This is a separate comparison path from GPT-5, using the same input data
    but analyzed independently by GPT-4.
    """
    # Validation: Need at least 2 candidates
    if not request.candidate_ids or len(request.candidate_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 candidate IDs are required for comparison",
        )

    # Validation: Need job description info
    if not request.jd_info or not isinstance(request.jd_info, dict):
        raise HTTPException(
            status_code=400, detail="Job description information (jd_info) is required"
        )

    # Load existing resume database to validate candidate IDs
    active_resume_db = get_active_resume_db_records()

    # Validate candidate IDs and build candidate data
    candidates_data = []
    missing_candidate_ids = []

    for candidate_id in request.candidate_ids:
        if candidate_id not in active_resume_db:
            missing_candidate_ids.append(candidate_id)
            continue

        record = active_resume_db[candidate_id]
        resume_skill_profile = record.get("resume_skill_profile", {})

        # Build candidate data structure for comparison
        candidate_data = {
            "candidate_id": candidate_id,
            "candidate_name": record.get("resume_name", "Unknown Candidate"),
            "resume_skill_profile": resume_skill_profile,
        }

        # Extract skills from profile
        if isinstance(resume_skill_profile, dict):
            skills = resume_skill_profile.get("skills", {})
            if isinstance(skills, dict):
                technical_skills = skills.get("technical_skills", [])
                if isinstance(technical_skills, list):
                    candidate_data["matching_skills"] = technical_skills

        candidates_data.append(candidate_data)

    # Check if any candidate IDs were not found
    if missing_candidate_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate IDs not found in database: {', '.join(missing_candidate_ids)}",
        )

    # Validation: Ensure we have enough valid candidates
    if len(candidates_data) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 valid candidates are required for comparison",
        )

    try:
        # Call the isolated GPT-4 comparison function
        comparison_result = compare_selected_candidates_gpt4(
            job_description=request.jd_info, candidates_data=candidates_data
        )

        # Check if comparison failed due to validation
        if "error" in comparison_result:
            error_type = comparison_result["error"]
            if error_type == "insufficient_candidates":
                raise HTTPException(
                    status_code=400,
                    detail="Comparison requires at least 2 valid candidates",
                )
            elif error_type == "missing_candidate_id":
                raise HTTPException(
                    status_code=400, detail="Candidate data is missing required IDs"
                )
            elif error_type == "invalid_candidate_data":
                raise HTTPException(
                    status_code=400, detail="Invalid candidate data format"
                )

        return comparison_result

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as exc:
        # Handle other errors safely
        raise HTTPException(
            status_code=500, detail=f"GPT-4 candidate comparison failed: {str(exc)}"
        )


@api.post("/api/evidence-assessment")
async def evidence_assessment(request: CandidateComparisonRequest):
    """Generate an evidence-based assessment comparing candidates.

    This endpoint uses the evidence assessment engine to compare
    candidates against a job description using existing stored evidence.
    It provides a concise, evidence-based assessment with supporting points.
    """
    # Validation: Need at least 2 candidates
    if not request.candidate_ids or len(request.candidate_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 candidate IDs are required for evidence assessment",
        )

    # Validation: Need job description info
    if not request.jd_info or not isinstance(request.jd_info, dict):
        raise HTTPException(
            status_code=400, detail="Job description information (jd_info) is required"
        )

    # Load existing resume database to validate candidate IDs
    active_resume_db = get_active_resume_db_records()

    # Validate candidate IDs and build candidate data
    candidates_data = []
    missing_candidate_ids = []

    for candidate_id in request.candidate_ids:
        if candidate_id not in active_resume_db:
            missing_candidate_ids.append(candidate_id)
            continue

        record = active_resume_db[candidate_id]
        resume_skill_profile = record.get("resume_skill_profile", {})

        # Build candidate data structure for assessment
        candidate_data = {
            "candidate_id": candidate_id,
            "candidate_name": record.get("resume_name", "Unknown Candidate"),
            "resume_skill_profile": resume_skill_profile,
        }

        # Add existing analysis data if available
        # Extract skills from profile
        if isinstance(resume_skill_profile, dict):
            skills = resume_skill_profile.get("skills", {})
            if isinstance(skills, dict):
                technical_skills = skills.get("technical_skills", [])
                if isinstance(technical_skills, list):
                    candidate_data["matching_skills"] = technical_skills

        candidates_data.append(candidate_data)

    # Check if any candidate IDs were not found
    if missing_candidate_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate IDs not found in database: {', '.join(missing_candidate_ids)}",
        )

    # Validation: Ensure we have enough valid candidates
    if len(candidates_data) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 valid candidates are required for evidence assessment",
        )

    try:
        # Call the evidence assessment function
        assessment_result = generate_evidence_assessment(
            job_description=request.jd_info, candidates_data=candidates_data
        )

        # Check if assessment failed due to validation
        if "error" in assessment_result:
            error_type = assessment_result["error"]
            if error_type == "insufficient_candidates":
                raise HTTPException(
                    status_code=400,
                    detail="Evidence assessment requires at least 2 valid candidates",
                )
            elif error_type == "missing_candidate_name":
                raise HTTPException(
                    status_code=400, detail="Candidate data is missing required names"
                )
            elif error_type == "invalid_candidate_data":
                raise HTTPException(
                    status_code=400, detail="Invalid candidate data format"
                )

        return assessment_result

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as exc:
        # Handle other errors safely
        raise HTTPException(
            status_code=500, detail=f"Evidence assessment failed: {str(exc)}"
        )


class ComparisonExportRequest(BaseModel):
    evidence_assessment: Optional[Dict[str, Any]] = None
    gpt4_result: Optional[Dict[str, Any]] = None
    gpt5_result: Optional[Dict[str, Any]] = None
    job_description: Optional[Dict[str, Any]] = None


@api.post("/api/export-comparison")
async def export_comparison(request: ComparisonExportRequest):
    """Export candidate comparison report as PDF.

    This endpoint generates a PDF report containing all available comparison
    information including evidence assessment, GPT-4 assessment, and GPT-5 assessment.
    """
    try:
        # Generate PDF from comparison data
        pdf_bytes = generate_comparison_report_pdf(
            evidence_assessment=request.evidence_assessment,
            gpt4_result=request.gpt4_result,
            gpt5_result=request.gpt5_result,
            job_description=request.job_description,
        )

        # Return PDF as response
        from fastapi.responses import Response

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=candidate_comparison_report.pdf",
                "Content-Length": str(len(pdf_bytes)),
            },
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF export failed: {str(exc)}")


def _strip_html(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = re.sub(r"<(script|style)[^>]*>[\s\S]*?</\1>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return text


def _report_id_for(path: str) -> str:
    return hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]


def _safe_json_loads(s: str):
    if not isinstance(s, str):
        return None
    try:
        return json.loads(s)
    except Exception:
        pass  # Intentionally silent - fallback to next pattern
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", s)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass  # Intentionally silent - fallback to next pattern
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", s)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass  # Intentionally silent - fallback to None
    return None


# ==================================================
# SHORTLIST API MODELS
# ==================================================


class CreateShortlistRequest(BaseModel):
    job_description: Dict[str, Any]
    user_id: str
    created_by_role: str
    evidence_assessment_snapshot: Optional[Dict[str, Any]] = None


class AddCandidateRequest(BaseModel):
    resume_id: str
    candidate_name: str
    match_score: float
    match_position: str
    evidence_snapshot: Optional[Dict[str, Any]] = None


class UpdateStatusRequest(BaseModel):
    status: str


# ==================================================
# SHORTLIST API ENDPOINTS
# ==================================================


@api.post("/api/shortlists/create")
async def create_shortlist_endpoint(request: CreateShortlistRequest):
    """Create a new shortlist for the authenticated user."""
    try:
        shortlist = create_shortlist(
            job_description=request.job_description,
            user_id=request.user_id,
            created_by_role=request.created_by_role,
            evidence_assessment_snapshot=request.evidence_assessment_snapshot,
        )
        return {"shortlist": shortlist}
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to create shortlist: {str(exc)}"
        )


@api.get("/api/shortlists")
async def get_shortlists_endpoint(user_id: str = Query(...)):
    """Get all shortlists for the authenticated user."""
    try:
        shortlists = get_user_shortlists(user_id)
        return {"shortlists": shortlists}
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get shortlists: {str(exc)}"
        )


@api.get("/api/shortlists/{shortlist_id}")
async def get_shortlist_endpoint(shortlist_id: str, user_id: str = Query(...)):
    """Get a specific shortlist by ID."""
    try:
        # Verify ownership
        if not verify_shortlist_ownership(shortlist_id, user_id):
            raise HTTPException(
                status_code=403, detail="You do not have access to this shortlist"
            )

        shortlist = get_shortlist(shortlist_id)
        if not shortlist:
            raise HTTPException(status_code=404, detail="Shortlist not found")

        return {"shortlist": shortlist}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get shortlist: {str(exc)}"
        )


@api.post("/api/shortlists/{shortlist_id}/candidates")
async def add_candidate_endpoint(
    shortlist_id: str, request: AddCandidateRequest, user_id: str = Query(...)
):
    """Add a candidate to an existing shortlist."""
    try:
        # Verify ownership
        if not verify_shortlist_ownership(shortlist_id, user_id):
            raise HTTPException(
                status_code=403, detail="You do not have access to this shortlist"
            )

        # Verify candidate exists
        if not verify_candidate_exists(request.resume_id):
            raise HTTPException(
                status_code=404,
                detail=f"Candidate {request.resume_id} not found in resume database",
            )

        shortlist = add_candidate_to_shortlist(
            shortlist_id=shortlist_id,
            resume_id=request.resume_id,
            candidate_name=request.candidate_name,
            match_score=request.match_score,
            match_position=request.match_position,
            evidence_snapshot=request.evidence_snapshot,
        )

        if not shortlist:
            raise HTTPException(status_code=404, detail="Shortlist not found")

        return {"shortlist": shortlist}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to add candidate: {str(exc)}"
        )


@api.get("/api/shortlists/{shortlist_id}/candidates")
async def get_shortlist_candidates_endpoint(
    shortlist_id: str, user_id: str = Query(...)
):
    """Get all candidates in a shortlist."""
    try:
        # Verify ownership
        if not verify_shortlist_ownership(shortlist_id, user_id):
            raise HTTPException(
                status_code=403, detail="You do not have access to this shortlist"
            )

        shortlist = get_shortlist(shortlist_id)
        if not shortlist:
            raise HTTPException(status_code=404, detail="Shortlist not found")

        candidates = shortlist.get("shortlisted_candidates", [])
        return {"candidates": candidates}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get candidates: {str(exc)}"
        )


@api.delete("/api/shortlists/{shortlist_id}/candidates/{resume_id}")
async def remove_candidate_endpoint(
    shortlist_id: str, resume_id: str, user_id: str = Query(...)
):
    """Remove a candidate from a shortlist."""
    try:
        # Verify ownership
        if not verify_shortlist_ownership(shortlist_id, user_id):
            raise HTTPException(
                status_code=403, detail="You do not have access to this shortlist"
            )

        shortlist = remove_candidate_from_shortlist(shortlist_id, resume_id)
        if not shortlist:
            raise HTTPException(status_code=404, detail="Shortlist not found")

        return {"shortlist": shortlist}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to remove candidate: {str(exc)}"
        )


@api.put("/api/shortlists/{shortlist_id}/status")
async def update_status_endpoint(
    shortlist_id: str, request: UpdateStatusRequest, user_id: str = Query(...)
):
    """Update shortlist status."""
    try:
        # Verify ownership
        if not verify_shortlist_ownership(shortlist_id, user_id):
            raise HTTPException(
                status_code=403, detail="You do not have access to this shortlist"
            )

        shortlist = update_shortlist_status(shortlist_id, request.status)
        if not shortlist:
            raise HTTPException(
                status_code=404, detail="Shortlist not found or invalid status"
            )

        return {"shortlist": shortlist}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to update status: {str(exc)}"
        )


@api.delete("/api/shortlists/{shortlist_id}")
async def delete_shortlist_endpoint(shortlist_id: str, user_id: str = Query(...)):
    """Delete a shortlist."""
    try:
        # Verify ownership
        if not verify_shortlist_ownership(shortlist_id, user_id):
            raise HTTPException(
                status_code=403, detail="You do not have access to this shortlist"
            )

        success = delete_shortlist(shortlist_id)
        if not success:
            raise HTTPException(status_code=404, detail="Shortlist not found")

        return {"message": "Shortlist deleted successfully"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete shortlist: {str(exc)}"
        )


class GenerateQuestionsRequest(BaseModel):
    assessment_id: str
    candidate_id: str
    job_role: Optional[str] = "Engineer"
    job_description: Optional[Any] = None
    candidate_resume: Optional[Any] = None


@api.post("/api/assessment/generate-questions")
async def generate_questions_endpoint(request: GenerateQuestionsRequest):
    """Generate or retrieve candidate-specific 15-question assessment."""
    try:
        from backend_question_generator import (
            generate_candidate_assessment,
            get_assessment_questions,
        )

        # Check existing
        existing = get_assessment_questions(request.assessment_id)
        if (
            existing
            and existing.get("questions")
            and len(existing.get("questions", [])) == 15
        ):
            return existing

        # Fetch shortlist context if JD or Resume not fully supplied
        jd_data = request.job_description
        resume_data = request.candidate_resume

        if not jd_data or not resume_data:
            shortlists_data = get_shortlists()
            for sl in shortlists_data:
                candidates = (
                    sl.get("candidates") or sl.get("shortlisted_candidates") or []
                )
                for cand in candidates:
                    if cand.get("resume_id") == request.candidate_id:
                        if not jd_data:
                            jd_data = sl.get("job_description")
                        break
                if jd_data:
                    break

        if not resume_data:
            resume_db = get_active_resume_db_records()
            if request.candidate_id in resume_db:
                resume_data = resume_db[request.candidate_id]

        payload = generate_candidate_assessment(
            assessment_id=request.assessment_id,
            candidate_id=request.candidate_id,
            job_description=jd_data,
            candidate_resume=resume_data,
            job_role=request.job_role or "Engineer",
        )
        return payload
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate assessment questions: {str(exc)}",
        )


@api.get("/api/assessment/questions/{assessment_id}")
async def get_questions_endpoint(assessment_id: str):
    """Retrieve persisted questions for an assessment ID without regenerating."""
    try:
        from backend_question_generator import get_assessment_questions

        existing = get_assessment_questions(assessment_id)
        if existing and existing.get("questions"):
            return existing
        raise HTTPException(
            status_code=404,
            detail=f"Assessment questions for ID '{assessment_id}' not found",
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve assessment questions: {str(exc)}",
        )


class SubmitAssessmentRequest(BaseModel):
    assessment_id: str
    candidate_id: str
    resume_id: Optional[str] = None
    role: Optional[str] = "Engineer"
    answers: Dict[str, Any]
    started_at: Optional[str] = None


@api.post("/api/assessment/submit")
async def submit_assessment_endpoint(request: SubmitAssessmentRequest):
    """Securely submit and persist candidate assessment answers."""
    try:
        from datetime import datetime, timezone

        from backend_question_generator import (
            get_assessment_attempt,
            get_assessment_questions,
            save_assessment_attempt,
        )

        # 1. Check if assessment exists
        questions_payload = get_assessment_questions(request.assessment_id)
        if not questions_payload or not questions_payload.get("questions"):
            raise HTTPException(
                status_code=404,
                detail=f"Assessment ID '{request.assessment_id}' not found. Cannot submit answers.",
            )

        # 2. Check for duplicate submission
        existing_attempt = get_assessment_attempt(request.assessment_id)
        if existing_attempt and existing_attempt.get("status") in [
            "submitted",
            "completed",
        ]:
            return {
                "message": "Assessment has already been submitted",
                "status": existing_attempt.get("status"),
                "submitted_at": existing_attempt.get("submitted_at"),
                "already_submitted": True,
            }

        # 3. Security validation: Verify submitted answer keys belong ONLY to valid question IDs
        valid_qids = {
            q.get("id") for q in questions_payload.get("questions", []) if q.get("id")
        }
        sanitized_answers = {}

        for qid, ans in request.answers.items():
            if qid not in valid_qids:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid question ID '{qid}' submitted for this assessment.",
                )
            # Ensure only answer string is accepted
            if isinstance(ans, str):
                sanitized_answers[qid] = ans.strip()
            elif ans is None:
                sanitized_answers[qid] = ""
            else:
                sanitized_answers[qid] = str(ans)

        # 4. Construct persisted attempt payload (NO scoring calculations in Phase 3A)
        now_iso = datetime.now(timezone.utc).isoformat()
        attempt_payload = {
            "assessment_id": request.assessment_id,
            "candidate_id": request.candidate_id,
            "resume_id": request.resume_id or request.candidate_id,
            "role": request.role or questions_payload.get("job_role", "Engineer"),
            "started_at": request.started_at or now_iso,
            "submitted_at": now_iso,
            "status": "submitted",
            "answers": sanitized_answers,
        }

        # 5. Persist attempt locally
        save_assessment_attempt(request.assessment_id, attempt_payload)

        return {
            "message": "Assessment submitted successfully",
            "assessment_id": request.assessment_id,
            "status": "submitted",
            "submitted_at": now_iso,
            "answered_count": len([v for v in sanitized_answers.values() if v]),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to submit assessment answers: {str(exc)}"
        )


class BehaviorEventItem(BaseModel):
    type: str
    timestamp: str
    duration_seconds: Optional[float] = None
    details: Optional[str] = None


class PostBehaviorEventsRequest(BaseModel):
    assessment_id: str
    candidate_id: Optional[str] = "unknown"
    events: List[BehaviorEventItem]


class AssessmentAccessTokenRequest(BaseModel):
    assessment_id: str
    candidate_id: str


@api.post("/api/assessment/access-token")
async def issue_assessment_access_token(
    request: Request, payload: AssessmentAccessTokenRequest
):
    recruiter = require_recruiter(request)
    assessment_id = validate_identifier(payload.assessment_id, "assessment ID")
    candidate_id = validate_identifier(payload.candidate_id, "candidate ID")
    record = _assessment_record_for(assessment_id)
    if not record or str(record.get("candidate_id")) != candidate_id:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    if not _user_owns_assessment(recruiter["sub"], assessment_id):
        raise HTTPException(status_code=403, detail="Assessment access denied.")
    return {
        "assessment_id": assessment_id,
        "candidate_id": candidate_id,
        "token": issue_assessment_token(recruiter["sub"], assessment_id, candidate_id),
    }


@api.post("/api/assessment/behavior-events")
async def post_behavior_events_endpoint(
    request: Request, payload: PostBehaviorEventsRequest
):
    """Securely log observable candidate behavior events."""
    try:
        from backend_question_generator import (
            append_assessment_behavior_events,
            get_assessment_questions,
        )

        # 1. Validate assessment exists
        assessment_id = validate_identifier(payload.assessment_id, "assessment ID")
        candidate_id = validate_identifier(payload.candidate_id, "candidate ID")
        require_assessment_access(request, assessment_id, candidate_id)
        questions_payload = get_assessment_questions(assessment_id)
        if not questions_payload:
            raise HTTPException(
                status_code=404,
                detail=f"Assessment ID '{assessment_id}' not found. Cannot record behavior events.",
            )
        if str(questions_payload.get("candidate_id")) != candidate_id:
            raise HTTPException(status_code=403, detail="Candidate access denied.")

        # Allowed observable event types
        ALLOWED_EVENT_TYPES = {
            "tab_hidden",
            "tab_visible",
            "face_present",
            "face_absent",
            "multiple_faces_detected",
            "looking_away",
            "looking_forward",
            "eye_looking_left",
            "eye_looking_right",
            "eye_looking_up",
            "eye_looking_down",
            "eye_looking_forward",
            "camera_started",
            "camera_stopped",
            "camera_error",
            "camera_permission_denied",
            "audio_activity_detected",
            "network_offline",
            "network_online",
            "copy_attempt",
            "paste_attempt",
        }

        if len(payload.events) > 100:
            raise HTTPException(
                status_code=400, detail="Too many behavior events in one request."
            )
        _enforce_event_rate(f"{assessment_id}:{candidate_id}", len(payload.events))

        sanitized_events = []
        for item in payload.events:
            evt_type = str(item.type).strip()
            if evt_type in ALLOWED_EVENT_TYPES:
                evt_dict = {
                    "type": evt_type,
                    "timestamp": _validate_event_timestamp(item.timestamp),
                }
                if item.duration_seconds is not None:
                    evt_dict["duration_seconds"] = _validate_duration(
                        item.duration_seconds
                    )
                if item.details:
                    evt_dict["details"] = str(item.details)[:200]
                sanitized_events.append(evt_dict)

                # --- 1. & 3. TERMINAL LOGGING ---
                if evt_type == "tab_hidden":
                    print("\n[TAB MONITORING] TAB HIDDEN")
                    print(f"assessment_id={assessment_id}")
                    print(f"timestamp={evt_dict['timestamp']}")
                elif evt_type == "tab_visible":
                    print("\n[TAB MONITORING] TAB VISIBLE")
                    print(f"assessment_id={assessment_id}")
                    print(f"timestamp={evt_dict['timestamp']}")
                    if "duration_seconds" in evt_dict:
                        print(f"duration_seconds={evt_dict['duration_seconds']}")
                elif evt_type == "face_present":
                    print("\n[FACE MONITORING] FACE PRESENT")
                    print(f"assessment_id={assessment_id}")
                    print(f"timestamp={evt_dict['timestamp']}")
                elif evt_type == "face_absent":
                    print("\n[FACE MONITORING] FACE ABSENT")
                    print(f"assessment_id={assessment_id}")
                    print(f"timestamp={evt_dict['timestamp']}")
                    if "duration_seconds" in evt_dict:
                        print(
                            f"absence_duration_seconds={evt_dict['duration_seconds']}"
                        )

        if not sanitized_events:
            return {"message": "No valid behavior events to record", "count": 0}

        record = append_assessment_behavior_events(
            assessment_id=assessment_id,
            candidate_id=candidate_id,
            new_events=sanitized_events,
        )

        return {
            "message": "Behavior events logged successfully",
            "assessment_id": assessment_id,
            "events_added": len(sanitized_events),
            "total_events": len(record.get("events", [])),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to record behavior events: {str(exc)}"
        )


@api.get("/api/assessment/behavior-events/{assessment_id}")
async def get_behavior_events_endpoint(request: Request, assessment_id: str):
    """Retrieve logged behavior monitoring events for an assessment ID."""
    try:
        from backend_question_generator import get_assessment_behavior_events

        assessment_id = validate_identifier(assessment_id, "assessment ID")
        recruiter = require_recruiter(request)
        if not _user_owns_assessment(recruiter["sub"], assessment_id):
            raise HTTPException(status_code=403, detail="Assessment access denied.")

        record = get_assessment_behavior_events(assessment_id)
        if record:
            return record
        return {"assessment_id": assessment_id, "candidate_id": "unknown", "events": []}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch behavior events: {str(exc)}"
        )


@api.post("/api/assessment/evidence")
async def post_assessment_evidence_endpoint(
    request: Request,
    assessment_id: str = Form(...),
    candidate_id: str = Form("unknown"),
    event_type: str = Form(...),
    timestamp: str = Form(...),
    duration_seconds: float = Form(...),
    evidence_type: str = Form(...),
    clip: UploadFile = File(...),
):
    """Store one short, allowlisted assessment evidence clip."""
    assessment_id = validate_identifier(assessment_id, "assessment ID")
    candidate_id = validate_identifier(candidate_id, "candidate ID")
    require_assessment_access(request, assessment_id, candidate_id)
    if event_type not in EVIDENCE_EVENT_TYPES:
        raise HTTPException(
            status_code=400, detail="Evidence event type is not allowed."
        )
    if duration_seconds <= 0 or duration_seconds > 5:
        raise HTTPException(
            status_code=400, detail="Evidence duration must be between 0 and 5 seconds."
        )
    if evidence_type not in {"screen_video", "screen_screenshot"}:
        raise HTTPException(
            status_code=400,
            detail="Evidence type must be screen_video or screen_screenshot.",
        )

    from backend_question_generator import get_assessment_questions

    questions_payload = get_assessment_questions(assessment_id)
    if not questions_payload:
        raise HTTPException(
            status_code=404, detail=f"Assessment ID '{assessment_id}' not found."
        )
    if str(questions_payload.get("candidate_id")) != candidate_id:
        raise HTTPException(status_code=403, detail="Candidate access denied.")

    content_type = clip.content_type or ""

    clip_bytes = await clip.read(MAX_EVIDENCE_BYTES + 1)
    if not clip_bytes or len(clip_bytes) > MAX_EVIDENCE_BYTES:
        raise HTTPException(
            status_code=400, detail="Evidence clip is empty or too large."
        )
    _validate_event_timestamp(timestamp)
    _validate_duration(duration_seconds, maximum=5)
    _validate_evidence_bytes(evidence_type, content_type, clip_bytes)

    evidence_id = uuid.uuid4().hex
    extension = "png" if evidence_type == "screen_screenshot" else "webm"
    clip_path = _assert_evidence_path(assessment_id, evidence_id, extension)
    root = ASSESSMENT_EVIDENCE_DIR.resolve()
    resolved_clip_str = os.path.realpath(str(clip_path))
    root_str = os.path.realpath(str(root))
    if not resolved_clip_str.startswith(
        root_str + os.sep
    ) or not clip_path.is_relative_to(root):
        raise HTTPException(status_code=400, detail="Invalid evidence path.")
    clip_target_path = pathlib.Path(resolved_clip_str)
    clip_target_path.parent.mkdir(parents=True, exist_ok=True)
    clip_target_path.write_bytes(clip_bytes)

    evidence_item = {
        "evidence_id": evidence_id,
        "assessment_id": assessment_id,
        "candidate_id": candidate_id or "unknown",
        "event_type": event_type,
        "evidence_type": evidence_type,
        "timestamp": timestamp,
        "duration_seconds": round(float(duration_seconds), 2),
        "storage_reference": f"/api/assessment/evidence/{assessment_id}/{evidence_id}",
    }
    with _evidence_lock:
        metadata = _read_evidence_metadata()
        metadata.setdefault(assessment_id, []).append(evidence_item)
        _write_evidence_metadata(metadata)

    return evidence_item


@api.get("/api/assessment/evidence/{assessment_id}")
async def get_assessment_evidence_endpoint(request: Request, assessment_id: str):
    """Return evidence metadata for only the requested assessment."""
    assessment_id = validate_identifier(assessment_id, "assessment ID")
    recruiter = require_recruiter(request)
    if not _user_owns_assessment(recruiter["sub"], assessment_id):
        raise HTTPException(status_code=403, detail="Assessment access denied.")
    with _evidence_lock:
        metadata = _read_evidence_metadata()
        evidence = metadata.get(assessment_id, [])
    return {"assessment_id": assessment_id, "evidence": evidence}


@api.get("/api/assessment/evidence/{assessment_id}/{evidence_id}")
async def get_assessment_evidence_clip_endpoint(
    request: Request, assessment_id: str, evidence_id: str
):
    """Stream one stored evidence clip after verifying its assessment ownership."""
    assessment_id = validate_identifier(assessment_id, "assessment ID")
    evidence_id = validate_identifier(evidence_id, "evidence ID")
    recruiter = require_recruiter(request)
    if not _user_owns_assessment(recruiter["sub"], assessment_id):
        raise HTTPException(status_code=403, detail="Assessment access denied.")
    with _evidence_lock:
        evidence = next(
            (
                item
                for item in _read_evidence_metadata().get(assessment_id, [])
                if item.get("evidence_id") == evidence_id
            ),
            None,
        )
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence clip not found.")

    extension = (
        "png" if evidence.get("evidence_type") == "screen_screenshot" else "webm"
    )
    clip_path = _assert_evidence_path(assessment_id, evidence_id, extension)
    root = ASSESSMENT_EVIDENCE_DIR.resolve()
    resolved_clip_str = os.path.realpath(str(clip_path))
    root_str = os.path.realpath(str(root))
    if not resolved_clip_str.startswith(
        root_str + os.sep
    ) or not clip_path.is_relative_to(root):
        raise HTTPException(status_code=400, detail="Invalid evidence path.")
    if not os.path.isfile(resolved_clip_str):
        raise HTTPException(status_code=404, detail="Evidence clip file not found.")
    media_type = (
        "image/png"
        if evidence.get("evidence_type") == "screen_screenshot"
        else "video/webm"
    )
    return FileResponse(resolved_clip_str, media_type=media_type)


@api.post("/api/assessment/score/{assessment_id}")
async def post_score_assessment_endpoint(assessment_id: str):
    """Score a candidate's submitted assessment attempt."""
    try:
        from backend_question_generator import score_assessment_attempt

        result = score_assessment_attempt(assessment_id)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to score assessment: {str(exc)}"
        )
