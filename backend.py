import json
import hashlib
import os
import re
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
    import anthropic
except ImportError:
    anthropic = None

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
CANDIDATE_GRADING_CACHE_PATH = VECTOR_STORE_DIR / "candidate_grading_cache.json"

AI_PROVIDER_OPTIONS = [
    "Ollama",
    "Gemini",
    "Claude",
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

CLAUDE_MODEL_OPTIONS = [
    "claude-haiku-4-5",
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
    "claude-sonnet-4-5",
]

GEMINI_TRANSIENT_ERROR_CODES = [
    "503",
    "UNAVAILABLE",
]

CLAUDE_TRANSIENT_ERROR_CODES = [
    "429",
    "529",
    "overloaded_error",
    "rate_limit_error",
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
    "education": "",
    "additional_insights": {}
}

If the developer asks for extra fields, put them inside additional_insights
without changing the core JSON keys above.

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
    ],
    "additional_insights": {}
}

Rules:
- Maximum 10 matching skills.
- Maximum 10 missing skills.
- No explanations.
- No markdown.
- No code blocks.
- No text before or after JSON.
- If the developer asks for extra fields, put them inside additional_insights
  without changing the core JSON keys above.

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
    "justification": "",
    "additional_insights": {}
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
- If the developer asks for extra fields, put them inside additional_insights
  without changing the core JSON keys above.

MATCH SCORE:
{score}%

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_text}
"""

DEFAULT_CANDIDATE_GRADING_PROMPT_TEMPLATE = """You are a senior technical recruiter.

Grade the candidate's fit for the job using only these weighted criteria:

1. Skill gap: {skill_gap_weight}%
2. Years of experience: {years_experience_weight}%
3. Hands-on project experience: {project_experience_weight}%
4. Educational qualification: {education_weight}%
5. Seniority: {seniority_weight}%

Return ONLY valid JSON.

Format:

{
    "grade_percentage": 0,
    "criteria_scores": {
        "skill_gap": 0,
        "years_experience": 0,
        "project_experience": 0,
        "education": 0,
        "seniority": 0
    },
    "summary": "",
    "strengths": [
        "strength1",
        "strength2"
    ],
    "concerns": [
        "concern1",
        "concern2"
    ],
    "additional_insights": {}
}

Rules:
- Do not use or mention the existing match score.
- Score each item inside criteria_scores from 0 to 100.
- Calculate the final weighted grade_percentage yourself using
  criteria_scores and GRADING WEIGHTS.
- grade_percentage must change when GRADING WEIGHTS change, even if the same
  resume and job description are used.
- Skill gap means the balance of matching skills versus missing skills, with
  extra importance for mandatory or repeated job-description skills.
- Years of experience means whether the resume shows enough relevant total and
  role-specific experience for the job description.
- Hands-on project experience means whether the resume proves practical project
  usage of the important skills through implementations, products, client work,
  responsibilities, or measurable outcomes.
- Educational qualification means whether the resume's degrees,
  certifications, or formal education satisfy explicit or implied
  job-description education requirements.
- Seniority means whether role titles, responsibility level, leadership scope,
  and years of experience align with the job's expected seniority.
- Do not grade based on domain fit, location, education, company brand, role
  seniority, or general presentation unless that evidence directly supports one
  of the weighted criteria above.
- 90 to 100 means excellent fit with strong evidence across required skills,
  relevant experience, and hands-on project usage.
- 75 to 89 means strong fit with a few manageable gaps.
- 55 to 74 means partial fit with meaningful missing skills or unclear hands-on
  evidence.
- 35 to 54 means weak fit with major required-skill or experience gaps.
- 0 to 34 means very low fit with little relevant evidence for the job.
- Write the summary in 2 to 3 short lines.
- Use strengths for evidence-backed positives.
- Use concerns for missing skills, weak experience, or unclear project evidence.
- No explanations outside JSON.
- No markdown.
- No code blocks.
- If the developer asks for extra grading observations or custom rubric notes,
  put them inside additional_insights without changing the core JSON keys above.

RESUME CONTEXT:
{resume_text}

JOB DESCRIPTION:
{job_text}

MATCHING SKILLS:
{matching_skills}

MISSING SKILLS:
{missing_skills}

GRADING WEIGHTS:
{grading_weights}
"""

DEFAULT_CANDIDATE_GRADING_WEIGHTS = {
    "skill_gap": 50,
    "years_experience": 20,
    "project_experience": 15,
    "education": 5,
    "seniority": 10,
}

DEFAULT_EXPERIENCE_TIMELINE_PROMPT_TEMPLATE = """You are a senior ATS resume parser and technical recruiter.

Extract the candidate's professional experience timeline from the resume with
high accuracy. Focus only on work experience, internships, apprenticeships,
freelance/contract roles, and clearly dated project-based professional work.

Return ONLY valid JSON.

Format:

{
    "total_experience": "",
    "timeline": [
        {
            "role": "",
            "company": "",
            "start_date": "",
            "end_date": "",
            "duration": "",
            "location": "",
            "summary": "",
            "technologies": [
                "technology1",
                "technology2"
            ],
            "projects": [
                "project or product name"
            ],
            "relevance": ""
        }
    ],
    "additional_insights": {}
}

Rules:
- Read the full resume before deciding the timeline.
- Sort timeline entries from most recent to oldest.
- Extract a maximum of 8 timeline entries.
- Use the role/title exactly as written when possible.
- Use the company/client/organization exactly as written when possible.
- start_date and end_date must preserve the resume wording, such as
  "Jan 2022", "2021", "Present", or "Not Found".
- duration should be calculated only when dates are clear. Otherwise return
  "Not Found".
- summary must be 1 concise sentence describing the candidate's work in that
  role using evidence from the resume.
- technologies must include only tools, programming languages, platforms,
  frameworks, methods, or domain systems explicitly connected to that role.
- projects must include only project/product names explicitly connected to
  that role. Return an empty list if none are clear.
- relevance must explain in 1 short sentence how this role supports or does
  not support the job description.
- Do not invent dates, companies, roles, skills, projects, or responsibilities.
- If the resume has no clear dated experience, return total_experience as
  "Not Found" and timeline as an empty list.
- No markdown.
- No code blocks.
- No text before or after JSON.
- If the developer asks for extra timeline fields, put them inside
  additional_insights without changing the core JSON keys above.

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_text}
"""

DEFAULT_CANDIDATE_SNAPSHOT_PROMPT_TEMPLATE = """You are a senior ATS resume parser and recruiter.

Extract a concise candidate snapshot from the resume. The snapshot will appear
at the top of a recruiter-facing detailed analysis page, so prefer short,
high-confidence values that help identify the candidate quickly.

Return ONLY valid JSON.

Format:

{
    "candidate_name": "",
    "likely_role": "",
    "current_title": "",
    "current_company": "",
    "location": "",
    "total_experience": "",
    "additional_insights": {}
}

Rules:
- Use only information explicitly present in the resume.
- candidate_name should be the person's name if it is clearly visible near the
  top/header of the resume. If unclear, return "Not Found".
- likely_role should summarize the candidate's professional identity using
  the strongest repeated role signals, such as "Senior Business Consultant",
  "Frontend Developer", or "Data Analyst".
- current_title and current_company should come from the most recent role or
  current employment entry. If dates are unclear, use the first clearly listed
  professional role/company.
- location should be the candidate's city/state/country if clearly present.
- total_experience should preserve explicit wording such as "8+ years" or
  "14 years". If not explicit, infer only when the resume dates are clear;
  otherwise return "Not Found".
- Keep every field concise. Do not write paragraphs.
- Do not invent names, companies, locations, dates, or experience.
- No markdown.
- No code blocks.
- No text before or after JSON.
- If the developer asks for extra snapshot fields, put them inside
  additional_insights without changing the core JSON keys above.

RESUME:
{resume_text}
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
    ],
    "additional_insights": {}
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
- If the developer asks for extra extracted fields, put them inside
  additional_insights without changing the core JSON keys above.

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
        "additional_insights": {
            "type": "object",
        },
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
        "additional_insights": {
            "type": "object",
        },
    },
}

SKILL_GAP_SCHEMA = {
    "type": "object",
    "properties": {
        "matching_skills": {},
        "missing_skills": {},
        "additional_insights": {
            "type": "object",
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
        "additional_insights": {
            "type": "object",
        },
    },
}

CANDIDATE_GRADING_SCHEMA = {
    "type": "object",
    "required": [
        "grade_percentage",
        "criteria_scores",
        "summary",
        "strengths",
        "concerns",
    ],
    "properties": {
        "grade_percentage": {
            "type": "integer",
        },
        "criteria_scores": {
            "type": "object",
            "properties": {
                "skill_gap": {
                    "type": "integer",
                },
                "years_experience": {
                    "type": "integer",
                },
                "project_experience": {
                    "type": "integer",
                },
                "education": {
                    "type": "integer",
                },
                "seniority": {
                    "type": "integer",
                },
            },
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
        "additional_insights": {
            "type": "object",
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

EXPERIENCE_TIMELINE_SCHEMA = {
    "type": "object",
    "required": [
        "total_experience",
        "timeline",
    ],
    "properties": {
        "total_experience": {
            "type": "string",
        },
        "timeline": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "role": {
                        "type": "string",
                    },
                    "company": {
                        "type": "string",
                    },
                    "start_date": {
                        "type": "string",
                    },
                    "end_date": {
                        "type": "string",
                    },
                    "duration": {
                        "type": "string",
                    },
                    "location": {
                        "type": "string",
                    },
                    "summary": {
                        "type": "string",
                    },
                    "technologies": {
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                    },
                    "projects": {
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                    },
                    "relevance": {
                        "type": "string",
                    },
                },
            },
        },
        "additional_insights": {
            "type": "object",
        },
    },
}

CANDIDATE_SNAPSHOT_SCHEMA = {
    "type": "object",
    "required": [
        "candidate_name",
        "likely_role",
        "current_title",
        "current_company",
        "location",
        "total_experience",
    ],
    "properties": {
        "candidate_name": {
            "type": "string",
        },
        "likely_role": {
            "type": "string",
        },
        "current_title": {
            "type": "string",
        },
        "current_company": {
            "type": "string",
        },
        "location": {
            "type": "string",
        },
        "total_experience": {
            "type": "string",
        },
        "additional_insights": {
            "type": "object",
        },
    },
}

JD_FALLBACK = {
    "experience": "Not Found",
    "primary_skills": "Not Found",
    "secondary_skills": "Not Found",
    "education": "Not Found",
    "additional_insights": {},
}

SKILL_GAP_FALLBACK = {
    "matching_skills": [],
    "missing_skills": [],
    "additional_insights": {},
}

CANDIDATE_DETAIL_FALLBACK = {
    "matching_skills": [],
    "missing_skills": [],
    "justification": "Justification could not be generated.",
    "additional_insights": {},
}

CANDIDATE_GRADING_FALLBACK = {
    "grade": "C",
    "grade_percentage": 55,
    "criteria_scores": {
        "skill_gap": 55,
        "years_experience": 55,
        "project_experience": 55,
        "education": 55,
        "seniority": 55,
    },
    "summary": "Candidate grading could not be generated.",
    "strengths": [],
    "concerns": [],
    "additional_insights": {},
}

RESUME_SKILL_FALLBACK = {
    "technical_skills": [],
    "soft_skills": [],
    "tools": [],
    "domains": [],
    "experience_summary": "Not Found",
    "skill_evidence": [],
    "additional_insights": {},
    "experience_timeline": {
        "total_experience": "Not Found",
        "timeline": [],
        "additional_insights": {},
    },
    "candidate_snapshot": {
        "candidate_name": "Not Found",
        "likely_role": "Not Found",
        "current_title": "Not Found",
        "current_company": "Not Found",
        "location": "Not Found",
        "total_experience": "Not Found",
        "source": "not_found",
        "additional_insights": {},
    },
}

EXPERIENCE_TIMELINE_FALLBACK = {
    "total_experience": "Not Found",
    "timeline": [],
    "additional_insights": {},
}

CANDIDATE_SNAPSHOT_FALLBACK = {
    "candidate_name": "Not Found",
    "likely_role": "Not Found",
    "current_title": "Not Found",
    "current_company": "Not Found",
    "location": "Not Found",
    "total_experience": "Not Found",
    "source": "not_found",
    "additional_insights": {},
}

RUNTIME_STATE = {
    "ai_provider": DEFAULT_AI_PROVIDER,
    "ollama_model": DEFAULT_OLLAMA_MODEL,
    "gemini_model": GEMINI_MODEL_OPTIONS[0],
    "claude_model": CLAUDE_MODEL_OPTIONS[0],
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
    "candidate_grading_weights": DEFAULT_CANDIDATE_GRADING_WEIGHTS.copy(),
    "active_experience_timeline_prompt_template": (
        DEFAULT_EXPERIENCE_TIMELINE_PROMPT_TEMPLATE
    ),
    "active_candidate_snapshot_prompt_template": (
        DEFAULT_CANDIDATE_SNAPSHOT_PROMPT_TEMPLATE
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
    "timeline_diagnostics": [],
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
        return None, []
    if FAISS_INDEX_PATH.exists():
        try:
            index = faiss.read_index(str(FAISS_INDEX_PATH))
        except Exception:
            index = faiss.IndexFlatIP(dimension)
    else:
        index = faiss.IndexFlatIP(dimension)
    metadata = []
    if FAISS_METADATA_PATH.exists():
        try:
            metadata = json.loads(FAISS_METADATA_PATH.read_text(encoding="utf-8"))
        except Exception:
            metadata = []
    return index, metadata

def faiss_index_lookup(resume_id):
    """Return the cached embedding for 
esume_id from the FAISS index,
    or None if it isn't indexed yet.

    This is a fast path used by get_or_create_resume_embedding so repeat
    uploads of the same resume skip the embedding model entirely.
    """
    if faiss is None or not FAISS_INDEX_PATH.exists():
        return None

    try:
        index, metadata = load_resume_vector_store()
    except Exception:
        return None

    for rec in metadata:
        if rec.get("id") == resume_id or rec.get("resume_id") == resume_id:
            try:
                row = int(rec.get("faiss_row", metadata.index(rec)))
                return np.asarray(
                    [
                        index.reconstruct(row),
                    ],
                    dtype="float32",
                )
            except (TypeError, ValueError, RuntimeError):
                return None
    return None

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

    # Fast path: if the embedding is already in FAISS, skip the model
    # call entirely. This makes repeat uploads of the same resume free.
    cached_embedding = faiss_index_lookup(resume_id)
    if cached_embedding is not None:
        return cached_embedding
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

    if RUNTIME_STATE.get("claude_model") not in CLAUDE_MODEL_OPTIONS:
        RUNTIME_STATE["claude_model"] = CLAUDE_MODEL_OPTIONS[0]

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
    RUNTIME_STATE.setdefault(
        "active_experience_timeline_prompt_template",
        DEFAULT_EXPERIENCE_TIMELINE_PROMPT_TEMPLATE,
    )
    RUNTIME_STATE.setdefault(
        "active_candidate_snapshot_prompt_template",
        DEFAULT_CANDIDATE_SNAPSHOT_PROMPT_TEMPLATE,
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

    if get_selected_provider() == "Claude":
        return RUNTIME_STATE.get("claude_model", CLAUDE_MODEL_OPTIONS[0])

    return RUNTIME_STATE.get("ollama_model", DEFAULT_OLLAMA_MODEL)


def get_selected_provider():
    return RUNTIME_STATE.get("ai_provider", DEFAULT_AI_PROVIDER)


def get_model_options(provider=None):
    provider = provider or get_selected_provider()

    if provider == "Gemini":
        return GEMINI_MODEL_OPTIONS

    if provider == "Claude":
        return CLAUDE_MODEL_OPTIONS

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


def normalize_candidate_grading_weights(weights):
    default_weights = DEFAULT_CANDIDATE_GRADING_WEIGHTS.copy()

    if not isinstance(weights, dict):
        return default_weights

    expected_keys = set(default_weights)
    provided_keys = set(weights)
    if not expected_keys.issubset(provided_keys):
        return default_weights

    normalized = {}
    for key, default_value in default_weights.items():
        try:
            value = int(round(float(weights.get(key, default_value))))
        except (TypeError, ValueError):
            value = default_value

        normalized[key] = max(0, min(100, value))

    total = sum(normalized.values())
    if total <= 0:
        return default_weights

    legacy_expanded_weights = {
        "skill_gap": 50,
        "years_experience": 25,
        "project_experience": 25,
        "education": 5,
        "seniority": 10,
    }
    if normalized == legacy_expanded_weights:
        return default_weights

    return normalized


def normalize_grading_criteria_scores(scores):
    default_scores = CANDIDATE_GRADING_FALLBACK["criteria_scores"].copy()

    if not isinstance(scores, dict):
        return default_scores

    normalized = {}
    for key, default_value in default_scores.items():
        try:
            value = int(round(float(scores.get(key, default_value))))
        except (TypeError, ValueError):
            value = default_value

        normalized[key] = max(0, min(100, value))

    return normalized


def data_has_grading_criteria_scores(data):
    if not isinstance(data, dict):
        return False

    if isinstance(
        get_first_present(
            data,
            ["criteria_scores", "criterion_scores", "rubric_scores"],
            None,
        ),
        dict,
    ):
        return True

    return any(
        key in data
        for key in [
            "skill_gap_score",
            "skills_score",
            "years_experience_score",
            "experience_score",
            "project_experience_score",
            "hands_on_project_score",
            "education_score",
            "educational_qualification_score",
            "seniority_score",
        ]
    )


def calculate_weighted_grade_percentage(criteria_scores, grading_weights):
    criteria_scores = normalize_grading_criteria_scores(criteria_scores)
    grading_weights = normalize_candidate_grading_weights(grading_weights)
    total_weight = sum(grading_weights.values()) or 100
    return round(
        (
            criteria_scores["skill_gap"] * grading_weights["skill_gap"]
            + criteria_scores["years_experience"]
            * grading_weights["years_experience"]
            + criteria_scores["project_experience"]
            * grading_weights["project_experience"]
            + criteria_scores["education"] * grading_weights["education"]
            + criteria_scores["seniority"] * grading_weights["seniority"]
        )
        / total_weight
    )


def grade_letter_from_percentage(grade_percentage):
    if grade_percentage >= 90:
        return "A"

    if grade_percentage >= 75:
        return "B"

    if grade_percentage >= 55:
        return "C"

    if grade_percentage >= 35:
        return "D"

    return "F"


def attach_candidate_grading_weights(candidate_grading, grading_weights):
    if not isinstance(candidate_grading, dict):
        return candidate_grading

    criteria_scores = candidate_grading.get("criteria_scores")
    if not isinstance(criteria_scores, dict):
        criteria_scores = CANDIDATE_GRADING_FALLBACK["criteria_scores"]

    grading_weights = normalize_candidate_grading_weights(grading_weights)
    grade_percentage = int(
        max(
            0,
            min(
                100,
                round(float(candidate_grading.get("grade_percentage", 0))),
            ),
        )
    )
    return {
        **candidate_grading,
        "grade": grade_letter_from_percentage(grade_percentage),
        "grade_percentage": grade_percentage,
        "criteria_scores": normalize_grading_criteria_scores(criteria_scores),
        "weights": grading_weights,
    }


def criteria_scores_have_signal(criteria_scores):
    if not isinstance(criteria_scores, dict):
        return False

    normalized = normalize_grading_criteria_scores(criteria_scores)
    return any(value > 0 for value in normalized.values())


def ensure_grading_breakdown(
    candidate_grading,
    resume_context,
    matching_skills,
    missing_skills,
    grading_weights,
):
    if not isinstance(candidate_grading, dict):
        return candidate_grading

    criteria_scores = candidate_grading.get("criteria_scores")
    if not criteria_scores_have_signal(criteria_scores):
        criteria_scores = calculate_local_grading_criteria_scores(
            resume_context,
            matching_skills,
            missing_skills,
        )

    return attach_candidate_grading_weights(
        {
            **candidate_grading,
            "criteria_scores": criteria_scores,
        },
        grading_weights,
    )


def get_candidate_grading_weights():
    return normalize_candidate_grading_weights(
        RUNTIME_STATE.get("candidate_grading_weights")
    )


def get_experience_timeline_prompt_template():
    prompt = RUNTIME_STATE.get(
        "active_experience_timeline_prompt_template",
        "",
    )
    return (
        prompt
        if prompt.strip()
        else DEFAULT_EXPERIENCE_TIMELINE_PROMPT_TEMPLATE
    )


def get_candidate_snapshot_prompt_template():
    prompt = RUNTIME_STATE.get(
        "active_candidate_snapshot_prompt_template",
        "",
    )
    return (
        prompt
        if prompt.strip()
        else DEFAULT_CANDIDATE_SNAPSHOT_PROMPT_TEMPLATE
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


def get_candidate_grading_cache_key(
    resume_context,
    job_text,
    matching_skills,
    missing_skills,
    prompt_template,
    provider,
    model_name,
):
    payload = {
        "provider": provider,
        "model": model_name,
        "resume_context": resume_context,
        "job_text": job_text,
        "matching_skills": matching_skills,
        "missing_skills": missing_skills,
        "prompt_template": prompt_template,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_persistent_candidate_grading(cache_key, provider=None):
    store = read_json_file(CANDIDATE_GRADING_CACHE_PATH, {})
    item = store.get(cache_key)

    if isinstance(item, dict) and candidate_grading_is_model(
        item.get("grading")
    ):
        if provider and item["grading"].get("source") != provider:
            return None

        return item["grading"]

    return None


def save_persistent_candidate_grading(cache_key, grading, provider, model_name):
    if not candidate_grading_is_model(grading):
        return

    store = read_json_file(CANDIDATE_GRADING_CACHE_PATH, {})
    store[cache_key] = {
        "provider": provider,
        "model": model_name,
        "created_at": get_current_timestamp(),
        "grading": grading,
    }
    write_json_file(CANDIDATE_GRADING_CACHE_PATH, store)


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

    if not CANDIDATE_GRADING_CACHE_PATH.exists():
        write_json_file(CANDIDATE_GRADING_CACHE_PATH, {})

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
        stored_resume_text = ""

        if isinstance(skills_item, dict):
            resume_skill_profile = normalize_resume_skill_profile(
                skills_item.get("skills", {}) or {}
            )
            stored_resume_text = display_value(
                skills_item.get("resume_text"),
                "",
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
                "resume_text": (
                    stored_resume_text
                    if stored_resume_text and stored_resume_text != "Not Found"
                    else (
                        format_resume_skill_profile(resume_skill_profile)
                        if resume_skill_profile_has_signal(resume_skill_profile)
                        else ""
                    )
                ),
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
        "claude_model": CLAUDE_MODEL_OPTIONS[0],
        "jd_prompt_template": DEFAULT_JD_PROMPT_TEMPLATE,
        "skill_gap_prompt_template": DEFAULT_SKILL_GAP_PROMPT_TEMPLATE,
        "candidate_detail_prompt_template": (
            DEFAULT_CANDIDATE_DETAIL_PROMPT_TEMPLATE
        ),
        "candidate_grading_prompt_template": (
            DEFAULT_CANDIDATE_GRADING_PROMPT_TEMPLATE
        ),
        "candidate_grading_weights": (
            DEFAULT_CANDIDATE_GRADING_WEIGHTS.copy()
        ),
        "experience_timeline_prompt_template": (
            DEFAULT_EXPERIENCE_TIMELINE_PROMPT_TEMPLATE
        ),
        "candidate_snapshot_prompt_template": (
            DEFAULT_CANDIDATE_SNAPSHOT_PROMPT_TEMPLATE
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
    jd_prompt = str(normalized_config.get("jd_prompt_template", ""))
    skill_gap_prompt = str(
        normalized_config.get("skill_gap_prompt_template", "")
    )
    candidate_detail_prompt = str(
        normalized_config.get("candidate_detail_prompt_template", "")
    )
    candidate_grading_prompt = str(
        normalized_config.get("candidate_grading_prompt_template", "")
    )
    normalized_config["candidate_grading_weights"] = (
        normalize_candidate_grading_weights(
            normalized_config.get("candidate_grading_weights")
        )
    )
    experience_timeline_prompt = str(
        normalized_config.get("experience_timeline_prompt_template", "")
    )
    candidate_snapshot_prompt = str(
        normalized_config.get("candidate_snapshot_prompt_template", "")
    )
    if "additional_insights" not in jd_prompt:
        normalized_config["jd_prompt_template"] = DEFAULT_JD_PROMPT_TEMPLATE

    if "additional_insights" not in skill_gap_prompt:
        normalized_config["skill_gap_prompt_template"] = (
            DEFAULT_SKILL_GAP_PROMPT_TEMPLATE
        )

    if (
        "candidate resume context" not in candidate_detail_prompt
        or "additional_insights" not in candidate_detail_prompt
    ):
        normalized_config["candidate_detail_prompt_template"] = (
            DEFAULT_CANDIDATE_DETAIL_PROMPT_TEMPLATE
        )

    if (
        "Do not use or mention the existing match score"
        not in candidate_grading_prompt
        or "grade_percentage" not in candidate_grading_prompt
        or "{skill_gap_weight}" not in candidate_grading_prompt
        or "{education_weight}" not in candidate_grading_prompt
        or "{seniority_weight}" not in candidate_grading_prompt
        or "criteria_scores" not in candidate_grading_prompt
        or "Calculate the final weighted grade_percentage yourself"
        not in candidate_grading_prompt
        or "additional_insights" not in candidate_grading_prompt
    ):
        normalized_config["candidate_grading_prompt_template"] = (
            DEFAULT_CANDIDATE_GRADING_PROMPT_TEMPLATE
        )

    if (
        "professional experience timeline" not in experience_timeline_prompt
        or "{resume_text}" not in experience_timeline_prompt
        or "{job_text}" not in experience_timeline_prompt
        or "additional_insights" not in experience_timeline_prompt
    ):
        normalized_config["experience_timeline_prompt_template"] = (
            DEFAULT_EXPERIENCE_TIMELINE_PROMPT_TEMPLATE
        )

    if (
        "candidate snapshot" not in candidate_snapshot_prompt.lower()
        or "{resume_text}" not in candidate_snapshot_prompt
        or "additional_insights" not in candidate_snapshot_prompt
    ):
        normalized_config["candidate_snapshot_prompt_template"] = (
            DEFAULT_CANDIDATE_SNAPSHOT_PROMPT_TEMPLATE
        )

    if (
        "skill_evidence" not in resume_skill_prompt
        or "experience_timeline" in resume_skill_prompt
        or "resume_last_updated" in resume_skill_prompt
        or "additional_insights" not in resume_skill_prompt
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
    RUNTIME_STATE["claude_model"] = config["claude_model"]
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
    RUNTIME_STATE["candidate_grading_weights"] = config[
        "candidate_grading_weights"
    ]
    RUNTIME_STATE["active_experience_timeline_prompt_template"] = config[
        "experience_timeline_prompt_template"
    ]
    RUNTIME_STATE["active_candidate_snapshot_prompt_template"] = config[
        "candidate_snapshot_prompt_template"
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


def safe_claude_json(prompt, schema, fallback, model_name=None):
    try:
        if anthropic is None:
            raise RuntimeError(
                "Install anthropic to use Claude models."
            )

        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "Set ANTHROPIC_API_KEY to use Claude models."
            )

        client = anthropic.Anthropic()
        selected_model = model_name or get_selected_model()

        for attempt in range(3):
            try:
                response = client.messages.create(
                    model=selected_model,
                    max_tokens=2048,
                    temperature=0,
                    system=(
                        "You are a JSON API. Return exactly one valid JSON "
                        "object only. Do not include markdown or explanations."
                    ),
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                )
                break
            except Exception as error:
                message = str(error)
                is_transient = any(
                    code in message
                    for code in CLAUDE_TRANSIENT_ERROR_CODES
                )

                if not is_transient or attempt == 2:
                    raise

                time.sleep(2)

        text_parts = []
        for block in getattr(response, "content", []) or []:
            text = getattr(block, "text", None)
            if text:
                text_parts.append(text)

        data = safe_json_extract("\n".join(text_parts))

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

    if provider == "Claude":
        return safe_claude_json(
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
            item.strip(" -ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢\t")
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


def normalize_additional_insights(value):
    if not isinstance(value, dict):
        return {}

    normalized = {}

    for key, item in value.items():
        clean_key = str(key).strip()

        if not clean_key:
            continue

        if isinstance(item, dict):
            nested = normalize_additional_insights(item)

            if nested:
                normalized[clean_key] = nested

            continue

        if isinstance(item, list):
            clean_items = []

            for list_item in item:
                if isinstance(list_item, dict):
                    nested = normalize_additional_insights(list_item)

                    if nested:
                        clean_items.append(nested)

                    continue

                text = str(list_item).strip()

                if text and text != "Not Found":
                    clean_items.append(text)

            if clean_items:
                normalized[clean_key] = clean_items[:20]

            continue

        text = str(item).strip()

        if text and text != "Not Found":
            normalized[clean_key] = text

    return normalized


def normalize_experience_timeline(data):
    if not isinstance(data, dict):
        return EXPERIENCE_TIMELINE_FALLBACK.copy()

    timeline_rows = []
    timeline = get_first_present(
        data,
        [
            "timeline",
            "experience_timeline",
            "experience",
            "work_experience",
            "roles",
        ],
        [],
    )

    if not isinstance(timeline, list):
        timeline = []

    for item in timeline:
        if not isinstance(item, dict):
            continue

        role = display_value(
            get_first_present(item, ["role", "title", "position"], ""),
            "",
        )
        company = display_value(
            get_first_present(
                item,
                ["company", "organization", "employer", "client"],
                "",
            ),
            "",
        )
        summary = display_value(
            get_first_present(
                item,
                ["summary", "responsibilities", "description"],
                "",
            ),
            "",
        )

        if not any([role, company, summary]):
            continue

        timeline_rows.append(
            {
                "role": role or "Not Found",
                "company": company or "Not Found",
                "start_date": display_value(
                    get_first_present(
                        item,
                        ["start_date", "start", "from"],
                        "",
                    ),
                    "Not Found",
                ),
                "end_date": display_value(
                    get_first_present(
                        item,
                        ["end_date", "end", "to"],
                        "",
                    ),
                    "Not Found",
                ),
                "duration": display_value(
                    get_first_present(item, ["duration", "tenure"], ""),
                    "Not Found",
                ),
                "location": display_value(item.get("location"), "Not Found"),
                "summary": summary or "Not Found",
                "technologies": normalize_skill_list(
                    get_first_present(
                        item,
                        ["technologies", "skills", "tools", "tech_stack"],
                        [],
                    )
                )[:12],
                "projects": normalize_skill_list(
                    get_first_present(
                        item,
                        ["projects", "project_names", "products"],
                        [],
                    )
                )[:8],
                "relevance": display_value(
                    get_first_present(
                        item,
                        ["relevance", "job_relevance", "fit"],
                        "",
                    ),
                    "Not Found",
                ),
            }
        )

        if len(timeline_rows) >= 8:
            break

    return {
        "total_experience": display_value(
            get_first_present(
                data,
                [
                    "total_experience",
                    "total_years",
                    "years_of_experience",
                    "experience_summary",
                ],
                "Not Found",
            ),
            "Not Found",
        ),
        "timeline": timeline_rows,
        "additional_insights": normalize_additional_insights(
            data.get("additional_insights", {})
        ),
    }


def normalize_candidate_snapshot(data):
    if not isinstance(data, dict):
        data = {}

    return {
        "candidate_name": display_value(
            get_first_present(
                data,
                ["candidate_name", "name", "full_name"],
                "Not Found",
            ),
            "Not Found",
        ),
        "likely_role": display_value(
            get_first_present(
                data,
                ["likely_role", "role", "profile_title", "headline"],
                "Not Found",
            ),
            "Not Found",
        ),
        "current_title": display_value(
            get_first_present(
                data,
                ["current_title", "title", "current_role"],
                "Not Found",
            ),
            "Not Found",
        ),
        "current_company": display_value(
            get_first_present(
                data,
                ["current_company", "company", "current_employer"],
                "Not Found",
            ),
            "Not Found",
        ),
        "location": display_value(
            get_first_present(
                data,
                ["location", "city", "address"],
                "Not Found",
            ),
            "Not Found",
        ),
        "total_experience": display_value(
            get_first_present(
                data,
                [
                    "total_experience",
                    "experience",
                    "years_of_experience",
                    "years_experience",
                ],
                "Not Found",
            ),
            "Not Found",
        ),
        "source": display_value(data.get("source"), "model"),
        "additional_insights": normalize_additional_insights(
            data.get("additional_insights", {})
        ),
    }


def candidate_snapshot_has_signal(snapshot):
    if not isinstance(snapshot, dict):
        return False

    for key in [
        "candidate_name",
        "likely_role",
        "current_title",
        "current_company",
        "location",
        "total_experience",
    ]:
        if display_value(snapshot.get(key), "") not in ["", "Not Found"]:
            return True

    return False


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


EXPERIENCE_DATE_PATTERN = re.compile(
    r"(?P<start>(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)"
    r"[a-z]*\.?\s+\d{4}|\d{4})\s*(?:-|–|—|to)\s*"
    r"(?P<end>(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)"
    r"[a-z]*\.?\s+\d{4}|\d{4}|present|current|till date)",
    re.IGNORECASE,
)


def parse_local_timeline_heading(line):
    match = EXPERIENCE_DATE_PATTERN.search(line)

    if not match:
        return None

    heading = EXPERIENCE_DATE_PATTERN.sub("", line).strip(" -|,;")
    role = "Not Found"
    company = "Not Found"

    for separator in [" at ", " @ ", " | ", " - ", " – ", " — ", ","]:
        if separator in heading:
            parts = [
                part.strip(" -|,;")
                for part in heading.split(separator, 1)
            ]
            if len(parts) == 2:
                role = parts[0] or role
                company = parts[1] or company
            break

    if role == "Not Found" and heading:
        role = heading[:120]

    return {
        "role": role,
        "company": company,
        "start_date": match.group("start"),
        "end_date": match.group("end"),
    }


def build_local_experience_timeline(resume_text, job_text=""):
    text = display_value(resume_text, "")

    if not text or text == "Not Found":
        return EXPERIENCE_TIMELINE_FALLBACK.copy()

    lines = [
        line.strip(" \t-*")
        for line in text.splitlines()
        if line.strip(" \t-*")
    ]
    timeline = []

    for index, line in enumerate(lines):
        heading = parse_local_timeline_heading(line)

        if not heading:
            continue

        nearby_lines = []

        for nearby in lines[index + 1:index + 5]:
            if EXPERIENCE_DATE_PATTERN.search(nearby):
                break

            if len(nearby) >= 25:
                nearby_lines.append(nearby)

        summary = " ".join(nearby_lines)[:360] or line[:240]
        technologies = find_keywords_in_text(
            " ".join([line] + nearby_lines),
            TECHNICAL_SKILL_KEYWORDS,
            limit=10,
        )

        timeline.append(
            {
                **heading,
                "duration": "Not Found",
                "location": "Not Found",
                "summary": summary,
                "technologies": technologies,
                "projects": [],
                "relevance": (
                    "This role was identified from dated resume experience; "
                    "review the listed technologies and summary against the JD."
                ),
            }
        )

        if len(timeline) >= 8:
            break

    if not timeline:
        return EXPERIENCE_TIMELINE_FALLBACK.copy()

    return {
        "total_experience": "Derived from dated resume entries",
        "timeline": timeline,
    }


def build_local_candidate_snapshot(resume_text, resume_name="", timeline=None):
    text = display_value(resume_text, "")
    lines = [
        line.strip(" \t-*")
        for line in text.splitlines()
        if line.strip(" \t-*")
    ] if text and text != "Not Found" else []
    safe_timeline = normalize_experience_timeline(
        timeline or EXPERIENCE_TIMELINE_FALLBACK
    )
    latest_role = (
        safe_timeline["timeline"][0]
        if safe_timeline.get("timeline")
        else {}
    )
    candidate_name = "Not Found"

    for line in lines[:8]:
        if (
            2 <= len(line.split()) <= 5
            and not any(char.isdigit() for char in line)
            and "@" not in line
            and not line.lower().startswith(("resume", "curriculum", "cv"))
        ):
            candidate_name = line[:80]
            break

    if candidate_name == "Not Found" and resume_name:
        candidate_name = Path(resume_name).stem[:80]

    experience_match = re.search(
        r"(\d{1,2}\+?\s*(?:years|yrs)\b)",
        text,
        re.IGNORECASE,
    )

    return normalize_candidate_snapshot(
        {
            "candidate_name": candidate_name,
            "likely_role": get_first_present(
                latest_role,
                ["role"],
                "Not Found",
            ),
            "current_title": get_first_present(
                latest_role,
                ["role"],
                "Not Found",
            ),
            "current_company": get_first_present(
                latest_role,
                ["company"],
                "Not Found",
            ),
            "location": "Not Found",
            "total_experience": (
                experience_match.group(1)
                if experience_match
                else safe_timeline.get("total_experience", "Not Found")
            ),
            "source": "local_fallback",
        }
    )


def add_timeline_diagnostic(resume_name, diagnostic):
    diagnostics = RUNTIME_STATE.setdefault("timeline_diagnostics", [])
    safe_diagnostic = {
        "resume_name": display_value(resume_name, "Unknown Resume"),
        **diagnostic,
    }
    diagnostics.append(safe_diagnostic)
    RUNTIME_STATE["timeline_diagnostics"] = diagnostics[-20:]
    return safe_diagnostic


def persist_resume_experience_timeline(
    resume_id,
    resume_name,
    timeline,
    provider=None,
    model_name=None,
):
    normalized_timeline = normalize_experience_timeline(timeline)

    if not resume_id or not normalized_timeline.get("timeline"):
        return

    skills_store = read_json_file(RESUME_SKILLS_PATH, {})
    item = skills_store.get(resume_id, {})

    if not isinstance(item, dict):
        item = {}

    profile = normalize_resume_skill_profile(item.get("skills", {}) or {})
    profile["experience_timeline"] = normalized_timeline
    skills_store[resume_id] = {
        **item,
        "resume_id": resume_id,
        "resume_name": resume_name or item.get("resume_name", "Unknown Resume"),
        "skills": profile,
        "model": item.get("model", GEMINI_RESUME_SKILL_MODEL),
        "timeline_model": model_name or get_selected_model(),
        "timeline_provider": provider or get_selected_provider(),
        "timeline_last_updated_at": get_current_timestamp(),
        "last_updated_at": get_current_timestamp(),
    }
    write_json_file(RESUME_SKILLS_PATH, skills_store)


def persist_resume_text(resume_id, resume_name, resume_text):
    text = display_value(resume_text, "")

    if not resume_id or not text or text == "Not Found":
        return

    skills_store = read_json_file(RESUME_SKILLS_PATH, {})
    item = skills_store.get(resume_id, {})

    if not isinstance(item, dict):
        item = {}

    skills_store[resume_id] = {
        **item,
        "resume_id": resume_id,
        "resume_name": resume_name or item.get("resume_name", "Unknown Resume"),
        "resume_text": text,
        "resume_text_last_updated_at": get_current_timestamp(),
        "last_updated_at": get_current_timestamp(),
    }
    write_json_file(RESUME_SKILLS_PATH, skills_store)


def persist_candidate_snapshot(
    resume_id,
    resume_name,
    snapshot,
    provider=None,
    model_name=None,
):
    normalized_snapshot = normalize_candidate_snapshot(snapshot)

    if not resume_id or not candidate_snapshot_has_signal(normalized_snapshot):
        return

    skills_store = read_json_file(RESUME_SKILLS_PATH, {})
    item = skills_store.get(resume_id, {})

    if not isinstance(item, dict):
        item = {}

    profile = normalize_resume_skill_profile(item.get("skills", {}) or {})
    profile["candidate_snapshot"] = normalized_snapshot
    skills_store[resume_id] = {
        **item,
        "resume_id": resume_id,
        "resume_name": resume_name or item.get("resume_name", "Unknown Resume"),
        "skills": profile,
        "model": item.get("model", GEMINI_RESUME_SKILL_MODEL),
        "snapshot_model": model_name or get_selected_model(),
        "snapshot_provider": provider or get_selected_provider(),
        "snapshot_last_updated_at": get_current_timestamp(),
        "last_updated_at": get_current_timestamp(),
    }
    write_json_file(RESUME_SKILLS_PATH, skills_store)


def ensure_candidate_snapshot(
    profile,
    resume_text,
    provider=None,
    model_name=None,
    resume_name="",
    resume_id="",
):
    if not isinstance(profile, dict):
        profile = normalize_resume_skill_profile(RESUME_SKILL_FALLBACK)

    existing_snapshot = normalize_candidate_snapshot(
        profile.get("candidate_snapshot", CANDIDATE_SNAPSHOT_FALLBACK)
    )

    if candidate_snapshot_has_signal(existing_snapshot):
        profile["candidate_snapshot"] = existing_snapshot
        persist_candidate_snapshot(
            resume_id,
            resume_name,
            existing_snapshot,
            provider=provider,
            model_name=model_name,
        )
        return profile

    resume_context = display_value(resume_text, "")
    selected_provider = provider or get_selected_provider()
    selected_model = model_name or get_selected_model()
    previous_ai_error = RUNTIME_STATE.get("last_ai_error", "")

    if not resume_context or resume_context == "Not Found":
        local_snapshot = build_local_candidate_snapshot(
            "",
            resume_name=resume_name,
            timeline=profile.get("experience_timeline"),
        )
        profile["candidate_snapshot"] = local_snapshot
        persist_candidate_snapshot(
            resume_id,
            resume_name,
            local_snapshot,
            provider=selected_provider,
            model_name=selected_model,
        )
        return profile

    prompt = format_prompt(
        get_candidate_snapshot_prompt_template(),
        resume_text=resume_context,
    )
    RUNTIME_STATE["last_ai_error"] = ""
    data = safe_ai_json(
        prompt,
        CANDIDATE_SNAPSHOT_SCHEMA,
        CANDIDATE_SNAPSHOT_FALLBACK,
        model_name=selected_model,
        provider=selected_provider,
    )
    snapshot_error = RUNTIME_STATE.get("last_ai_error", "")
    snapshot = normalize_candidate_snapshot(data)

    if snapshot_error or not candidate_snapshot_has_signal(snapshot):
        snapshot = build_local_candidate_snapshot(
            resume_context,
            resume_name=resume_name,
            timeline=profile.get("experience_timeline"),
        )
        snapshot["source"] = (
            "local_fallback_after_model_error"
            if snapshot_error
            else "local_fallback_after_empty_model"
        )

    profile["candidate_snapshot"] = snapshot
    persist_candidate_snapshot(
        resume_id,
        resume_name,
        snapshot,
        provider=selected_provider,
        model_name=selected_model,
    )
    RUNTIME_STATE["last_ai_error"] = previous_ai_error
    return profile


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
            "experience_timeline": EXPERIENCE_TIMELINE_FALLBACK,
        }
    )


def ensure_resume_experience_timeline(
    profile,
    resume_text,
    job_text="",
    provider=None,
    model_name=None,
    resume_name="",
    resume_id="",
):
    if not isinstance(profile, dict):
        profile = normalize_resume_skill_profile(RESUME_SKILL_FALLBACK)

    existing_timeline = normalize_experience_timeline(
        profile.get("experience_timeline", EXPERIENCE_TIMELINE_FALLBACK)
    )
    diagnostic = {
        "provider": provider or get_selected_provider(),
        "model": model_name or get_selected_model(),
        "resume_context_chars": len(display_value(resume_text, "")),
        "existing_rows": len(existing_timeline.get("timeline", [])),
        "model_rows": 0,
        "local_rows": 0,
        "final_rows": 0,
        "source": "not_started",
        "error": "",
    }

    if existing_timeline.get("timeline"):
        profile["experience_timeline"] = existing_timeline
        diagnostic["final_rows"] = len(existing_timeline.get("timeline", []))
        diagnostic["source"] = "cached_profile"
        profile["experience_timeline_debug"] = add_timeline_diagnostic(
            resume_name,
            diagnostic,
        )
        persist_resume_experience_timeline(
            resume_id,
            resume_name,
            existing_timeline,
            provider=diagnostic["provider"],
            model_name=diagnostic["model"],
        )
        return profile

    resume_context = display_value(resume_text, "")

    if not resume_context or resume_context == "Not Found":
        profile["experience_timeline"] = existing_timeline
        diagnostic["source"] = "missing_resume_context"
        profile["experience_timeline_debug"] = add_timeline_diagnostic(
            resume_name,
            diagnostic,
        )
        return profile

    previous_ai_error = RUNTIME_STATE.get("last_ai_error", "")
    prompt = format_prompt(
        get_experience_timeline_prompt_template(),
        resume_text=resume_context,
        job_text=display_value(job_text, ""),
    )
    selected_provider = provider or get_selected_provider()
    selected_model = model_name or get_selected_model()
    diagnostic["provider"] = selected_provider
    diagnostic["model"] = selected_model
    RUNTIME_STATE["last_ai_error"] = ""
    data = safe_ai_json(
        prompt,
        EXPERIENCE_TIMELINE_SCHEMA,
        EXPERIENCE_TIMELINE_FALLBACK,
        model_name=selected_model,
        provider=selected_provider,
    )
    timeline_error = RUNTIME_STATE.get("last_ai_error", "")
    timeline = normalize_experience_timeline(data)
    diagnostic["model_rows"] = len(timeline.get("timeline", []))

    if timeline_error:
        local_timeline = build_local_experience_timeline(
            resume_context,
            job_text,
        )
        diagnostic["local_rows"] = len(local_timeline.get("timeline", []))
        diagnostic["final_rows"] = diagnostic["local_rows"]
        diagnostic["source"] = (
            "local_fallback_after_model_error"
            if diagnostic["local_rows"]
            else "model_error_and_local_empty"
        )
        diagnostic["error"] = timeline_error[:600]
        profile["experience_timeline"] = local_timeline
        RUNTIME_STATE["last_resume_skill_status"] = (
            "Experience timeline could not be generated with "
            f"{selected_provider}: "
            f"{timeline_error}"
        )
        RUNTIME_STATE["last_ai_error"] = previous_ai_error
        profile["experience_timeline_debug"] = add_timeline_diagnostic(
            resume_name,
            diagnostic,
        )
        return profile

    if not timeline.get("timeline"):
        timeline = build_local_experience_timeline(
            resume_context,
            job_text,
        )
        diagnostic["local_rows"] = len(timeline.get("timeline", []))
        diagnostic["source"] = (
            "local_fallback_after_empty_model"
            if diagnostic["local_rows"]
            else "model_empty_and_local_empty"
        )
    else:
        diagnostic["source"] = "model"

    profile["experience_timeline"] = timeline
    diagnostic["final_rows"] = len(timeline.get("timeline", []))
    RUNTIME_STATE["last_ai_error"] = previous_ai_error
    profile["experience_timeline_debug"] = add_timeline_diagnostic(
        resume_name,
        diagnostic,
    )
    persist_resume_experience_timeline(
        resume_id,
        resume_name,
        timeline,
        provider=selected_provider,
        model_name=selected_model,
    )
    return profile


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
        "additional_insights": {},
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
        "timeline_diagnostics": RUNTIME_STATE.get("timeline_diagnostics", []),
    }


def clear_runtime_status():
    RUNTIME_STATE["last_ai_error"] = ""
    RUNTIME_STATE["last_vector_store_error"] = ""
    RUNTIME_STATE["last_vector_store_status"] = ""
    RUNTIME_STATE["last_resume_skill_status"] = ""
    RUNTIME_STATE["timeline_diagnostics"] = []
    RUNTIME_STATE["skip_gemini_grading"] = False


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

    # `file` may be a SpooledTemporaryFile from FastAPI/Uvicorn without
    # a `.name`, or an in-memory BytesIO that already has one set; the
    # DOCX benchmark relies on the latter case. Sniff the bytes when
    # the filename is missing or unfamiliar.
    name = getattr(file, "name", "") or ""
    lower_name = name.lower()
    if lower_name.endswith(".pdf"):
        return extract_pdf_text(file)

    if lower_name.endswith(".docx"):
        return extract_docx_text(file)

    if hasattr(file, "read"):
        head = file.read(4)
        if hasattr(file, "seek"):
            file.seek(0)
        if head.startswith(b"%PDF"):
            return extract_pdf_text(file)
        if head[:2] == b"PK":
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
_JD_ANALYSIS_CACHE = {}


def analyze_job_description_cached(job_text, model_name=None, provider=None):
    """Memoized wrapper around analyze_job_description.

    Same JD text + same provider/model = same response, so cache it.
    Scenario matrix re-runs hit the cache 100% after the first pass.
    """
    key = (job_text.strip(), provider, model_name)
    if key in _JD_ANALYSIS_CACHE:
        return _JD_ANALYSIS_CACHE[key]
    result = analyze_job_description(job_text, model_name=model_name, provider=provider)
    _JD_ANALYSIS_CACHE[key] = result
    return result

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
        "additional_insights": normalize_additional_insights(
            get_first_present(data, ["additional_insights"], {})
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
        "additional_insights": normalize_additional_insights(
            get_first_present(data, ["additional_insights"], {})
        ),
    }


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
        "additional_insights": normalize_additional_insights(
            get_first_present(data, ["additional_insights"], {})
        ),
    }


def normalize_candidate_grading(data):
    raw_percentage = get_first_present(
        data,
        [
            "grade_percentage",
            "percentage",
            "score",
            "candidate_score",
            "fit_percentage",
            "fit_score",
        ],
        None,
    )
    grade_percentage = None
    if raw_percentage is not None:
        percentage_text = str(raw_percentage).strip().replace("%", "")
        try:
            grade_percentage = int(round(float(percentage_text)))
        except (TypeError, ValueError):
            grade_percentage = None

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

    if grade_percentage is None:
        grade_percentage = {
            "A": 90,
            "B": 80,
            "C": 65,
            "D": 45,
            "F": 25,
        }.get(grade, CANDIDATE_GRADING_FALLBACK["grade_percentage"])
    grade_percentage = max(0, min(100, grade_percentage))
    raw_criteria_scores = get_first_present(
        data,
        [
            "criteria_scores",
            "criterion_scores",
            "rubric_scores",
        ],
        {},
    )
    if not isinstance(raw_criteria_scores, dict):
        raw_criteria_scores = {}
    raw_criteria_scores = {
        **raw_criteria_scores,
        "skill_gap": get_first_present(
            raw_criteria_scores,
            ["skill_gap", "skill_gap_score", "skills_score"],
            get_first_present(data, ["skill_gap_score", "skills_score"], None),
        ),
        "years_experience": get_first_present(
            raw_criteria_scores,
            [
                "years_experience",
                "years_experience_score",
                "experience_score",
            ],
            get_first_present(
                data,
                ["years_experience_score", "experience_score"],
                None,
            ),
        ),
        "project_experience": get_first_present(
            raw_criteria_scores,
            [
                "project_experience",
                "project_experience_score",
                "hands_on_project_score",
            ],
            get_first_present(
                data,
                ["project_experience_score", "hands_on_project_score"],
                None,
            ),
        ),
        "education": get_first_present(
            raw_criteria_scores,
            [
                "education",
                "education_score",
                "educational_qualification",
                "educational_qualification_score",
            ],
            get_first_present(
                data,
                ["education_score", "educational_qualification_score"],
                None,
            ),
        ),
        "seniority": get_first_present(
            raw_criteria_scores,
            [
                "seniority",
                "seniority_score",
                "role_seniority",
                "role_seniority_score",
            ],
            get_first_present(
                data,
                ["seniority_score", "role_seniority_score"],
                None,
            ),
        ),
    }
    criteria_scores = normalize_grading_criteria_scores(raw_criteria_scores)

    return {
        "grade": grade,
        "grade_percentage": grade_percentage,
        "criteria_scores": criteria_scores,
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
        "additional_insights": normalize_additional_insights(
            get_first_present(data, ["additional_insights"], {})
        ),
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
        "additional_insights": normalize_additional_insights(
            data.get("additional_insights", {})
        ),
        "experience_timeline": normalize_experience_timeline(
            data.get("experience_timeline", EXPERIENCE_TIMELINE_FALLBACK)
        ),
        "candidate_snapshot": normalize_candidate_snapshot(
            data.get("candidate_snapshot", CANDIDATE_SNAPSHOT_FALLBACK)
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

    if normalize_experience_timeline(
        profile.get("experience_timeline", {})
    ).get("timeline"):
        return True

    if candidate_snapshot_has_signal(profile.get("candidate_snapshot", {})):
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
        persist_resume_text(resume_id, resume_name, resume_text)
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
                **(
                    skills_store.get(resume_id)
                    if isinstance(skills_store.get(resume_id), dict)
                    else {}
                ),
                "resume_id": resume_id,
                "resume_name": resume_name,
                "resume_text": resume_text,
                "skills": local_profile,
                "model": "local-fallback",
                "resume_text_last_updated_at": get_current_timestamp(),
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
        **(
            skills_store.get(resume_id)
            if isinstance(skills_store.get(resume_id), dict)
            else {}
        ),
        "resume_id": resume_id,
        "resume_name": resume_name,
        "resume_text": resume_text,
        "skills": profile,
        "model": profile_model,
        "resume_text_last_updated_at": get_current_timestamp(),
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


def calculate_local_grading_criteria_scores(
    resume_context,
    matching_skills,
    missing_skills,
):
    matching_skills = remove_placeholder_skills(matching_skills)
    missing_skills = remove_placeholder_skills(missing_skills)
    resume_context_text = display_value(resume_context, "")
    lower_context = resume_context_text.lower()
    total_skill_signals = len(matching_skills) + len(missing_skills)
    skill_gap_score = (
        round((len(matching_skills) / total_skill_signals) * 100)
        if total_skill_signals
        else 0
    )
    years_experience_score = 0
    experience_match = re.search(
        r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years|yrs)",
        lower_context,
    )
    if experience_match:
        years = float(experience_match.group(1))
        years_experience_score = max(25, min(100, round(years * 12.5)))

    project_signal_count = sum(
        1
        for keyword in [
            "project",
            "implemented",
            "built",
            "developed",
            "deployed",
            "designed",
            "client",
            "production",
        ]
        if keyword in lower_context
    )
    project_experience_score = min(100, project_signal_count * 18)
    education_terms = [
        "phd",
        "doctorate",
        "master",
        "mba",
        "m.tech",
        "mtech",
        "bachelor",
        "b.tech",
        "btech",
        "b.e.",
        "degree",
        "university",
        "college",
        "certification",
        "certified",
    ]
    education_signal_count = sum(
        1 for keyword in education_terms if keyword in lower_context
    )
    education_score = min(100, education_signal_count * 18)
    seniority_score = 35
    seniority_terms = [
        ("intern", 20),
        ("trainee", 25),
        ("junior", 35),
        ("associate", 45),
        ("developer", 55),
        ("engineer", 55),
        ("consultant", 60),
        ("senior", 75),
        ("sr.", 75),
        ("lead", 85),
        ("manager", 85),
        ("architect", 90),
        ("principal", 95),
        ("director", 95),
    ]
    for keyword, score in seniority_terms:
        if keyword in lower_context:
            seniority_score = max(seniority_score, score)

    if experience_match:
        seniority_score = max(
            seniority_score,
            min(100, round(float(experience_match.group(1)) * 10)),
        )

    return {
        "skill_gap": skill_gap_score,
        "years_experience": years_experience_score,
        "project_experience": project_experience_score,
        "education": education_score,
        "seniority": seniority_score,
    }


def build_candidate_grading_fallback(
    resume_context,
    matching_skills,
    missing_skills,
    grading_weights=None,
):
    matching_skills = remove_placeholder_skills(matching_skills)
    missing_skills = remove_placeholder_skills(missing_skills)
    grading_weights = normalize_candidate_grading_weights(grading_weights)
    resume_context_text = display_value(resume_context, "")
    lower_context = resume_context_text.lower()
    criteria_scores = calculate_local_grading_criteria_scores(
        resume_context_text,
        matching_skills,
        missing_skills,
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
    grade_percentage = calculate_weighted_grade_percentage(
        criteria_scores,
        grading_weights,
    )
    grade_percentage = max(0, min(100, grade_percentage))

    grade = grade_letter_from_percentage(grade_percentage)

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
        f"Grade {grade_percentage}% is based on {len(matching_skills)} matching skill "
        f"signal(s), {len(missing_skills)} missing skill signal(s), and "
        "weighted years/project evidence from the resume. "
        "This grade does not use the generated match score."
    )

    return {
        "grade": grade,
        "grade_percentage": grade_percentage,
        "criteria_scores": criteria_scores,
        "summary": summary,
        "strengths": strengths[:6],
        "concerns": concerns[:6],
        "weights": grading_weights,
        "source": "local_fallback",
        "additional_insights": {},
    }


def candidate_grading_is_usable(candidate_grading):
    if not isinstance(candidate_grading, dict):
        return False

    grade_percentage = candidate_grading.get("grade_percentage")
    criteria_scores = candidate_grading.get("criteria_scores")
    summary = display_value(candidate_grading.get("summary"), "")

    return (
        grade_percentage is not None
        and isinstance(criteria_scores, dict)
        and summary
        and summary != CANDIDATE_GRADING_FALLBACK["summary"]
    )


def candidate_grading_is_model(candidate_grading):
    return (
        candidate_grading_is_usable(candidate_grading)
        and candidate_grading.get("source") in AI_PROVIDER_OPTIONS
    )


def ensure_candidate_grading(
    candidate_detail,
    resume_context="",
    matching_skills=None,
    missing_skills=None,
    grading_weights=None,
):
    grading_weights = normalize_candidate_grading_weights(grading_weights)
    matching_skills = (
        matching_skills
        if matching_skills is not None
        else (
            candidate_detail.get("matching_skills", [])
            if isinstance(candidate_detail, dict)
            else []
        )
    )
    missing_skills = (
        missing_skills
        if missing_skills is not None
        else (
            candidate_detail.get("missing_skills", [])
            if isinstance(candidate_detail, dict)
            else []
        )
    )

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
        matching_skills,
        missing_skills,
        grading_weights,
    )
    candidate_detail["candidate_grading"] = fallback_grading
    return candidate_detail


def analyze_candidate_grading(
    resume_context,
    job_text,
    matching_skills,
    missing_skills,
    prompt_template=None,
    resume_name="",
    provider=None,
    model_name=None,
    grading_weights=None,
):
    provider = provider or get_selected_provider()
    model_name = model_name or get_selected_model()
    prompt_template = (
        prompt_template or get_candidate_grading_prompt_template()
    )
    grading_weights = normalize_candidate_grading_weights(
        grading_weights or get_candidate_grading_weights()
    )
    matching_skills = remove_placeholder_skills(matching_skills)
    missing_skills = remove_placeholder_skills(missing_skills)
    persistent_cache_key = get_candidate_grading_cache_key(
        resume_context,
        job_text,
        matching_skills,
        missing_skills,
        {
            "prompt_template": prompt_template,
            "grading_weights": grading_weights,
        },
        provider,
        model_name,
    )
    cache_key = get_ai_cache_key(
        "candidate_grading_v9",
        provider,
        model_name,
        resume_context,
        job_text,
        json.dumps(matching_skills, ensure_ascii=False),
        json.dumps(missing_skills, ensure_ascii=False),
        json.dumps(grading_weights, ensure_ascii=False, sort_keys=True),
        prompt_template,
    )
    cache = get_ai_cache()

    if cache_key in cache and candidate_grading_is_usable(cache[cache_key]):
        cache[cache_key] = attach_candidate_grading_weights(
            cache[cache_key],
            grading_weights,
        )
        return cache[cache_key]

    persistent_grading = get_persistent_candidate_grading(
        persistent_cache_key,
        provider=provider,
    )
    if persistent_grading:
        persistent_grading = attach_candidate_grading_weights(
            persistent_grading,
            grading_weights,
        )
        cache[cache_key] = persistent_grading
        return persistent_grading

    previous_ai_error = RUNTIME_STATE.get("last_ai_error", "")
    fallback_result = build_candidate_grading_fallback(
        resume_context,
        matching_skills,
        missing_skills,
        grading_weights,
    )

    if RUNTIME_STATE.get("skip_gemini_grading"):
        return fallback_result

    prompt = format_prompt(
        prompt_template,
        resume_text=resume_context,
        job_text=job_text,
        matching_skills=json.dumps(matching_skills, ensure_ascii=False),
        missing_skills=json.dumps(missing_skills, ensure_ascii=False),
        skill_gap_weight=grading_weights["skill_gap"],
        years_experience_weight=grading_weights["years_experience"],
        project_experience_weight=grading_weights["project_experience"],
        education_weight=grading_weights["education"],
        seniority_weight=grading_weights["seniority"],
        grading_weights=json.dumps(grading_weights, ensure_ascii=False),
    )
    RUNTIME_STATE["last_ai_error"] = ""
    data = safe_ai_json(
        prompt,
        CANDIDATE_GRADING_SCHEMA,
        CANDIDATE_GRADING_FALLBACK,
        model_name=model_name,
        provider=provider,
    )
    grading_error = RUNTIME_STATE.get("last_ai_error", "")
    result = normalize_candidate_grading(data)
    if data_has_grading_criteria_scores(data):
        criteria_scores = result["criteria_scores"]
    else:
        criteria_scores = calculate_local_grading_criteria_scores(
            resume_context,
            matching_skills,
            missing_skills,
        )
    if not criteria_scores_have_signal(criteria_scores):
        criteria_scores = calculate_local_grading_criteria_scores(
            resume_context,
            matching_skills,
            missing_skills,
        )
    result["criteria_scores"] = criteria_scores

    if grading_error or not candidate_grading_is_usable(result):
        if (
            "429" in grading_error
            or "RESOURCE_EXHAUSTED" in grading_error
            or "503" in grading_error
            or "UNAVAILABLE" in grading_error
            or "rate_limit" in grading_error.lower()
            or "overloaded" in grading_error.lower()
        ):
            RUNTIME_STATE["skip_gemini_grading"] = True

        RUNTIME_STATE["last_ai_error"] = previous_ai_error
        return fallback_result

    result["source"] = provider
    result = attach_candidate_grading_weights(result, grading_weights)
    cache[cache_key] = result
    save_persistent_candidate_grading(
        persistent_cache_key,
        result,
        provider,
        model_name,
    )
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
    resume_id="",
    grading_weights=None,
):
    provider = provider or get_selected_provider()
    grading_weights = normalize_candidate_grading_weights(
        grading_weights or get_candidate_grading_weights()
    )
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
        "candidate_detail_with_grading_v12",
        provider,
        model_name or get_selected_model(),
        score,
        resume_context,
        job_text,
        prompt_template or get_candidate_detail_prompt_template(),
        get_experience_timeline_prompt_template(),
        get_candidate_snapshot_prompt_template(),
        json.dumps(
            grading_weights,
            ensure_ascii=False,
            sort_keys=True,
        ),
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

        if not candidate_grading_is_model(
            cached_result.get("candidate_grading")
        ):
            cached_result["candidate_grading"] = analyze_candidate_grading(
                resume_context,
                job_text,
                cached_result.get("matching_skills", []),
                cached_result.get("missing_skills", []),
                resume_name=resume_name,
                provider=provider,
                model_name=model_name,
                grading_weights=grading_weights,
            )
        else:
            cached_result["candidate_grading"] = (
                attach_candidate_grading_weights(
                    cached_result["candidate_grading"],
                    grading_weights,
                )
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
    timeline_profile = ensure_resume_experience_timeline(
        resume_skill_profile,
        resume_context,
        job_text,
        provider=provider,
        model_name=model_name,
        resume_name=resume_name,
        resume_id=resume_id,
    )
    result["experience_timeline"] = (
        timeline_profile.get("experience_timeline")
        if isinstance(timeline_profile, dict)
        else EXPERIENCE_TIMELINE_FALLBACK
    )
    result["experience_timeline_debug"] = (
        timeline_profile.get("experience_timeline_debug")
        if isinstance(timeline_profile, dict)
        else {}
    )
    snapshot_profile = ensure_candidate_snapshot(
        timeline_profile,
        resume_context,
        provider=provider,
        model_name=model_name,
        resume_name=resume_name,
        resume_id=resume_id,
    )
    result["candidate_snapshot"] = (
        snapshot_profile.get("candidate_snapshot")
        if isinstance(snapshot_profile, dict)
        else CANDIDATE_SNAPSHOT_FALLBACK
    )
    result["candidate_grading"] = analyze_candidate_grading(
        resume_context,
        job_text,
        result["matching_skills"],
        result["missing_skills"],
        resume_name=resume_name,
        provider=provider,
        model_name=model_name,
        grading_weights=grading_weights,
    )
    if (
        not RUNTIME_STATE.get("last_ai_error")
        and candidate_grading_is_model(result.get("candidate_grading"))
        and normalize_experience_timeline(
            result.get("experience_timeline", {})
        ).get("timeline")
    ):
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

def persist_analysis_session(*args, **kwargs) -> str:
    """Append one analysis session to vector_store/analysis_sessions.json.

    Accepts either a single ``payload`` dict (legacy callers) or the
    keyword-argument form used by ``api.py`` (e.g. ``job_description=``,
    ``file_cache=``). All extra args are folded into the stored payload
    so any caller shape works.
    """
    import os, json, uuid

    if args and isinstance(args[0], dict) and not kwargs:
        payload = dict(args[0])
    else:
        payload = dict(kwargs)

    base_dir = payload.pop("base_dir", "vector_store")
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







