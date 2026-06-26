import io

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend import (
    AI_PROVIDER_OPTIONS,
    GEMINI_MODEL_OPTIONS,
    OLLAMA_MODEL_OPTIONS,
    analyze_candidate_detail,
    analyze_job_description,
    display_value,
    extract_text,
    get_configuration,
    get_or_create_resume_embedding,
    get_resume_id,
    get_resume_skill_profile,
    get_runtime_status,
    initialize_project_storage_files,
    calculate_match_score,
    reset_configuration,
    update_configuration,
    validate_upload,
)

from backend_skills import (
    SkillNotFoundError,
    get_skill,
    list_skills,
    run_skill,
)
from backend_skills.runner import SkillExecutionError, SkillValidationError


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


@api.get("/skills")
def skills():
    """Return every Skill discovered under the repo ``skills/`` folder."""
    return {
        "skills": list_skills(),
    }


@api.post("/skills/{name}/run")
def run_skill_endpoint(name: str, payload: dict | None = None):
    """Execute a Skill end-to-end and return its parsed JSON output."""
    payload = payload or {}
    inputs = payload.get("inputs") or {}
    provider = payload.get("provider")
    model_name = payload.get("model_name")

    if provider is not None and provider not in AI_PROVIDER_OPTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider '{provider}'.",
        )

    try:
        result = run_skill(
            name,
            inputs=inputs,
            provider=provider,
            model_name=model_name,
        )
    except SkillNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Skill '{name}' was not found.",
        )
    except SkillValidationError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except SkillExecutionError as error:
        raise HTTPException(status_code=502, detail=str(error))

    summary = get_skill(name).to_summary()
    return {
        "skill": summary,
        "result": result,
        "runtime_status": get_runtime_status(),
    }


@api.get("/configuration")
def configuration():
    return {
        "configuration": get_configuration(),
        "providers": AI_PROVIDER_OPTIONS,
        "ollama_models": OLLAMA_MODEL_OPTIONS,
        "gemini_models": GEMINI_MODEL_OPTIONS,
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
    resumes: list[UploadFile] = File(...),
):
    if provider not in AI_PROVIDER_OPTIONS:
        raise HTTPException(status_code=400, detail="Unsupported provider.")

    if not job_description.strip():
        raise HTTPException(
            status_code=400,
            detail="Job description is required.",
        )

    if not resumes:
        raise HTTPException(
            status_code=400,
            detail="At least one resume is required.",
        )

    jd_info = analyze_job_description(
        job_description,
        model_name=model_name,
        provider=provider,
    )

    resume_records = []
    file_cache = []

    for resume in resumes:
        content = await resume.read()
        resume_file = InMemoryUpload(content, resume.filename)
        is_valid, message = validate_upload(resume_file)

        if not is_valid:
            resume_records.append(
                {
                    "resume_name": resume.filename,
                    "error": message,
                }
            )
            continue

        resume_id = get_resume_id(resume_file)
        resume_text = extract_text(resume_file)
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
        score = calculate_match_score(
            resume_embedding,
            job_description,
        )

        record = {
            "resume_name": resume.filename,
            "resume_id": resume_id,
            "match_score": score,
            "fit": build_fit_bucket(score),
        }
        resume_records.append(record)
        file_cache.append(
            {
                "record": record,
                "resume_text": resume_text,
                "resume_skill_profile": resume_skill_profile,
            }
        )

    valid_records = [
        record for record in resume_records if "match_score" in record
    ]
    ranking = sorted(
        valid_records,
        key=lambda item: item["match_score"],
        reverse=True,
    )
    top_ids = {
        record["resume_id"] for record in ranking[:5]
    }
    top_details = []

    for item in file_cache:
        record = item["record"]

        if record["resume_id"] not in top_ids:
            continue

        detail = analyze_candidate_detail(
            item["resume_text"],
            job_description,
            record["match_score"],
            model_name=model_name,
            resume_skill_profile=item["resume_skill_profile"],
            provider=provider,
            job_skill_requirements=jd_info,
        )
        top_details.append(
            {
                **record,
                **detail,
            }
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
        "categories": categories,
        "invalid_resumes": [
            record for record in resume_records if "error" in record
        ],
        "runtime_status": get_runtime_status(),
    }
