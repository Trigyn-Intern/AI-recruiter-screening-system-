import json
import hashlib
import os
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import numpy as np
import ollama
import pandas as pd
from docx import Document
from jsonschema import ValidationError, validate
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

try:
    from google import genai
except ImportError:
    genai = None

try:
    import faiss
except ImportError:
    faiss = None




# ==================================================
# CONFIGURATION DEFAULTS
# ==================================================

DEFAULT_OLLAMA_MODEL = "llama3.2"
DEFAULT_AI_PROVIDER = "Ollama"
GEMINI_RESUME_SKILL_MODEL = "gemini-2.5-flash"
EMBEDDING_MODEL_NAME = "BAAI/bge-large-en-v1.5"
EMBEDDING_DIMENSION = 1024
PROJECT_ROOT = Path(__file__).resolve().parent
VECTOR_STORE_DIR = PROJECT_ROOT / "vector_store"
FAISS_INDEX_PATH = VECTOR_STORE_DIR / "resume_embeddings.faiss"
FAISS_METADATA_PATH = VECTOR_STORE_DIR / "resume_metadata.json"
RESUME_SKILLS_PATH = VECTOR_STORE_DIR / "resume_skills.json"
PROMPT_CONFIG_PATH = VECTOR_STORE_DIR / "prompt_config.json"

AI_PROVIDER_OPTIONS = [
    "Ollama",
    "Gemini",
]

OLLAMA_MODEL_OPTIONS = [
    "llama3.2",
    "llama3.3",
    "llama3.1",
    "llama3",
    "gemma4",
    "gemma3",
    "mistral",
    "mistral-nemo",
    "mistral-small",
    "gemma2",
    "qwen2.5",
    "qwen3.5",
    "qwen3",
    "gpt-oss",
    "phi4",
    "phi4-mini",
    "deepseek-r1",
    "mixtral",
]

GEMINI_MODEL_OPTIONS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
    "gemini-3.5-flash",
    "gemini-3-flash-preview",
    "gemini-3.1-pro-preview",
    "gemini-3.1-flash-lite",
]

GEMINI_TRANSIENT_ERROR_CODES = [
    "503",
    "UNAVAILABLE",
]

DEFAULT_JD_PROMPT_TEMPLATE = """You are an HR Recruitment Expert.

Read the Job Description carefully.

Extract:

1. Years of Experience Required
2. Primary Skills
3. Secondary Skills
4. Educational Qualifications

Return ONLY valid JSON.

Format:

{
    "experience": "",
    "primary_skills": "",
    "secondary_skills": "",
    "education": ""
}

JOB DESCRIPTION:

{job_text}
"""

DEFAULT_SKILL_GAP_PROMPT_TEMPLATE = """You are an ATS and Technical Recruiter.

Compare the candidate profile against the job requirements.

Return ONLY valid JSON.

Format:

{
    "matching_skills": [
        "skill1",
        "skill2"
    ],
    "missing_skills": [
        "skill1",
        "skill2"
    ]
}

Rules:
- Maximum 10 matching skills.
- Maximum 10 missing skills.
- No explanations.
- No markdown.
- No code blocks.
- No text before or after JSON.

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_text}
"""

DEFAULT_MATCH_JUSTIFICATION_PROMPT_TEMPLATE = """You are an ATS and Technical Recruiter.

Explain why the candidate received the given resume-job match score.

Return ONLY valid JSON.

Format:

{
    "justification": ""
}

Rules:
- Write 2 to 3 short lines.
- Mention the strongest matching evidence.
- Mention the most important gaps if any.
- Do not use markdown.
- Do not include text before or after JSON.

MATCH SCORE:
{score}%

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_text}
"""

DEFAULT_CANDIDATE_DETAIL_PROMPT_TEMPLATE = """You are an ATS and Technical Recruiter.

Compare the provided candidate resume context against the job requirements and
explain the resume-job match score.

Return ONLY valid JSON.

Format:

{
    "matching_skills": [
        "skill1",
        "skill2"
    ],
    "missing_skills": [
        "skill1",
        "skill2"
    ],
    "justification": ""
}

Rules:
- Maximum 10 matching skills.
- Maximum 10 missing skills.
- Write the justification in 2 to 3 short lines.
- Mention the strongest matching evidence.
- Mention the most important gaps if any.
- The RESUME section below is the candidate resume context. It may contain raw
  resume text, indexed resume JSON, or both.
- Never say that no resume was provided when the RESUME section has content.
- No explanations outside JSON.
- No markdown.
- No code blocks.

MATCH SCORE:
{score}%

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_text}
"""

DEFAULT_CANDIDATE_GRADING_PROMPT_TEMPLATE = """You are a senior technical recruiter.

Grade the candidate's fit for the job using only the resume context, matching
skills, missing skills, years of experience, hands-on project evidence, domain
fit, and role seniority signals.

Return ONLY valid JSON.

Format:

{
    "grade": "A | B | C | D | F",
    "summary": "",
    "strengths": [
        "strength1",
        "strength2"
    ],
    "concerns": [
        "concern1",
        "concern2"
    ]
}

Rules:
- Do not use or mention the existing match score.
- Do not calculate a percentage score.
- Grade A only for strong evidence across required skills, relevant experience,
  and hands-on project usage.
- Grade B for mostly strong fit with a few manageable gaps.
- Grade C for partial fit with meaningful missing skills or unclear hands-on
  evidence.
- Grade D for weak fit with major required-skill or experience gaps.
- Grade F only when the resume has almost no relevant evidence for the job.
- Write the summary in 2 to 3 short lines.
- Use strengths for evidence-backed positives.
- Use concerns for missing skills, weak experience, or unclear project evidence.
- No explanations outside JSON.
- No markdown.
- No code blocks.

RESUME CONTEXT:
{resume_text}

JOB DESCRIPTION:
{job_text}

MATCHING SKILLS:
{matching_skills}

MISSING SKILLS:
{missing_skills}
"""

DEFAULT_RESUME_SKILL_EXTRACTION_PROMPT_TEMPLATE = """You are an ATS resume parser.

Extract the candidate's skills, role signals, and evidence from the resume.

Return ONLY valid JSON.

Format:

{
    "technical_skills": [
        "skill1",
        "skill2"
    ],
    "soft_skills": [
        "skill1",
        "skill2"
    ],
    "tools": [
        "tool1",
        "tool2"
    ],
    "domains": [
        "domain1",
        "domain2"
    ],
    "experience_summary": "",
    "skill_evidence": [
        {
            "skill": "skill name",
            "evidence": "exact resume phrase, sentence, or project line",
            "source": "project, role, company, or section name if available"
        }
    ]
}

Rules:
- Keep each list to a maximum of 15 items.
- skill_evidence is optional. Include up to 10 evidence-backed skills when
  the resume has clear evidence, otherwise return an empty list.
- evidence must be copied or closely paraphrased from the resume, not invented.
- If a field is not found, return an empty list or "Not Found".
- Use concise skill names.
- Do not include markdown.
- Do not include text before or after JSON.

RESUME:
{resume_text}
"""

JD_SCHEMA = {
    "type": "object",
    "required": [
        "experience",
        "primary_skills",
        "secondary_skills",
        "education",
    ],
    "properties": {
        "experience": {},
        "primary_skills": {},
        "secondary_skills": {},
        "education": {},
    },
}

JD_RESPONSE_SCHEMA = {
    "type": "object",
    "required": [
        "experience",
        "primary_skills",
        "secondary_skills",
        "education",
    ],
    "properties": {
        "experience": {},
        "primary_skills": {},
        "secondary_skills": {},
        "education": {},
    },
}

SKILL_GAP_SCHEMA = {
    "type": "object",
    "properties": {
        "matching_skills": {},
        "missing_skills": {},
    },
}

MATCH_JUSTIFICATION_SCHEMA = {
    "type": "object",
    "required": [
        "justification",
    ],
    "properties": {
        "justification": {
            "type": "string",
        },
    },
}

CANDIDATE_DETAIL_SCHEMA = {
    "type": "object",
    "required": [
        "matching_skills",
        "missing_skills",
        "justification",
    ],
    "properties": {
        "matching_skills": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "missing_skills": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "justification": {
            "type": "string",
        },
    },
}

CANDIDATE_GRADING_SCHEMA = {
    "type": "object",
    "required": [
        "grade",
        "summary",
        "strengths",
        "concerns",
    ],
    "properties": {
        "grade": {
            "type": "string",
        },
        "summary": {
            "type": "string",
        },
        "strengths": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "concerns": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
    },
}

RESUME_SKILL_SCHEMA = {
    "type": "object",
    "required": [
        "technical_skills",
        "soft_skills",
        "tools",
        "domains",
        "experience_summary",
    ],
    "properties": {
        "technical_skills": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "soft_skills": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "tools": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "domains": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "experience_summary": {
            "type": "string",
        },
        "skill_evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "skill": {
                        "type": "string",
                    },
                    "evidence": {
                        "type": "string",
                    },
                    "source": {
                        "type": "string",
                    },
                },
            },
        },
    },
}

JD_FALLBACK = {
    "experience": "Not Found",
    "primary_skills": "Not Found",
    "secondary_skills": "Not Found",
    "education": "Not Found",
}

SKILL_GAP_FALLBACK = {
    "matching_skills": [],
    "missing_skills": [],
}

MATCH_JUSTIFICATION_FALLBACK = {
    "justification": "Justification could not be generated.",
}

CANDIDATE_DETAIL_FALLBACK = {
    "matching_skills": [],
    "missing_skills": [],
    "justification": "Justification could not be generated.",
}

CANDIDATE_GRADING_FALLBACK = {
    "grade": "C",
    "summary": "Candidate grading could not be generated.",
    "strengths": [],
    "concerns": [],
}

RESUME_SKILL_FALLBACK = {
    "technical_skills": [],
    "soft_skills": [],
    "tools": [],
    "domains": [],
    "experience_summary": "Not Found",
    "skill_evidence": [],
}

RUNTIME_STATE = {
    "ai_provider": DEFAULT_AI_PROVIDER,
    "ollama_model": DEFAULT_OLLAMA_MODEL,
    "gemini_model": GEMINI_MODEL_OPTIONS[0],
    "jd_prompt_template": DEFAULT_JD_PROMPT_TEMPLATE,
    "skill_gap_prompt_template": DEFAULT_SKILL_GAP_PROMPT_TEMPLATE,
    "active_jd_prompt_template": DEFAULT_JD_PROMPT_TEMPLATE,
    "active_skill_gap_prompt_template": DEFAULT_SKILL_GAP_PROMPT_TEMPLATE,
    "active_candidate_detail_prompt_template": (
        DEFAULT_CANDIDATE_DETAIL_PROMPT_TEMPLATE
    ),
    "active_candidate_grading_prompt_template": (
        DEFAULT_CANDIDATE_GRADING_PROMPT_TEMPLATE
    ),
    "active_resume_skill_extraction_prompt_template": (
        DEFAULT_RESUME_SKILL_EXTRACTION_PROMPT_TEMPLATE
    ),
    "use_custom_jd_prompt": False,
    "use_custom_skill_gap_prompt": False,
    "ai_analysis_cache": {},
    "last_ai_error": "",
    "last_vector_store_error": "",
    "last_vector_store_status": "",
    "last_resume_skill_status": "",
    "grading_checkpoints": [],
    "skip_gemini_grading": False,
}


# ==================================================
# LOAD EMBEDDING MODEL
# ==================================================

@lru_cache(maxsize=1)
def load_model():
    try:
        return SentenceTransformer(
            EMBEDDING_MODEL_NAME,
            local_files_only=True,
        )
    except TypeError:
        return SentenceTransformer(EMBEDDING_MODEL_NAME)


def create_hash_embedding(text, prefix):
    vector = np.zeros((EMBEDDING_DIMENSION,), dtype="float32")
    tokens = (prefix + " " + text).lower().split()

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "little") % EMBEDDING_DIMENSION
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    norm = np.linalg.norm(vector)

    if norm == 0:
        vector[0] = 1.0
    else:
        vector = vector / norm

    return vector.reshape(1, -1).astype("float32")


def encode_text_embedding(text, prefix):
    try:
        embedding_model = load_model()
        embedding = embedding_model.encode(
            [
                prefix + text,
            ],
            normalize_embeddings=True,
        )
        return np.asarray(embedding, dtype="float32")
    except Exception as error:
        RUNTIME_STATE["last_vector_store_error"] = (
            "Embedding model unavailable, using local hash embeddings: "
            f"{error}"
        )
        return create_hash_embedding(text, prefix)


def load_resume_vector_store(dimension=EMBEDDING_DIMENSION):
    if faiss is None:
        raise RuntimeError(
            "Install faiss-cpu to use the resume vector database."
        )

    ensure_vector_store_dir()
    metadata = read_json_file(FAISS_METADATA_PATH, [])

    if FAISS_INDEX_PATH.exists():
        index = faiss.read_index(str(FAISS_INDEX_PATH))
    else:
        index = faiss.IndexFlatIP(dimension)

    return index, metadata


def save_resume_vector_store(index, metadata):
    ensure_vector_store_dir()
    faiss.write_index(index, str(FAISS_INDEX_PATH))
    write_json_file(FAISS_METADATA_PATH, metadata)


def find_resume_metadata(metadata, resume_id):
    for item in metadata:
        if item.get("resume_id") == resume_id:
            return item

    return None


def get_current_timestamp():
    return datetime.now(timezone.utc).isoformat()


def get_or_create_resume_embedding(resume_id, resume_name, resume_text):
    try:
        index, metadata = load_resume_vector_store()
        existing = find_resume_metadata(metadata, resume_id)

        if existing is not None:
            existing["resume_name"] = resume_name
            existing["last_updated_at"] = get_current_timestamp()
            save_resume_vector_store(index, metadata)
            row = int(existing["faiss_row"])
            RUNTIME_STATE["last_vector_store_error"] = ""
            RUNTIME_STATE["last_vector_store_status"] = (
                f"Loaded cached embedding for {resume_name}."
            )
            return np.asarray(
                [
                    index.reconstruct(row),
                ],
                dtype="float32",
            )

        embedding = encode_text_embedding(
            resume_text,
            "Represent this resume for retrieval:",
        )

        if int(embedding.shape[1]) != int(index.d):
            raise RuntimeError(
                "Stored FAISS index dimension does not match the embedding "
                "model dimension."
            )

        index.add(embedding)
        metadata.append(
            {
                "resume_id": resume_id,
                "resume_name": resume_name,
                "faiss_row": int(index.ntotal - 1),
                "embedding_model": EMBEDDING_MODEL_NAME,
                "created_at": get_current_timestamp(),
                "last_updated_at": get_current_timestamp(),
            }
        )
        save_resume_vector_store(index, metadata)
        RUNTIME_STATE["last_vector_store_error"] = ""
        RUNTIME_STATE["last_vector_store_status"] = (
            f"Saved new embedding for {resume_name}."
        )
        return embedding

    except Exception as error:
        RUNTIME_STATE["last_vector_store_error"] = str(error)
        RUNTIME_STATE["last_vector_store_status"] = ""
        embedding = encode_text_embedding(
            resume_text,
            "Represent this resume for retrieval:",
        )
        return embedding


@lru_cache(maxsize=1)
def get_available_ollama_models():
    try:
        response = ollama.list()
        models = getattr(response, "models", None)

        if models is None and isinstance(response, dict):
            models = response.get("models", [])

        names = []

        for model in models:
            if isinstance(model, dict):
                name = model.get("name") or model.get("model")
            else:
                name = (
                    getattr(model, "name", None)
                    or getattr(model, "model", None)
                )

            if name:
                names.append(name)

        return names

    except Exception:
        return []


# ==================================================
# HELPERS
# ==================================================

def init_configuration_state():
    if RUNTIME_STATE.get("ai_provider") not in AI_PROVIDER_OPTIONS:
        RUNTIME_STATE["ai_provider"] = DEFAULT_AI_PROVIDER

    model_options = get_model_options()

    if RUNTIME_STATE.get("ollama_model") not in model_options:
        RUNTIME_STATE["ollama_model"] = model_options[0]

    if RUNTIME_STATE.get("gemini_model") not in GEMINI_MODEL_OPTIONS:
        RUNTIME_STATE["gemini_model"] = GEMINI_MODEL_OPTIONS[0]

    if not RUNTIME_STATE.get("jd_prompt_template", "").strip():
        RUNTIME_STATE["jd_prompt_template"] = DEFAULT_JD_PROMPT_TEMPLATE

    if not RUNTIME_STATE.get("skill_gap_prompt_template", "").strip():
        RUNTIME_STATE[
            "skill_gap_prompt_template"
        ] = DEFAULT_SKILL_GAP_PROMPT_TEMPLATE

    RUNTIME_STATE.setdefault("use_custom_jd_prompt", False)
    RUNTIME_STATE.setdefault("use_custom_skill_gap_prompt", False)
    RUNTIME_STATE.setdefault(
        "active_jd_prompt_template",
        DEFAULT_JD_PROMPT_TEMPLATE,
    )
    RUNTIME_STATE.setdefault(
        "active_skill_gap_prompt_template",
        DEFAULT_SKILL_GAP_PROMPT_TEMPLATE,
    )
    RUNTIME_STATE.setdefault(
        "active_candidate_grading_prompt_template",
        DEFAULT_CANDIDATE_GRADING_PROMPT_TEMPLATE,
    )

    if not RUNTIME_STATE["use_custom_jd_prompt"]:
        RUNTIME_STATE["active_jd_prompt_template"] = (
            DEFAULT_JD_PROMPT_TEMPLATE
        )

    if not RUNTIME_STATE["use_custom_skill_gap_prompt"]:
        RUNTIME_STATE["active_skill_gap_prompt_template"] = (
            DEFAULT_SKILL_GAP_PROMPT_TEMPLATE
        )


def get_selected_model():
    if get_selected_provider() == "Gemini":
        return RUNTIME_STATE.get("gemini_model", GEMINI_MODEL_OPTIONS[0])

    return RUNTIME_STATE.get("ollama_model", DEFAULT_OLLAMA_MODEL)


def get_selected_provider():
    return RUNTIME_STATE.get("ai_provider", DEFAULT_AI_PROVIDER)


def get_model_options(provider=None):
    provider = provider or get_selected_provider()

    if provider == "Gemini":
        return GEMINI_MODEL_OPTIONS

    available_models = get_available_ollama_models()

    if available_models:
        return list(dict.fromkeys(available_models + OLLAMA_MODEL_OPTIONS))

    return OLLAMA_MODEL_OPTIONS


def get_jd_prompt_template():
    prompt = RUNTIME_STATE.get("active_jd_prompt_template", "")
    return prompt if prompt.strip() else DEFAULT_JD_PROMPT_TEMPLATE


def get_skill_gap_prompt_template():
    prompt = RUNTIME_STATE.get("active_skill_gap_prompt_template", "")
    return prompt if prompt.strip() else DEFAULT_SKILL_GAP_PROMPT_TEMPLATE


def get_candidate_detail_prompt_template():
    prompt = RUNTIME_STATE.get("active_candidate_detail_prompt_template", "")
    return (
        prompt
        if prompt.strip()
        else DEFAULT_CANDIDATE_DETAIL_PROMPT_TEMPLATE
    )


def get_candidate_grading_prompt_template():
    prompt = RUNTIME_STATE.get("active_candidate_grading_prompt_template", "")
    return (
        prompt
        if prompt.strip()
        else DEFAULT_CANDIDATE_GRADING_PROMPT_TEMPLATE
    )


def get_resume_skill_extraction_prompt_template():
    prompt = RUNTIME_STATE.get(
        "active_resume_skill_extraction_prompt_template",
        "",
    )
    return (
        prompt
        if prompt.strip()
        else DEFAULT_RESUME_SKILL_EXTRACTION_PROMPT_TEMPLATE
    )


def get_ai_cache_key(*parts):
    return "|".join(str(part) for part in parts)


def get_ai_cache():
    return RUNTIME_STATE.setdefault("ai_analysis_cache", {})


def ensure_vector_store_dir():
    VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)


def initialize_project_storage_files():
    ensure_vector_store_dir()

    if not FAISS_METADATA_PATH.exists():
        write_json_file(FAISS_METADATA_PATH, [])

    if not RESUME_SKILLS_PATH.exists():
        write_json_file(RESUME_SKILLS_PATH, {})

    if not PROMPT_CONFIG_PATH.exists():
        write_json_file(PROMPT_CONFIG_PATH, get_default_configuration())

    load_configuration()


def get_faiss_index_size():
    if faiss is None or not FAISS_INDEX_PATH.exists():
        return 0

    try:
        index = faiss.read_index(str(FAISS_INDEX_PATH))
        return int(index.ntotal)
    except Exception as error:
        RUNTIME_STATE["last_vector_store_error"] = str(error)
        return 0


def get_resume_database_records():
    initialize_project_storage_files()
    metadata = read_json_file(FAISS_METADATA_PATH, [])
    skills_store = read_json_file(RESUME_SKILLS_PATH, {})
    index_size = get_faiss_index_size()
    records = {}

    for item in metadata:
        if not isinstance(item, dict):
            continue

        resume_id = item.get("resume_id")

        if not resume_id:
            continue

        faiss_row = item.get("faiss_row")
        embedding_indexed = (
            FAISS_INDEX_PATH.exists()
            and isinstance(faiss_row, int)
            and 0 <= faiss_row < index_size
        )
        records[resume_id] = {
            "resume_id": resume_id,
            "resume_name": item.get("resume_name", "Unknown Resume"),
            "faiss_row": faiss_row,
            "embedding_model": item.get("embedding_model", ""),
            "embedding_indexed": embedding_indexed,
            "last_updated_at": item.get("last_updated_at", ""),
            "skills_indexed": False,
            "skills_model": "",
            "skill_count": 0,
            "status": "Embedding Indexed" if embedding_indexed else "Not Indexed",
        }

    for resume_id, item in skills_store.items():
        if not isinstance(item, dict):
            continue

        profile = item.get("skills", {})
        profile_skills = get_resume_profile_skills(profile)
        has_skill_signal = resume_skill_profile_has_signal(profile)

        if not has_skill_signal and resume_id not in records:
            continue

        existing = records.setdefault(
            resume_id,
            {
                "resume_id": resume_id,
                "resume_name": item.get("resume_name", "Unknown Resume"),
                "faiss_row": None,
                "embedding_model": "",
                "embedding_indexed": False,
                "last_updated_at": item.get("last_updated_at", ""),
                "skills_indexed": False,
                "skills_model": "",
                "skill_count": 0,
                "status": "Not Indexed",
            },
        )
        existing["resume_name"] = item.get(
            "resume_name",
            existing["resume_name"],
        )
        existing["skills_model"] = item.get("model", "")
        existing["skill_count"] = len(profile_skills)
        existing["skills_indexed"] = has_skill_signal
        existing["last_updated_at"] = (
            existing.get("last_updated_at")
            or item.get("last_updated_at", "")
        )

    for record in records.values():
        if record["embedding_indexed"] and record["skills_indexed"]:
            record["status"] = "Fully Indexed"
        elif record["embedding_indexed"] and record["skills_indexed"]:
            record["status"] = "Embedding + Skills"
        elif record["skills_indexed"]:
            record["status"] = "Skills Only"
        elif record["embedding_indexed"]:
            record["status"] = "Embedding Only"
        else:
            record["status"] = "Not Indexed"

    return sorted(
        records.values(),
        key=lambda item: item["resume_name"].lower(),
    )


def get_indexed_resume_analysis_records():
    if faiss is None or not FAISS_INDEX_PATH.exists():
        return []

    try:
        index, metadata = load_resume_vector_store()
    except Exception as error:
        RUNTIME_STATE["last_vector_store_error"] = str(error)
        return []

    skills_store = read_json_file(RESUME_SKILLS_PATH, {})
    analysis_records = []

    for item in metadata:
        if not isinstance(item, dict):
            continue

        resume_id = item.get("resume_id")
        resume_name = item.get("resume_name", "Unknown Resume")
        last_updated_at = item.get("last_updated_at", "")

        try:
            row = int(item.get("faiss_row"))
        except (TypeError, ValueError):
            continue

        if not resume_id or row < 0 or row >= int(index.ntotal):
            continue

        skills_item = skills_store.get(resume_id, {})
        resume_skill_profile = {}

        if isinstance(skills_item, dict):
            resume_skill_profile = normalize_resume_skill_profile(
                skills_item.get("skills", {}) or {}
            )
            last_updated_at = (
                last_updated_at
                or skills_item.get("last_updated_at", "")
            )

        analysis_records.append(
            {
                "resume_id": resume_id,
                "resume_name": resume_name,
                "resume_embedding": np.asarray(
                    [
                        index.reconstruct(row),
                    ],
                    dtype="float32",
                ),
                "resume_skill_profile": resume_skill_profile,
                "resume_text": format_resume_skill_profile(
                    resume_skill_profile
                )
                if resume_skill_profile_has_signal(resume_skill_profile)
                else "",
            }
        )

    RUNTIME_STATE["last_vector_store_error"] = ""
    RUNTIME_STATE["last_vector_store_status"] = (
        f"Loaded {len(analysis_records)} indexed resumes from Resume DB."
    )
    return analysis_records


def get_default_configuration():
    return {
        "ai_provider": DEFAULT_AI_PROVIDER,
        "ollama_model": DEFAULT_OLLAMA_MODEL,
        "gemini_model": GEMINI_MODEL_OPTIONS[0],
        "jd_prompt_template": DEFAULT_JD_PROMPT_TEMPLATE,
        "skill_gap_prompt_template": DEFAULT_SKILL_GAP_PROMPT_TEMPLATE,
        "candidate_detail_prompt_template": (
            DEFAULT_CANDIDATE_DETAIL_PROMPT_TEMPLATE
        ),
        "candidate_grading_prompt_template": (
            DEFAULT_CANDIDATE_GRADING_PROMPT_TEMPLATE
        ),
        "resume_skill_extraction_prompt_template": (
            DEFAULT_RESUME_SKILL_EXTRACTION_PROMPT_TEMPLATE
        ),
    }


def normalize_configuration(config):
    default_config = get_default_configuration()
    normalized_config = default_config.copy()

    if not isinstance(config, dict):
        return normalized_config

    for key, value in config.items():
        if key not in normalized_config or value is None:
            continue

        if key.endswith("_prompt_template"):
            if str(value).strip():
                normalized_config[key] = value
            continue

        normalized_config[key] = value

    resume_skill_prompt = str(
        normalized_config.get("resume_skill_extraction_prompt_template", "")
    )
    candidate_detail_prompt = str(
        normalized_config.get("candidate_detail_prompt_template", "")
    )
    candidate_grading_prompt = str(
        normalized_config.get("candidate_grading_prompt_template", "")
    )
    if "candidate resume context" not in candidate_detail_prompt:
        normalized_config["candidate_detail_prompt_template"] = (
            DEFAULT_CANDIDATE_DETAIL_PROMPT_TEMPLATE
        )

    if (
        "Do not use or mention the existing match score"
        not in candidate_grading_prompt
    ):
        normalized_config["candidate_grading_prompt_template"] = (
            DEFAULT_CANDIDATE_GRADING_PROMPT_TEMPLATE
        )

    if (
        "skill_evidence" not in resume_skill_prompt
        or "experience_timeline" in resume_skill_prompt
        or "resume_last_updated" in resume_skill_prompt
    ):
        normalized_config["resume_skill_extraction_prompt_template"] = (
            DEFAULT_RESUME_SKILL_EXTRACTION_PROMPT_TEMPLATE
        )

    return normalized_config


def load_configuration():
    saved_config = read_json_file(PROMPT_CONFIG_PATH, {})
    config = normalize_configuration(saved_config)

    RUNTIME_STATE["ai_provider"] = config["ai_provider"]
    RUNTIME_STATE["ollama_model"] = config["ollama_model"]
    RUNTIME_STATE["gemini_model"] = config["gemini_model"]
    RUNTIME_STATE["active_jd_prompt_template"] = config[
        "jd_prompt_template"
    ]
    RUNTIME_STATE["active_skill_gap_prompt_template"] = config[
        "skill_gap_prompt_template"
    ]
    RUNTIME_STATE["active_candidate_detail_prompt_template"] = config[
        "candidate_detail_prompt_template"
    ]
    RUNTIME_STATE["active_candidate_grading_prompt_template"] = config[
        "candidate_grading_prompt_template"
    ]
    RUNTIME_STATE["active_resume_skill_extraction_prompt_template"] = config[
        "resume_skill_extraction_prompt_template"
    ]
    return config


def get_configuration():
    return load_configuration()


def update_configuration(config):
    current_config = get_configuration()
    updated_config = normalize_configuration(
        {
            **current_config,
            **config,
        }
    )
    write_json_file(PROMPT_CONFIG_PATH, updated_config)
    load_configuration()
    RUNTIME_STATE["ai_analysis_cache"] = {}
    return updated_config


def reset_configuration():
    default_config = get_default_configuration()
    write_json_file(PROMPT_CONFIG_PATH, default_config)
    load_configuration()
    RUNTIME_STATE["ai_analysis_cache"] = {}
    return default_config


def read_json_file(path, default):
    try:
        if not path.exists():
            return default

        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return default


def write_json_file(path, data):
    ensure_vector_store_dir()

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def get_file_bytes(file):
    if hasattr(file, "seek"):
        file.seek(0)

    content = file.read()

    if hasattr(file, "seek"):
        file.seek(0)

    return content


def get_resume_id(file):
    return hashlib.sha256(get_file_bytes(file)).hexdigest()


def apply_prompt_configuration():
    jd_prompt = RUNTIME_STATE.get("jd_prompt_template", "")
    skill_gap_prompt = RUNTIME_STATE.get("skill_gap_prompt_template", "")

    RUNTIME_STATE["use_custom_jd_prompt"] = (
        jd_prompt.strip() != DEFAULT_JD_PROMPT_TEMPLATE.strip()
    )
    RUNTIME_STATE["use_custom_skill_gap_prompt"] = (
        skill_gap_prompt.strip() != DEFAULT_SKILL_GAP_PROMPT_TEMPLATE.strip()
    )

    RUNTIME_STATE["active_jd_prompt_template"] = (
        jd_prompt if jd_prompt.strip() else DEFAULT_JD_PROMPT_TEMPLATE
    )
    RUNTIME_STATE["active_skill_gap_prompt_template"] = (
        skill_gap_prompt
        if skill_gap_prompt.strip()
        else DEFAULT_SKILL_GAP_PROMPT_TEMPLATE
    )


def safe_json_extract(text):
    cleaned = text.strip()
    cleaned = cleaned.replace("```json", "")
    cleaned = cleaned.replace("```", "")

    start = cleaned.find("{")

    if start == -1:
        return None

    try:
        decoder = json.JSONDecoder()
        data, _ = decoder.raw_decode(cleaned[start:])
        return data
    except json.JSONDecodeError:
        return None


def safe_ollama_json(prompt, schema, fallback, model_name=None):
    try:
        response = ollama.chat(
            model=model_name or get_selected_model(),
            format="json",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a JSON API. Return one valid JSON object "
                        "only. Do not include markdown or explanations."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            options={
                "temperature": 0,
            },
        )

        result = response["message"]["content"]
        data = safe_json_extract(result)

        if data is None:
            RUNTIME_STATE["last_ai_error"] = (
                "The model did not return valid JSON."
            )
            return fallback

        validate(instance=data, schema=schema)
        RUNTIME_STATE["last_ai_error"] = ""
        return data

    except (KeyError, TypeError, ValidationError, Exception) as error:
        RUNTIME_STATE["last_ai_error"] = str(error)
        return fallback


def safe_gemini_json(prompt, schema, fallback, model_name=None):
    try:
        if genai is None:
            raise RuntimeError(
                "Install google-genai to use Gemini models."
            )

        if not os.getenv("GEMINI_API_KEY"):
            raise RuntimeError(
                "Set GEMINI_API_KEY to use Gemini models."
            )

        client = genai.Client()
        selected_model = model_name or get_selected_model()

        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=selected_model,
                    contents=prompt,
                    config={
                        "temperature": 0,
                        "response_mime_type": "application/json",
                        "response_schema": schema,
                    },
                )
                break
            except Exception as error:
                message = str(error)
                is_transient = any(
                    code in message
                    for code in GEMINI_TRANSIENT_ERROR_CODES
                )

                if not is_transient or attempt == 2:
                    raise

                time.sleep(2)

        data = safe_json_extract(response.text or "")

        if data is None:
            RUNTIME_STATE["last_ai_error"] = (
                "The model did not return valid JSON."
            )
            return fallback

        validate(instance=data, schema=schema)
        RUNTIME_STATE["last_ai_error"] = ""
        return data

    except (KeyError, TypeError, ValidationError, Exception) as error:
        RUNTIME_STATE["last_ai_error"] = str(error)
        return fallback


def safe_ai_json(prompt, schema, fallback, model_name=None, provider=None):
    provider = provider or get_selected_provider()

    if provider == "Gemini":
        return safe_gemini_json(
            prompt,
            schema,
            fallback,
            model_name=model_name,
        )

    return safe_ollama_json(
        prompt,
        schema,
        fallback,
        model_name=model_name,
    )


def format_prompt(template, **values):
    prompt = template
    used_placeholder = False

    for key, value in values.items():
        placeholder = "{" + key + "}"

        if placeholder in prompt:
            used_placeholder = True

        prompt = prompt.replace(
            placeholder,
            str(value),
        )

    if used_placeholder:
        return prompt

    return prompt + "\n\n" + "\n\n".join(
        f"{key.upper()}:\n{value}" for key, value in values.items()
    )


def validate_upload(file):
    max_size = 10 * 1024 * 1024
    allowed_extensions = (".pdf", ".docx")
    file_name = getattr(file, "name", "")
    lower_name = file_name.lower()

    if not lower_name.endswith(allowed_extensions):
        return False, "Unsupported file type. Upload PDF or DOCX files only."

    if hasattr(file, "seek"):
        file.seek(0)

    content = file.read()

    if hasattr(file, "seek"):
        file.seek(0)

    if len(content) > max_size:
        return False, "File is too large. Maximum size is 10 MB."

    if lower_name.endswith(".pdf") and not content.startswith(b"%PDF"):
        return False, "Invalid PDF file."

    if lower_name.endswith(".docx") and not content.startswith(b"PK"):
        return False, "Invalid DOCX file."

    return True, ""


def normalize_skill_list(value):
    if isinstance(value, dict):
        value = list(value.values())

    if isinstance(value, str):
        value = [
            item.strip(" -•\t")
            for item in value.replace("\n", ",").split(",")
        ]

    if not isinstance(value, list):
        return []

    return [
        str(item).strip()
        for item in value
        if str(item).strip()
    ][:10]


def split_skill_text(value):
    if isinstance(value, list):
        values = value
    elif isinstance(value, dict):
        values = value.values()
    else:
        values = str(value or "").replace("\n", ",").split(",")

    return normalize_skill_list(list(values))


def normalize_match_text(value):
    return " ".join(
        "".join(
            character.lower() if character.isalnum() else " "
            for character in str(value)
        ).split()
    )


def skill_matches_text(skill, text):
    skill_text = normalize_match_text(skill)
    target_text = normalize_match_text(text)

    if not skill_text or not target_text:
        return False

    if skill_text in target_text:
        return True

    skill_tokens = [
        token
        for token in skill_text.split()
        if len(token) > 2
    ]

    if not skill_tokens:
        return False

    target_tokens = set(target_text.split())
    matched_tokens = [
        token
        for token in skill_tokens
        if token in target_tokens
    ]
    required_matches = 1 if len(skill_tokens) <= 2 else 2
    return len(matched_tokens) >= required_matches


def get_resume_profile_skills(profile):
    if not isinstance(profile, dict):
        return []

    skills = []

    for key in [
        "technical_skills",
        "soft_skills",
        "tools",
        "domains",
    ]:
        skills.extend(normalize_skill_list(profile.get(key, [])))

    unique_skills = []
    seen = set()

    for skill in skills:
        normalized = normalize_match_text(skill)

        if normalized and normalized not in seen:
            seen.add(normalized)
            unique_skills.append(skill)

    return unique_skills


def normalize_skill_evidence(value):
    if not isinstance(value, list):
        return []

    evidence_rows = []

    for item in value:
        if isinstance(item, dict):
            skill = display_value(item.get("skill"), "")
            evidence = display_value(
                get_first_present(
                    item,
                    ["evidence", "quote", "line", "context"],
                    "",
                ),
                "",
            )
            source = display_value(
                get_first_present(
                    item,
                    ["source", "project", "role", "section"],
                    "",
                ),
                "",
            )
        else:
            skill = ""
            evidence = display_value(item, "")
            source = ""

        if evidence and evidence != "Not Found":
            evidence_rows.append(
                {
                    "skill": skill,
                    "evidence": evidence,
                    "source": "" if source == "Not Found" else source,
                }
            )

    return evidence_rows[:30]


TECHNICAL_SKILL_KEYWORDS = [
    "Python",
    "Java",
    "JavaScript",
    "TypeScript",
    "React",
    "Angular",
    "Vue",
    "Node.js",
    "FastAPI",
    "Flask",
    "Django",
    "Spring Boot",
    "SQL",
    "PostgreSQL",
    "MySQL",
    "MongoDB",
    "Oracle",
    "AWS",
    "Azure",
    "GCP",
    "Docker",
    "Kubernetes",
    "Kafka",
    "REST",
    "GraphQL",
    "Machine Learning",
    "Deep Learning",
    "NLP",
    "TensorFlow",
    "PyTorch",
    "Pandas",
    "NumPy",
    "Power BI",
    "Tableau",
    "Excel",
    "HTML",
    "CSS",
    "Git",
    "Jenkins",
    "CI/CD",
    "Linux",
    "BPM",
    "BRMS",
    "IBM BPM",
    "Flowable",
    "Drools",
]

SOFT_SKILL_KEYWORDS = [
    "Communication",
    "Leadership",
    "Collaboration",
    "Stakeholder Management",
    "Problem Solving",
    "Project Management",
    "People Management",
    "Analytical",
    "Decision Making",
    "Mentoring",
]

DOMAIN_KEYWORDS = [
    "Banking",
    "Healthcare",
    "Insurance",
    "Finance",
    "Recruiting",
    "Retail",
    "E-commerce",
    "Telecom",
    "Manufacturing",
    "Education",
]


def find_keywords_in_text(text, keywords, limit=15):
    found = []
    normalized_text = normalize_match_text(text)

    for keyword in keywords:
        if skill_matches_text(keyword, normalized_text):
            found.append(keyword)

        if len(found) >= limit:
            break

    return found


def find_evidence_line(text, skill):
    for line in text.splitlines():
        cleaned = line.strip(" -\t")

        if cleaned and skill_matches_text(skill, cleaned):
            return cleaned[:280]

    return ""


def build_local_resume_skill_profile(resume_text):
    text = display_value(resume_text, "")

    if not text or text == "Not Found":
        return normalize_resume_skill_profile(RESUME_SKILL_FALLBACK)

    technical_skills = find_keywords_in_text(
        text,
        TECHNICAL_SKILL_KEYWORDS,
    )
    soft_skills = find_keywords_in_text(
        text,
        SOFT_SKILL_KEYWORDS,
        limit=10,
    )
    domains = find_keywords_in_text(
        text,
        DOMAIN_KEYWORDS,
        limit=10,
    )
    tool_keywords = {
        "Git",
        "Jenkins",
        "Docker",
        "Kubernetes",
        "Kafka",
        "Power BI",
        "Tableau",
        "Excel",
        "IBM BPM",
        "Flowable",
        "Drools",
    }
    tools = [
        skill
        for skill in technical_skills
        if skill in tool_keywords
    ][:15]
    evidence = []

    for skill in technical_skills[:10]:
        line = find_evidence_line(text, skill)

        if line:
            evidence.append(
                {
                    "skill": skill,
                    "evidence": line,
                    "source": "Resume text",
                }
            )

    summary_lines = [
        line.strip()
        for line in text.splitlines()
        if len(line.strip()) > 40
    ][:3]
    summary = " ".join(summary_lines)[:700] or "Not Found"

    return normalize_resume_skill_profile(
        {
            "technical_skills": technical_skills,
            "soft_skills": soft_skills,
            "tools": tools,
            "domains": domains,
            "experience_summary": summary,
            "skill_evidence": evidence,
        }
    )


def build_matching_skill_evidence(resume_skill_profile, matching_skills):
    safe_matching_skills = normalize_skill_list(matching_skills)
    evidence_rows = normalize_skill_evidence(
        resume_skill_profile.get("skill_evidence", [])
        if isinstance(resume_skill_profile, dict)
        else []
    )
    summary = display_value(
        resume_skill_profile.get("experience_summary")
        if isinstance(resume_skill_profile, dict)
        else "",
        "",
    )
    matching_evidence = []

    for skill in safe_matching_skills:
        evidence_match = None

        for row in evidence_rows:
            evidence_skill = row.get("skill", "")
            evidence_text = row.get("evidence", "")

            if (
                skill_matches_text(skill, evidence_skill)
                or skill_matches_text(evidence_skill, skill)
                or skill_matches_text(skill, evidence_text)
            ):
                evidence_match = row
                break

        if evidence_match:
            matching_evidence.append(
                {
                    "skill": skill,
                    "evidence": evidence_match["evidence"],
                    "source": evidence_match.get("source", ""),
                }
            )
        elif summary and summary != "Not Found":
            matching_evidence.append(
                {
                    "skill": skill,
                    "evidence": summary,
                    "source": "Indexed experience summary",
                }
            )
        else:
            matching_evidence.append(
                {
                    "skill": skill,
                    "evidence": (
                        "Evidence is not available yet. Re-upload or reindex "
                        "this resume to generate evidence-backed skills."
                    ),
                    "source": "Resume DB",
                }
            )

    return matching_evidence


def get_job_required_skills(job_text, job_skill_requirements=None):
    skills = []

    if isinstance(job_skill_requirements, dict):
        for key in [
            "primary_skills",
            "secondary_skills",
            "required_skills",
            "skills",
            "technical_skills",
        ]:
            skills.extend(split_skill_text(job_skill_requirements.get(key)))

    if not skills:
        skills.extend(split_skill_text(job_text))

    unique_skills = []
    seen = set()

    for skill in skills:
        normalized = normalize_match_text(skill)

        if normalized and normalized not in seen:
            seen.add(normalized)
            unique_skills.append(skill)

    return unique_skills[:20]


def remove_placeholder_skills(skills):
    placeholders = {
        "not found",
        "none",
        "n/a",
        "na",
        "not applicable",
        "no missing skills",
        "no major gaps",
    }
    cleaned = []

    for skill in normalize_skill_list(skills):
        normalized = normalize_match_text(skill)

        if normalized and normalized not in placeholders:
            cleaned.append(skill)

    return cleaned


def merge_missing_skills(ai_missing_skills, indexed_missing_skills):
    ai_skills = remove_placeholder_skills(ai_missing_skills)

    if ai_skills:
        return ai_skills[:10]

    return remove_placeholder_skills(indexed_missing_skills)[:10]


def build_indexed_candidate_detail(
    resume_skill_profile,
    job_text,
    score,
    job_skill_requirements=None,
):
    resume_skills = get_resume_profile_skills(resume_skill_profile)
    required_skills = get_job_required_skills(
        job_text,
        job_skill_requirements,
    )

    matching_skills = [
        skill
        for skill in resume_skills
        if skill_matches_text(skill, job_text)
    ][:10]
    missing_skills = []

    for required_skill in required_skills:
        has_skill = any(
            skill_matches_text(required_skill, resume_skill)
            or skill_matches_text(resume_skill, required_skill)
            for resume_skill in resume_skills
        )

        if not has_skill:
            missing_skills.append(required_skill)

    missing_skills = missing_skills[:10]

    if matching_skills:
        strongest = ", ".join(matching_skills[:3])
    else:
        strongest = "No strong indexed skill overlap was found"

    if missing_skills:
        gaps = ", ".join(missing_skills[:3])
    else:
        gaps = "no major indexed skill gaps were found"

    justification = (
        f"The {score}% match is based on indexed resume skills such as "
        f"{strongest}. "
        f"The main indexed gaps are {gaps}."
    )

    return {
        "matching_skills": matching_skills,
        "missing_skills": missing_skills,
        "justification": justification,
        "matching_evidence": build_matching_skill_evidence(
            resume_skill_profile,
            matching_skills,
        ),
    }


def normalize_key(key):
    return "".join(
        character
        for character in str(key).lower()
        if character.isalnum()
    )


def flatten_dict(data):
    if not isinstance(data, dict):
        return {}

    flattened = {}

    for key, value in data.items():
        flattened[key] = value

        if isinstance(value, dict):
            flattened.update(flatten_dict(value))

    return flattened


def get_first_present(data, keys, default=None):
    if not isinstance(data, dict):
        return default

    flattened = flatten_dict(data)
    lower_key_map = {
        str(key).lower(): value
        for key, value in flattened.items()
    }
    normalized_key_map = {
        normalize_key(key): value
        for key, value in flattened.items()
    }

    for key in keys:
        if key in flattened:
            return flattened[key]

        value = lower_key_map.get(key.lower())

        if value is not None:
            return value

        value = normalized_key_map.get(normalize_key(key))

        if value is not None:
            return value

    return default


def display_value(value, default="Not Found"):
    if isinstance(value, list):
        values = [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]
        return ", ".join(values) if values else default

    if isinstance(value, dict):
        values = [
            str(item).strip()
            for item in value.values()
            if str(item).strip()
        ]
        return ", ".join(values) if values else default

    if value is None:
        return default

    value = str(value).strip()
    return value if value else default


def get_runtime_status():
    return {
        "last_ai_error": RUNTIME_STATE.get("last_ai_error", ""),
        "last_vector_store_error": RUNTIME_STATE.get("last_vector_store_error", ""),
        "last_vector_store_status": RUNTIME_STATE.get("last_vector_store_status", ""),
        "last_resume_skill_status": RUNTIME_STATE.get("last_resume_skill_status", ""),
        "grading_checkpoints": RUNTIME_STATE.get("grading_checkpoints", []),
    }


def clear_runtime_status():
    RUNTIME_STATE["last_ai_error"] = ""
    RUNTIME_STATE["last_vector_store_error"] = ""
    RUNTIME_STATE["last_vector_store_status"] = ""
    RUNTIME_STATE["last_resume_skill_status"] = ""
    RUNTIME_STATE["grading_checkpoints"] = []
    RUNTIME_STATE["skip_gemini_grading"] = False


def add_grading_checkpoint(checkpoint):
    checkpoints = RUNTIME_STATE.setdefault("grading_checkpoints", [])

    if not isinstance(checkpoint, dict):
        checkpoint = {
            "message": str(checkpoint),
        }

    checkpoints.append(checkpoint)
    RUNTIME_STATE["grading_checkpoints"] = checkpoints[-25:]


def summarize_gemini_error(error):
    error_text = display_value(error, "")

    if not error_text:
        return ""

    if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
        return "Gemini quota exhausted; local fallback used."

    if "503" in error_text or "UNAVAILABLE" in error_text:
        return "Gemini temporarily unavailable; local fallback used."

    if "GEMINI_API_KEY" in error_text:
        return "Gemini API key missing; local fallback used."

    return error_text[:180]


# ==================================================
# EXTRACT TEXT
# ==================================================

def extract_pdf_text(pdf_file):
    text = ""
    reader = PdfReader(pdf_file)

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return text


def extract_docx_text(docx_file):
    document = Document(docx_file)
    text = ""

    for paragraph in document.paragraphs:
        text += paragraph.text + "\n"

    return text


def extract_text(file):
    if hasattr(file, "seek"):
        file.seek(0)

    if file.name.endswith(".pdf"):
        return extract_pdf_text(file)

    if file.name.endswith(".docx"):
        return extract_docx_text(file)

    return ""


# ==================================================
# MATCH SCORE
# ==================================================

def calculate_match_score(resume_embedding, job_text):
    if isinstance(resume_embedding, str):
        resume_embedding = encode_text_embedding(
            resume_embedding,
            "Represent this resume for retrieval:",
        )

    job_embedding = encode_text_embedding(
        job_text,
        "Represent this description for matching:",
    )
    similarity = cosine_similarity(
        resume_embedding,
        job_embedding,
    )

    score = float(similarity[0][0]) * 100
    return round(score, 2)


# ==================================================
# AI ANALYSIS
# ==================================================

def analyze_job_description(
    job_text,
    model_name=None,
    prompt_template=None,
    provider=None,
):
    prompt_template = prompt_template or get_jd_prompt_template()
    provider = provider or get_selected_provider()
    cache_key = get_ai_cache_key(
        "job_description",
        provider,
        model_name or get_selected_model(),
        prompt_template,
        job_text,
    )
    cache = get_ai_cache()

    if cache_key in cache:
        return cache[cache_key]

    prompt = format_prompt(
        prompt_template,
        job_text=job_text,
    )

    data = safe_ai_json(
        prompt,
        JD_RESPONSE_SCHEMA,
        JD_FALLBACK,
        model_name=model_name,
        provider=provider,
    )

    result = {
        "experience": get_first_present(
            data,
            [
                "experience",
                "years_of_experience",
                "years_experience",
                "experience_required",
                "years_of_experience_required",
                "years of experience required",
                "required_experience",
            ],
            "Not Found",
        ),
        "primary_skills": get_first_present(
            data,
            [
                "primary_skills",
                "required_skills",
                "skills",
                "technical_skills",
                "primary skills",
                "core_skills",
                "must_have_skills",
            ],
            "Not Found",
        ),
        "secondary_skills": get_first_present(
            data,
            [
                "secondary_skills",
                "preferred_skills",
                "nice_to_have_skills",
                "additional_skills",
                "secondary skills",
                "optional_skills",
            ],
            "Not Found",
        ),
        "education": get_first_present(
            data,
            [
                "education",
                "educational_qualifications",
                "qualifications",
                "degree",
                "educational qualifications",
                "education_required",
            ],
            "Not Found",
        ),
    }

    if not RUNTIME_STATE.get("last_ai_error"):
        cache[cache_key] = result

    return result


def analyze_skill_gap(
    resume_text,
    job_text,
    model_name=None,
    prompt_template=None,
):
    prompt = format_prompt(
        prompt_template or DEFAULT_SKILL_GAP_PROMPT_TEMPLATE,
        resume_text=resume_text,
        job_text=job_text,
    )

    data = safe_ai_json(
        prompt,
        SKILL_GAP_SCHEMA,
        SKILL_GAP_FALLBACK,
        model_name=model_name,
    )

    return {
        "matching_skills": normalize_skill_list(
            get_first_present(
                data,
                [
                    "matching_skills",
                    "matched_skills",
                    "present_skills",
                    "skills_matched",
                    "matching skills",
                    "matched skills",
                    "relevant_skills",
                ],
                [],
            ),
        ),
        "missing_skills": normalize_skill_list(
            get_first_present(
                data,
                [
                    "missing_skills",
                    "skill_gaps",
                    "gaps",
                    "skills_missing",
                    "missing skills",
                    "skill gaps",
                    "required_missing_skills",
                ],
                [],
            ),
        ),
    }


def analyze_match_justification(
    resume_text,
    job_text,
    score,
    model_name=None,
):
    prompt = format_prompt(
        DEFAULT_MATCH_JUSTIFICATION_PROMPT_TEMPLATE,
        resume_text=resume_text,
        job_text=job_text,
        score=score,
    )

    data = safe_ai_json(
        prompt,
        MATCH_JUSTIFICATION_SCHEMA,
        MATCH_JUSTIFICATION_FALLBACK,
        model_name=model_name,
    )

    justification = get_first_present(
        data,
        [
            "justification",
            "match_justification",
            "score_justification",
            "reason",
            "summary",
        ],
        MATCH_JUSTIFICATION_FALLBACK["justification"],
    )

    return display_value(
        justification,
        MATCH_JUSTIFICATION_FALLBACK["justification"],
    )


def normalize_candidate_detail(data):
    return {
        "matching_skills": normalize_skill_list(
            get_first_present(
                data,
                [
                    "matching_skills",
                    "matched_skills",
                    "present_skills",
                    "skills_matched",
                    "matching skills",
                    "matched skills",
                    "relevant_skills",
                ],
                [],
            ),
        ),
        "missing_skills": normalize_skill_list(
            get_first_present(
                data,
                [
                    "missing_skills",
                    "skill_gaps",
                    "gaps",
                    "skills_missing",
                    "missing skills",
                    "skill gaps",
                    "required_missing_skills",
                ],
                [],
            ),
        ),
        "justification": display_value(
            get_first_present(
                data,
                [
                    "justification",
                    "match_justification",
                    "score_justification",
                    "reason",
                    "summary",
                ],
                CANDIDATE_DETAIL_FALLBACK["justification"],
            ),
            CANDIDATE_DETAIL_FALLBACK["justification"],
        ),
    }


def normalize_candidate_grading(data):
    grade = display_value(
        get_first_present(
            data,
            [
                "grade",
                "candidate_grade",
                "fit_grade",
                "rating",
            ],
            CANDIDATE_GRADING_FALLBACK["grade"],
        ),
        CANDIDATE_GRADING_FALLBACK["grade"],
    ).upper()
    allowed_grades = {"A", "B", "C", "D", "F"}

    if grade not in allowed_grades:
        grade = next(
            (
                candidate_grade
                for candidate_grade in ["A", "B", "C", "D", "F"]
                if candidate_grade in grade
            ),
            CANDIDATE_GRADING_FALLBACK["grade"],
        )

    return {
        "grade": grade,
        "summary": display_value(
            get_first_present(
                data,
                [
                    "summary",
                    "explanation",
                    "rationale",
                    "grading_summary",
                ],
                CANDIDATE_GRADING_FALLBACK["summary"],
            ),
            CANDIDATE_GRADING_FALLBACK["summary"],
        ),
        "strengths": remove_placeholder_skills(
            get_first_present(
                data,
                [
                    "strengths",
                    "positives",
                    "key_strengths",
                ],
                [],
            ),
        )[:6],
        "concerns": remove_placeholder_skills(
            get_first_present(
                data,
                [
                    "concerns",
                    "risks",
                    "weaknesses",
                    "gaps",
                ],
                [],
            ),
        )[:6],
    }


def normalize_resume_skill_profile(data):
    return {
        "technical_skills": normalize_skill_list(
            data.get("technical_skills", [])
        ),
        "soft_skills": normalize_skill_list(
            data.get("soft_skills", [])
        ),
        "tools": normalize_skill_list(
            data.get("tools", [])
        ),
        "domains": normalize_skill_list(
            data.get("domains", [])
        ),
        "experience_summary": display_value(
            data.get("experience_summary"),
            "Not Found",
        ),
        "skill_evidence": normalize_skill_evidence(
            data.get("skill_evidence", [])
        ),
    }


def resume_skill_profile_has_signal(profile):
    if not isinstance(profile, dict):
        return False

    if "MagicMock" in json.dumps(profile, default=str):
        return False

    skill_keys = [
        "technical_skills",
        "soft_skills",
        "tools",
        "domains",
    ]

    if any(profile.get(key) for key in skill_keys):
        return True

    return display_value(
        profile.get("experience_summary"),
        "",
    ) != "Not Found"


def is_complete_resume_skill_profile(profile):
    if not isinstance(profile, dict):
        return False

    required_keys = [
        "technical_skills",
        "soft_skills",
        "tools",
        "domains",
        "experience_summary",
        "skill_evidence",
    ]

    return all(key in profile for key in required_keys)


def get_resume_skill_profile(resume_id, resume_name, resume_text):
    skills_store = read_json_file(RESUME_SKILLS_PATH, {})
    existing = skills_store.get(resume_id)
    previous_ai_error = RUNTIME_STATE.get("last_ai_error", "")

    if (
        isinstance(existing, dict)
        and existing.get("model") in [
            GEMINI_RESUME_SKILL_MODEL,
            "local-fallback",
        ]
        and is_complete_resume_skill_profile(existing.get("skills"))
        and resume_skill_profile_has_signal(existing.get("skills"))
    ):
        RUNTIME_STATE["last_resume_skill_status"] = (
            f"Loaded cached Gemini skills for {resume_name}."
        )
        return existing["skills"]

    prompt = format_prompt(
        get_resume_skill_extraction_prompt_template(),
        resume_text=resume_text,
    )
    data = safe_gemini_json(
        prompt,
        RESUME_SKILL_SCHEMA,
        RESUME_SKILL_FALLBACK,
        model_name=GEMINI_RESUME_SKILL_MODEL,
    )
    resume_skill_error = RUNTIME_STATE.get("last_ai_error", "")
    profile = normalize_resume_skill_profile(data)
    local_profile = None
    profile_model = GEMINI_RESUME_SKILL_MODEL

    if resume_skill_error:
        local_profile = build_local_resume_skill_profile(resume_text)

        if resume_skill_profile_has_signal(local_profile):
            skills_store[resume_id] = {
                "resume_id": resume_id,
                "resume_name": resume_name,
                "skills": local_profile,
                "model": "local-fallback",
                "last_updated_at": get_current_timestamp(),
            }
            write_json_file(RESUME_SKILLS_PATH, skills_store)
            RUNTIME_STATE["last_resume_skill_status"] = (
                f"Saved local fallback skills for {resume_name}: "
                f"{resume_skill_error}"
            )
            RUNTIME_STATE["last_ai_error"] = previous_ai_error
            return local_profile

        RUNTIME_STATE["last_resume_skill_status"] = (
            f"Could not save Gemini skills for {resume_name}: "
            f"{resume_skill_error}"
        )
        RUNTIME_STATE["last_ai_error"] = previous_ai_error
        return profile

    if not resume_skill_profile_has_signal(profile):
        local_profile = local_profile or build_local_resume_skill_profile(
            resume_text
        )

        if resume_skill_profile_has_signal(local_profile):
            profile = local_profile
            profile_model = "local-fallback"

    skills_store[resume_id] = {
        "resume_id": resume_id,
        "resume_name": resume_name,
        "skills": profile,
        "model": profile_model,
        "last_updated_at": get_current_timestamp(),
    }
    write_json_file(RESUME_SKILLS_PATH, skills_store)
    if profile_model == "local-fallback":
        RUNTIME_STATE["last_resume_skill_status"] = (
            f"Saved local fallback skills for {resume_name}."
        )
    else:
        RUNTIME_STATE["last_resume_skill_status"] = (
            f"Saved Gemini skills for {resume_name}."
        )
    RUNTIME_STATE["last_ai_error"] = previous_ai_error
    return profile


def format_resume_skill_profile(profile):
    return json.dumps(
        profile,
        ensure_ascii=False,
        indent=2,
    )


def build_resume_analysis_context(resume_text, resume_skill_profile):
    raw_resume_text = display_value(resume_text, "")
    has_raw_resume_text = raw_resume_text and raw_resume_text != "Not Found"
    has_indexed_profile = resume_skill_profile_has_signal(
        resume_skill_profile
    )

    if has_raw_resume_text and has_indexed_profile:
        return (
            "RAW RESUME TEXT:\n"
            f"{raw_resume_text}\n\n"
            "INDEXED RESUME PROFILE:\n"
            f"{format_resume_skill_profile(resume_skill_profile)}"
        )

    if has_raw_resume_text:
        return raw_resume_text

    if has_indexed_profile:
        return (
            "INDEXED RESUME PROFILE:\n"
            f"{format_resume_skill_profile(resume_skill_profile)}"
        )

    return ""


def build_candidate_grading_fallback(
    resume_context,
    matching_skills,
    missing_skills,
):
    matching_skills = remove_placeholder_skills(matching_skills)
    missing_skills = remove_placeholder_skills(missing_skills)
    resume_context_text = display_value(resume_context, "")
    lower_context = resume_context_text.lower()
    total_skill_signals = len(matching_skills) + len(missing_skills)
    match_ratio = (
        len(matching_skills) / total_skill_signals
        if total_skill_signals
        else 0
    )
    project_signal_count = sum(
        1
        for keyword in [
            "project",
            "implemented",
            "built",
            "developed",
            "deployed",
            "designed",
            "experience",
        ]
        if keyword in lower_context
    )

    if match_ratio >= 0.8 and project_signal_count >= 2:
        grade = "A"
    elif match_ratio >= 0.65:
        grade = "B"
    elif match_ratio >= 0.4:
        grade = "C"
    elif match_ratio >= 0.2:
        grade = "D"
    else:
        grade = "F"

    strengths = []
    concerns = []

    if matching_skills:
        strengths.append(
            "Matches key requirements including "
            f"{', '.join(matching_skills[:4])}."
        )

    if project_signal_count >= 2:
        strengths.append(
            "Resume context includes hands-on project or implementation "
            "signals."
        )
    elif matching_skills:
        concerns.append(
            "Hands-on project evidence is limited or unclear for the matched "
            "skills."
        )

    if missing_skills:
        concerns.append(
            "Missing or unclear required skills include "
            f"{', '.join(missing_skills[:4])}."
        )

    if not matching_skills:
        concerns.append(
            "No strong matching skills were found from the candidate detail "
            "analysis."
        )

    if not strengths:
        strengths.append(
            "Some resume context is available for review, but strong fit "
            "signals are limited."
        )

    if not concerns:
        concerns.append(
            "No major concerns were detected from the extracted matching and "
            "missing skills."
        )

    summary = (
        f"Grade {grade} is based on {len(matching_skills)} matching skill "
        f"signal(s), {len(missing_skills)} missing skill signal(s), and "
        "available resume evidence. "
        "This grade does not use the generated match score."
    )

    return {
        "grade": grade,
        "summary": summary,
        "strengths": strengths[:6],
        "concerns": concerns[:6],
    }


def candidate_grading_is_usable(candidate_grading):
    if not isinstance(candidate_grading, dict):
        return False

    grade = display_value(candidate_grading.get("grade"), "")
    summary = display_value(candidate_grading.get("summary"), "")

    return (
        grade != "Not Found"
        and summary
        and summary != CANDIDATE_GRADING_FALLBACK["summary"]
    )


def ensure_candidate_grading(
    candidate_detail,
    resume_context="",
    matching_skills=None,
    missing_skills=None,
):
    if candidate_grading_is_usable(
        candidate_detail.get("candidate_grading")
        if isinstance(candidate_detail, dict)
        else None
    ):
        return candidate_detail

    if not isinstance(candidate_detail, dict):
        candidate_detail = {}

    fallback_grading = build_candidate_grading_fallback(
        resume_context,
        matching_skills
        if matching_skills is not None
        else candidate_detail.get("matching_skills", []),
        missing_skills
        if missing_skills is not None
        else candidate_detail.get("missing_skills", []),
    )
    fallback_grading["debug"] = {
        "resume_name": candidate_detail.get("resume_name", ""),
        "resume_context_chars": len(display_value(resume_context, "")),
        "matching_skill_count": len(
            remove_placeholder_skills(
                matching_skills
                if matching_skills is not None
                else candidate_detail.get("matching_skills", [])
            )
        ),
        "missing_skill_count": len(
            remove_placeholder_skills(
                missing_skills
                if missing_skills is not None
                else candidate_detail.get("missing_skills", [])
            )
        ),
        "cache": "guard",
        "source": "api_guard_fallback",
        "gemini_error": "",
        "gemini_grade": "",
        "final_grade": fallback_grading.get("grade", ""),
    }
    candidate_detail["candidate_grading"] = fallback_grading
    add_grading_checkpoint(fallback_grading["debug"])
    return candidate_detail


def analyze_candidate_grading(
    resume_context,
    job_text,
    matching_skills,
    missing_skills,
    prompt_template=None,
    resume_name="",
):
    prompt_template = (
        prompt_template or get_candidate_grading_prompt_template()
    )
    matching_skills = remove_placeholder_skills(matching_skills)
    missing_skills = remove_placeholder_skills(missing_skills)
    debug = {
        "resume_name": resume_name,
        "resume_context_chars": len(display_value(resume_context, "")),
        "job_description_chars": len(display_value(job_text, "")),
        "matching_skill_count": len(matching_skills),
        "missing_skill_count": len(missing_skills),
        "cache": "miss",
        "source": "",
        "gemini_error": "",
        "gemini_grade": "",
        "final_grade": "",
    }
    cache_key = get_ai_cache_key(
        "candidate_grading_v3",
        GEMINI_RESUME_SKILL_MODEL,
        resume_context,
        job_text,
        json.dumps(matching_skills, ensure_ascii=False),
        json.dumps(missing_skills, ensure_ascii=False),
        prompt_template,
    )
    cache = get_ai_cache()

    if cache_key in cache and candidate_grading_is_usable(cache[cache_key]):
        cached_error = (
            cache[cache_key]
            .get("debug", {})
            .get("gemini_error", "")
        )
        cached_result = {
            **cache[cache_key],
            "debug": {
                **debug,
                "cache": "hit",
                "source": "cache",
                "gemini_error": summarize_gemini_error(cached_error),
                "final_grade": cache[cache_key].get("grade", ""),
            },
        }
        add_grading_checkpoint(cached_result["debug"])
        return cached_result

    previous_ai_error = RUNTIME_STATE.get("last_ai_error", "")
    fallback_result = build_candidate_grading_fallback(
        resume_context,
        matching_skills,
        missing_skills,
    )

    if RUNTIME_STATE.get("skip_gemini_grading"):
        fallback_result = {
            **fallback_result,
            "debug": {
                **debug,
                "source": "local_fallback",
                "gemini_error": (
                    "Gemini grading skipped after a previous quota or "
                    "availability error in this run."
                ),
                "final_grade": fallback_result.get("grade", ""),
            },
        }
        add_grading_checkpoint(fallback_result["debug"])
        return fallback_result

    prompt = format_prompt(
        prompt_template,
        resume_text=resume_context,
        job_text=job_text,
        matching_skills=json.dumps(matching_skills, ensure_ascii=False),
        missing_skills=json.dumps(missing_skills, ensure_ascii=False),
    )
    data = safe_gemini_json(
        prompt,
        CANDIDATE_GRADING_SCHEMA,
        CANDIDATE_GRADING_FALLBACK,
        model_name=GEMINI_RESUME_SKILL_MODEL,
    )
    grading_error = RUNTIME_STATE.get("last_ai_error", "")
    result = normalize_candidate_grading(data)
    summarized_error = summarize_gemini_error(grading_error)
    debug["gemini_error"] = summarized_error
    debug["gemini_grade"] = result.get("grade", "")

    if grading_error or not candidate_grading_is_usable(result):
        if (
            "429" in grading_error
            or "RESOURCE_EXHAUSTED" in grading_error
            or "503" in grading_error
            or "UNAVAILABLE" in grading_error
        ):
            RUNTIME_STATE["skip_gemini_grading"] = True

        RUNTIME_STATE["last_ai_error"] = previous_ai_error
        fallback_result = {
            **fallback_result,
            "debug": {
                **debug,
                "source": "local_fallback",
                "final_grade": fallback_result.get("grade", ""),
            },
        }
        add_grading_checkpoint(fallback_result["debug"])
        return fallback_result

    result = {
        **result,
        "debug": {
            **debug,
            "source": "gemini",
            "final_grade": result.get("grade", ""),
        },
    }
    cache[cache_key] = result
    add_grading_checkpoint(result["debug"])
    return result


def analyze_candidate_detail(
    resume_text,
    job_text,
    score,
    model_name=None,
    resume_skill_profile=None,
    provider=None,
    prompt_template=None,
    job_skill_requirements=None,
    resume_name="",
):
    provider = provider or get_selected_provider()
    resume_context = build_resume_analysis_context(
        resume_text,
        resume_skill_profile,
    )
    indexed_detail = build_indexed_candidate_detail(
        resume_skill_profile,
        job_text,
        score,
        job_skill_requirements=job_skill_requirements,
    )
    cache_key = get_ai_cache_key(
        "candidate_detail_with_grading_v1",
        provider,
        model_name or get_selected_model(),
        score,
        resume_context,
        job_text,
        prompt_template or get_candidate_detail_prompt_template(),
    )
    cache = get_ai_cache()

    if cache_key in cache:
        cached_result = cache[cache_key]
        cached_result["missing_skills"] = merge_missing_skills(
            cached_result.get("missing_skills", []),
            indexed_detail["missing_skills"],
        )

        if not cached_result.get("matching_evidence"):
            cached_result["matching_evidence"] = build_matching_skill_evidence(
                resume_skill_profile,
                cached_result.get("matching_skills", []),
            )

        if not candidate_grading_is_usable(
            cached_result.get("candidate_grading")
        ):
            cached_result["candidate_grading"] = analyze_candidate_grading(
                resume_context,
                job_text,
                cached_result.get("matching_skills", []),
                cached_result.get("missing_skills", []),
                resume_name=resume_name,
            )

        return cached_result

    prompt = format_prompt(
        prompt_template or get_candidate_detail_prompt_template(),
        resume_text=resume_context,
        job_text=job_text,
        score=score,
    )

    data = safe_ai_json(
        prompt,
        CANDIDATE_DETAIL_SCHEMA,
        CANDIDATE_DETAIL_FALLBACK,
        model_name=model_name,
        provider=provider,
    )

    result = normalize_candidate_detail(data)
    justification_text = result["justification"].lower()
    unusable_resume_message = (
        "no resume" in justification_text
        or "resume was not provided" in justification_text
        or "resume is not provided" in justification_text
        or "without a resume" in justification_text
    )

    if not result["matching_skills"]:
        result["matching_skills"] = indexed_detail["matching_skills"]
    else:
        result["matching_skills"] = remove_placeholder_skills(
            result["matching_skills"]
        )

        if not result["matching_skills"]:
            result["matching_skills"] = indexed_detail["matching_skills"]

    result["missing_skills"] = merge_missing_skills(
        result["missing_skills"],
        indexed_detail["missing_skills"],
    )

    if (
        result["justification"]
        == CANDIDATE_DETAIL_FALLBACK["justification"]
        or unusable_resume_message
    ):
        result["justification"] = indexed_detail["justification"]

    result["matching_evidence"] = build_matching_skill_evidence(
        resume_skill_profile,
        result["matching_skills"],
    )
    result["candidate_grading"] = analyze_candidate_grading(
        resume_context,
        job_text,
        result["matching_skills"],
        result["missing_skills"],
        resume_name=resume_name,
    )
    if not RUNTIME_STATE.get("last_ai_error"):
        cache[cache_key] = result

    return result


# ==================================================
# PROCESS SINGLE RESUME
# ==================================================

def process_resume(resume_file, job_description):
    resume_id = get_resume_id(resume_file)
    resume_text = extract_text(resume_file)
    resume_embedding = get_or_create_resume_embedding(
        resume_id,
        resume_file.name,
        resume_text,
    )
    get_resume_skill_profile(
        resume_id,
        resume_file.name,
        resume_text,
    )
    score = calculate_match_score(
        resume_embedding,
        job_description,
    )

    return {
        "Resume Name": resume_file.name,
        "Resume ID": resume_id,
        "Match Score (%)": score,
    }

def persist_analysis_session(payload: dict, base_dir: str = "vector_store") -> str:
    """Append one analysis session to vector_store/analysis_sessions.json.
    Returns the session_id.
    """
    import os, json, uuid
    os.makedirs(base_dir, exist_ok=True)
    path = os.path.join(base_dir, "analysis_sessions.json")
    sessions = []
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                sessions = json.load(f) or []
        except Exception:
            sessions = []
    if "session_id" not in payload:
        payload["session_id"] = uuid.uuid4().hex
    sessions.append(payload)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sessions, f, ensure_ascii=False, indent=2)
    return payload["session_id"]


