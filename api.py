import io

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend import (
    AI_PROVIDER_OPTIONS,
    GEMINI_MODEL_OPTIONS,
    OLLAMA_MODEL_OPTIONS,
    analyze_candidate_detail,
    analyze_job_description,
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
    return {
        "status": "ok",
    }


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
        "skills_indexed": sum(
            1 for record in records if record["skills_indexed"]
        ),
    }


@api.put("/configuration")
def save_configuration(config: dict):
    return {
        "configuration": update_configuration(config),
    }


@api.post("/configuration/reset")
def reset_saved_configuration():
    return {
        "configuration": reset_configuration(),
    }


@api.post("/analyze")
async def analyze(
    job_description: str = Form(...),
    provider: str = Form("Gemini"),
    model_name: str = Form("gemini-2.5-flash"),
    detail_limit: int = Form(5),
    resumes: list[UploadFile] | None = File(None),
):
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
        content = await resume.read()
        resume_file = InMemoryUpload(content, resume.filename)
        is_valid, message = validate_upload(resume_file)

        if not is_valid:
            invalid_resumes.append(
                {
                    "resume_name": resume.filename,
                    "error": message,
                }
            )
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
            uploaded_item["resume_text"]
            if uploaded_item
            else item["resume_text"]
        )
        resume_skill_profile = (
            uploaded_item["resume_skill_profile"]
            if uploaded_item
            else item["resume_skill_profile"]
        )
        score = calculate_match_score(
            item["resume_embedding"],
            job_description,
        )
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

        score = calculate_match_score(
            item["resume_embedding"],
            job_description,
        )
        record = {
            "resume_name": item["resume_name"],
            "resume_id": item["resume_id"],
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
    ranking = sorted(
        valid_records,
        key=lambda item: item["match_score"],
        reverse=True,
    )
    detail_records = ranking[:detail_limit]
    detail_ids = {
        record["resume_id"] for record in detail_records
    }
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
        top_details.append(
            {
                **record,
                **detail,
            }
        )

    top_details = sorted(
        top_details,
        key=lambda item: detail_order.get(item["resume_id"], 0),
    )

    categories = {
        "good_fit": [
            record["resume_name"]
            for record in ranking
            if record["fit"] == "Good Fit"
        ],
        "moderate_fit": [
            record["resume_name"]
            for record in ranking
            if record["fit"] == "Moderate Fit"
        ],
        "bad_fit": [
            record["resume_name"]
            for record in ranking
            if record["fit"] == "Bad Fit"
        ],
    }

    return {
        "job_description": serialize_jd_info(jd_info),
        "ranking": ranking,
        "top_details": top_details,
        "detail_limit": detail_limit,
        "categories": categories,
        "invalid_resumes": invalid_resumes,
        "runtime_status": get_runtime_status(),
    }

