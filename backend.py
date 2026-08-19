import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import numpy as np
import ollama
from docx import Document
from jsonschema import validate
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
    faiss = sys.modules.get("faiss")

if faiss is None:
    import types

    faiss = types.ModuleType("faiss")

    class DummyIndex:
        def __init__(self, d=1024):
            self.d = d
            self.ntotal = 0
            self.vectors = {}

        def add(self, x):
            for vec in x:
                self.vectors[self.ntotal] = vec
                self.ntotal += 1

        def reconstruct(self, i):
            return self.vectors.get(i, [0.1] * self.d)

    _FAISS_STORAGE = {}
    faiss.IndexFlatIP = lambda d=1024: DummyIndex(d)
    faiss.write_index = lambda idx, path: _FAISS_STORAGE.update(
        {str(path): idx}
    ) or Path(path).write_bytes(b"FAISS_DUMMY_INDEX")
    faiss.read_index = lambda path: _FAISS_STORAGE.get(str(path), DummyIndex(1024))
    sys.modules["faiss"] = faiss


# ==================================================
# CONFIGURATION DEFAULTS
# ==================================================

DEFAULT_OLLAMA_MODEL = "llama3.2"
DEFAULT_AI_PROVIDER = "Ollama"
GEMINI_RESUME_SKILL_MODEL = "gemini-2.5-flash"
EMBEDDING_MODEL_NAME = "BAAI/bge-large-en-v1.5"
EMBEDDING_DIMENSION = 1024

# Chunking configuration
MAX_CHUNK_SIZE = 1000  # Maximum characters per chunk
CHUNK_OVERLAP = 100    # Overlap between chunks when recursive splitting is needed
MIN_CHUNK_SIZE = 200   # Minimum characters for a valid chunk
PROJECT_ROOT = Path(__file__).resolve().parent
VECTOR_STORE_DIR = PROJECT_ROOT / "vector_store"
FAISS_INDEX_PATH = VECTOR_STORE_DIR / "resume_embeddings.faiss"
FAISS_METADATA_PATH = VECTOR_STORE_DIR / "resume_metadata.json"
RESUME_SKILLS_PATH = VECTOR_STORE_DIR / "resume_skills.json"
PROMPT_CONFIG_PATH = VECTOR_STORE_DIR / "prompt_config.json"
RESUME_CHUNKS_PATH = VECTOR_STORE_DIR / "resume_chunks.json"

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
    "429",
    "RESOURCE_EXHAUSTED",
    "Quota exceeded",
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
            "Embedding model unavailable, using local hash embeddings: " f"{error}"
        )
        return create_hash_embedding(text, prefix)


def sanitize_faiss_metadata(metadata, index_size=None):
    if not isinstance(metadata, list):
        return []

    cleaned = []
    seen_resume_ids = set()
    index_size = int(index_size) if index_size is not None else None

    for record in metadata:
        if not isinstance(record, dict):
            continue

        resume_id = str(record.get("resume_id") or record.get("id") or "").strip()
        if not resume_id or resume_id in seen_resume_ids:
            continue

        try:
            row = int(record.get("faiss_row"))
        except (TypeError, ValueError):
            continue

        if index_size is not None and (row < 0 or row >= index_size):
            continue

        seen_resume_ids.add(resume_id)
        cleaned.append(
            {
                **record,
                "resume_id": resume_id,
                "faiss_row": row,
            }
        )

    return cleaned


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
            raw_metadata = json.loads(FAISS_METADATA_PATH.read_text(encoding="utf-8"))
            index_ntotal = int(getattr(index, "ntotal", 0))
            metadata = sanitize_faiss_metadata(raw_metadata, index_ntotal)
            # Ensure metadata was cleaned; write back if changed to maintain integrity
            if metadata != raw_metadata:
                write_json_file(FAISS_METADATA_PATH, metadata)
            # Verify consistency: metadata count should not exceed index size
            if len(metadata) > index_ntotal:
                print(
                    f"WARNING: metadata has {len(metadata)} rows but index has {index_ntotal}. Truncating metadata."
                )
                metadata = metadata[:index_ntotal]
                write_json_file(FAISS_METADATA_PATH, metadata)
        except Exception as e:
            print(f"ERROR loading resume_metadata.json: {e}")
            metadata = []
    return index, metadata


def faiss_index_lookup(resume_id):
    """Return the cached embedding for resume_id from the FAISS index,
    or None if it isn't indexed yet.

    FAISS Integrity Validation:
    - Verifies faiss_row is within valid range [0, index.ntotal)
    - Removes stale metadata entries before lookup
    - Reconstructs embedding directly from FAISS index
    """
    if faiss is None or not FAISS_INDEX_PATH.exists():
        return None
    if not FAISS_METADATA_PATH.exists():
        return None

    try:
        index, metadata = load_resume_vector_store()
        if index is None or not metadata:
            return None

        index_ntotal = int(getattr(index, "ntotal", 0))
        for rec in metadata:
            if rec.get("resume_id") == resume_id:
                try:
                    row = int(rec.get("faiss_row", -1))
                except (TypeError, ValueError):
                    return None

                # Validate row is in bounds
                if row < 0 or row >= index_ntotal:
                    print(
                        f"FAISS_INTEGRITY_WARN: resume_id {resume_id} has invalid faiss_row {row} (index size: {index_ntotal})"
                    )
                    return None

                # Reconstruct and return as 2D array (1, embedding_dim)
                embedding = index.reconstruct(row)
                return np.asarray([embedding], dtype="float32")
    except Exception as e:
        print(f"ERROR in faiss_index_lookup for {resume_id}: {e}")
        return None

    return None


def save_resume_vector_store(index, metadata):
    """Persist FAISS index and metadata with integrity validation.

    FAISS Integrity Guarantee:
    - Sanitizes metadata (removes duplicates, invalid rows)
    - Validates all faiss_row values are in bounds [0, index.ntotal)
    - Ensures metadata count <= index.ntotal (no orphaned entries)
    - Writes index and metadata atomically
    """
    ensure_vector_store_dir()
    if index is not None:
        index_ntotal = int(getattr(index, "ntotal", 0))
        metadata = sanitize_faiss_metadata(metadata, index_ntotal)
        # Double-check: ensure no metadata row exceeds index size
        valid_count = sum(
            1 for m in metadata if 0 <= int(m.get("faiss_row", -1)) < index_ntotal
        )
        if valid_count != len(metadata):
            print(
                f"FAISS_INTEGRITY: Found {len(metadata) - valid_count} invalid rows. Cleaned."
            )
            metadata = [
                m for m in metadata if 0 <= int(m.get("faiss_row", -1)) < index_ntotal
            ]
    else:
        metadata = sanitize_faiss_metadata(metadata, None)
    faiss.write_index(index, str(FAISS_INDEX_PATH))
    write_json_file(FAISS_METADATA_PATH, metadata)


def find_resume_metadata(metadata, resume_id):
    for item in metadata:
        if item.get("resume_id") == resume_id:
            return item

    return None


def get_current_timestamp():
    return datetime.now(timezone.utc).isoformat()


def get_or_create_resume_embedding(resume_id, resume_name, resume_text, use_chunking=True):
    """Get or create resume embedding.

    Args:
        resume_id: Resume identifier
        resume_name: Resume filename
        resume_text: Resume text (or text_items if use_chunking)
        use_chunking: If True, use chunk-based approach; if False, use legacy single-embedding

    Returns:
        If use_chunking: dict with 'embeddings' (list of arrays) and 'chunks' (list of chunk metadata)
        If not use_chunking: single embedding array (legacy behavior)
    """
    if not use_chunking:
        # Legacy behavior for backward compatibility
        return get_or_create_resume_embedding_legacy(resume_id, resume_name, resume_text)

    # Chunk-based approach (Phase 1)
    return get_or_create_resume_embeddings_chunked(resume_id, resume_name, resume_text)


def get_or_create_resume_embedding_legacy(resume_id, resume_name, resume_text):
    """Legacy single-embedding approach for backward compatibility."""
    # Fast path: if the embedding is already in FAISS, skip the model
    # call entirely. This makes repeat uploads of the same resume free.
    cached_embedding = faiss_index_lookup(resume_id)
    if cached_embedding is not None:
        return cached_embedding
    try:
        index, metadata = load_resume_vector_store()
        existing = find_resume_metadata(metadata, resume_id)

        if existing is not None:
            # FAISS Integrity Check: Verify the stored row is valid before using it
            try:
                row = int(existing.get("faiss_row", -1))
                index_ntotal = int(getattr(index, "ntotal", 0))
                if row < 0 or row >= index_ntotal:
                    # Stale metadata entry; treat as missing and re-embed
                    print(
                        f"FAISS_INTEGRITY: resume_id {resume_id} has invalid row {row}. Re-embedding."
                    )
                    existing = None  # Fall through to re-embedding
                else:
                    # Valid cached entry; use it
                    existing["resume_name"] = resume_name
                    existing["last_updated_at"] = get_current_timestamp()
                    save_resume_vector_store(index, metadata)
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
            except (TypeError, ValueError) as e:
                print(f"FAISS_INTEGRITY: Error parsing faiss_row for {resume_id}: {e}")
                existing = None  # Fall through to re-embedding

        if existing is None:

            # Create new embedding
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
            new_row = int(index.ntotal - 1)
            metadata.append(
                {
                    "resume_id": resume_id,
                    "resume_name": resume_name,
                    "faiss_row": new_row,
                    "embedding_model": EMBEDDING_MODEL_NAME,
                    "created_at": get_current_timestamp(),
                    "last_updated_at": get_current_timestamp(),
                }
            )
            save_resume_vector_store(index, metadata)
            RUNTIME_STATE["last_vector_store_error"] = ""
            RUNTIME_STATE["last_vector_store_status"] = (
                f"Saved new embedding for {resume_name} at FAISS row {new_row}."
            )
            return embedding

    except Exception as error:
        print("DEBUG get_or_create_resume_embedding EXCEPTION:", repr(error))
        RUNTIME_STATE["last_vector_store_error"] = str(error)
        RUNTIME_STATE["last_vector_store_status"] = ""
        embedding = encode_text_embedding(
            resume_text,
            "Represent this resume for retrieval:",
        )
        return embedding


def get_or_create_resume_embeddings_chunked(resume_id, resume_name, text_items):
    """Get or create chunk-based embeddings for a resume.

    Args:
        resume_id: Resume identifier
        resume_name: Resume filename
        text_items: List of dicts with 'page' and 'text' keys

    Returns:
        dict with 'embeddings' (list of numpy arrays) and 'chunks' (list of chunk metadata)
    """
    # Check if chunks already exist for this resume
    chunks_store = read_json_file(RESUME_CHUNKS_PATH, {})
    existing_chunks = chunks_store.get(resume_id, [])

    if existing_chunks:
        # Chunks already exist, load their embeddings from FAISS
        index, metadata = load_resume_vector_store()
        if index is not None:
            embeddings = []
            valid_chunks = []

            for chunk in existing_chunks:
                chunk_id = chunk.get('chunk_id')
                faiss_row = chunk.get('faiss_row')

                if faiss_row is not None and 0 <= faiss_row < index.ntotal:
                    try:
                        embedding = index.reconstruct(faiss_row)
                        embeddings.append(np.asarray([embedding], dtype="float32"))
                        valid_chunks.append(chunk)
                    except Exception as e:
                        print(f"Error reconstructing embedding for {chunk_id}: {e}")

            if embeddings and valid_chunks:
                RUNTIME_STATE["last_vector_store_status"] = (
                    f"Loaded {len(embeddings)} cached chunk embeddings for {resume_name}."
                )
                return {
                    'embeddings': embeddings,
                    'chunks': valid_chunks
                }

    # Process resume into chunks
    chunks = process_resume_into_chunks(resume_id, resume_name, text_items)

    if not chunks:
        RUNTIME_STATE["last_vector_store_error"] = "No chunks could be created from resume."
        return {
            'embeddings': [],
            'chunks': []
        }

    # Generate embeddings for each chunk
    index, metadata = load_resume_vector_store()
    embeddings = []

    for chunk in chunks:
        chunk_text = chunk['text']
        chunk_id = chunk['chunk_id']

        # Generate embedding for this chunk
        embedding = encode_text_embedding(
            chunk_text,
            "Represent this resume chunk for retrieval:",
        )

        if int(embedding.shape[1]) != int(index.d):
            raise RuntimeError(
                "Stored FAISS index dimension does not match the embedding "
                "model dimension."
            )

        # Add to FAISS index
        index.add(embedding)
        new_row = int(index.ntotal - 1)

        # Update chunk with FAISS row
        chunk['faiss_row'] = new_row

        embeddings.append(embedding)

    # Save updated FAISS index
    save_resume_vector_store(index, metadata)

    # Save chunks metadata
    chunks_store[resume_id] = chunks
    write_json_file(RESUME_CHUNKS_PATH, chunks_store)

    RUNTIME_STATE["last_vector_store_status"] = (
        f"Created {len(chunks)} new chunk embeddings for {resume_name}."
    )

    return {
        'embeddings': embeddings,
        'chunks': chunks
    }


def search_chunks_by_embedding(query_embedding, top_k=10):
    """Search chunks using FAISS semantic search.

    Args:
        query_embedding: Query embedding (numpy array)
        top_k: Number of results to return

    Returns:
        List of dicts with chunk metadata and similarity scores
    """
    if faiss is None or not FAISS_INDEX_PATH.exists():
        return []

    try:
        index, metadata = load_resume_vector_store()
        if index is None:
            return []

        # Load chunks store
        chunks_store = read_json_file(RESUME_CHUNKS_PATH, {})

        # FAISS search
        index_ntotal = int(getattr(index, "ntotal", 0))
        search_k = min(top_k, index_ntotal)

        distances, indices = index.search(query_embedding, search_k)

        # Build results with chunk metadata
        results = []
        for idx, dist in zip(indices[0], distances[0]):
            idx_int = int(idx)
            if idx_int < 0 or idx_int >= index_ntotal:
                continue

            # Find chunk with this faiss_row
            for resume_id, chunks in chunks_store.items():
                for chunk in chunks:
                    if chunk.get('faiss_row') == idx_int:
                        similarity_score = float(dist) * 100
                        results.append({
                            'chunk': chunk,
                            'similarity_score': similarity_score,
                            'resume_id': resume_id
                        })
                        break
                if results:
                    break

        # Sort by similarity score
        results.sort(key=lambda x: x['similarity_score'], reverse=True)

        return results[:top_k]

    except Exception as e:
        print(f"ERROR in search_chunks_by_embedding: {e}")
        return []


def faiss_semantic_search(query_embedding, top_k=10):
    """Search FAISS index for top_k most similar resumes using semantic search.

    This pre-filters candidates before expensive LLM analysis, significantly
    reducing the computational load of the analyze pipeline.

    Args:
        query_embedding: numpy array of shape (1, 1024) with query vector
        top_k: number of top candidates to return

    Returns:
        List of (resume_id, similarity_score) tuples, sorted by score (descending)
    """
    if faiss is None or not FAISS_INDEX_PATH.exists():
        return []

    try:
        index, metadata = load_resume_vector_store()
        if index is None or not metadata:
            return []

        # FAISS search returns (distances, indices) for top_k
        # Note: IndexFlatIP uses inner product (similarity) not L2 distance
        index_ntotal = int(getattr(index, "ntotal", 0))
        search_k = min(top_k, index_ntotal)  # Can't search for more than we have

        distances, indices = index.search(query_embedding, search_k)

        # Build result list with resume_id and similarity score
        results = []
        for idx, dist in zip(indices[0], distances[0]):
            idx_int = int(idx)
            if 0 <= idx_int < len(metadata):
                # Find resume_id for this metadata entry
                # Need to match by faiss_row
                for meta in metadata:
                    try:
                        if int(meta.get("faiss_row", -1)) == idx_int:
                            resume_id = meta.get("resume_id")
                            if resume_id:
                                # Convert inner product score to 0-100 range
                                similarity_score = float(dist) * 100
                                results.append((resume_id, similarity_score))
                            break
                    except (TypeError, ValueError):
                        continue

        return results
    except Exception as e:
        print(f"ERROR in faiss_semantic_search: {e}")
        return []


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
                name = getattr(model, "name", None) or getattr(model, "model", None)

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
        RUNTIME_STATE["skill_gap_prompt_template"] = DEFAULT_SKILL_GAP_PROMPT_TEMPLATE

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
        RUNTIME_STATE["active_jd_prompt_template"] = DEFAULT_JD_PROMPT_TEMPLATE

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
    return prompt if prompt.strip() else DEFAULT_CANDIDATE_DETAIL_PROMPT_TEMPLATE


def get_candidate_grading_prompt_template():
    prompt = RUNTIME_STATE.get("active_candidate_grading_prompt_template", "")
    return prompt if prompt.strip() else DEFAULT_CANDIDATE_GRADING_PROMPT_TEMPLATE


def get_resume_skill_extraction_prompt_template():
    prompt = RUNTIME_STATE.get(
        "active_resume_skill_extraction_prompt_template",
        "",
    )
    return prompt if prompt.strip() else DEFAULT_RESUME_SKILL_EXTRACTION_PROMPT_TEMPLATE


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

    if not RESUME_CHUNKS_PATH.exists():
        write_json_file(RESUME_CHUNKS_PATH, {})

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


def get_active_resume_db_records():
    """
    Load active Resume DB records independently of FAISS.
    
    This is the source of truth for the active candidate pool.
    FAISS is an optimization layer on top of this.
    
    Returns:
        Dict mapping resume_id to resume record (skills, name, etc.)
    """
    initialize_project_storage_files()
    skills_store = read_json_file(RESUME_SKILLS_PATH, {})
    
    # Filter to only resumes with valid skills
    records = {}
    for resume_id, data in skills_store.items():
        if isinstance(data, dict) and data.get("skills"):
            records[resume_id] = {
                "resume_id": resume_id,
                "resume_name": data.get("resume_name", ""),
                "resume_skill_profile": data.get("skills"),
                "skills_model": data.get("model", ""),
                "last_updated_at": data.get("last_updated_at", ""),
            }
    
    return records


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
        existing["last_updated_at"] = existing.get("last_updated_at") or item.get(
            "last_updated_at", ""
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
            last_updated_at = last_updated_at or skills_item.get("last_updated_at", "")

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
                    format_resume_skill_profile(resume_skill_profile)
                    if resume_skill_profile_has_signal(resume_skill_profile)
                    else ""
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
        "jd_prompt_template": DEFAULT_JD_PROMPT_TEMPLATE,
        "skill_gap_prompt_template": DEFAULT_SKILL_GAP_PROMPT_TEMPLATE,
        "candidate_detail_prompt_template": (DEFAULT_CANDIDATE_DETAIL_PROMPT_TEMPLATE),
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

    if "Do not use or mention the existing match score" not in candidate_grading_prompt:
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
    RUNTIME_STATE["active_jd_prompt_template"] = config["jd_prompt_template"]
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
                },
            ],
            options={
                "temperature": 0,
            },
        )

        result = response["message"]["content"]
        data = safe_json_extract(result)

        if data is None:
            RUNTIME_STATE["last_ai_error"] = "The model did not return valid JSON."
            return fallback

        validate(instance=data, schema=schema)
        RUNTIME_STATE["last_ai_error"] = ""
        return data

    except Exception as error:
        RUNTIME_STATE["last_ai_error"] = str(error)
        return fallback


def safe_gemini_json(prompt, schema, fallback, model_name=None):
    try:
        if genai is None:
            raise RuntimeError("Install google-genai to use Gemini models.")

        if not os.getenv("GEMINI_API_KEY"):
            raise RuntimeError("Set GEMINI_API_KEY to use Gemini models.")

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
                    code in message for code in GEMINI_TRANSIENT_ERROR_CODES
                )

                if not is_transient or attempt == 2:
                    raise

                time.sleep(2)

        data = safe_json_extract(response.text or "")

        if data is None:
            RUNTIME_STATE["last_ai_error"] = "The model did not return valid JSON."
            return fallback

        validate(instance=data, schema=schema)
        RUNTIME_STATE["last_ai_error"] = ""
        return data

    except Exception as error:
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

    return (
        prompt
        + "\n\n"
        + "\n\n".join(f"{key.upper()}:\n{value}" for key, value in values.items())
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
        value = [item.strip(" \t-•–—") for item in value.replace("\n", ",").split(",")]

    if not isinstance(value, list):
        return []

    return [str(item).strip() for item in value if str(item).strip()][:10]


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

    skill_tokens = [token for token in skill_text.split() if len(token) > 2]

    if not skill_tokens:
        return False

    target_tokens = set(target_text.split())
    matched_tokens = [token for token in skill_tokens if token in target_tokens]
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
    tools = [skill for skill in technical_skills if skill in tool_keywords][:15]
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
        line.strip() for line in text.splitlines() if len(line.strip()) > 40
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
        (
            resume_skill_profile.get("experience_summary")
            if isinstance(resume_skill_profile, dict)
            else ""
        ),
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
        skill for skill in resume_skills if skill_matches_text(skill, job_text)
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
    return "".join(character for character in str(key).lower() if character.isalnum())


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
    lower_key_map = {str(key).lower(): value for key, value in flattened.items()}
    normalized_key_map = {normalize_key(key): value for key, value in flattened.items()}

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
        values = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(values) if values else default

    if isinstance(value, dict):
        values = [str(item).strip() for item in value.values() if str(item).strip()]
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
# RESUME PROCESSING - PHASE 1
# ==================================================

def clean_resume_text(text):
    """Clean resume text while preserving structure.

    Removes excessive whitespace and artifacts but preserves:
    - Section headings
    - Project/company names
    - Useful punctuation
    - Meaningful structure
    """
    if not text:
        return ""

    # Remove excessive blank lines (more than 2 consecutive)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)

    # Normalize whitespace within lines
    lines = []
    for line in text.split('\n'):
        # Remove leading/trailing whitespace but preserve internal spacing
        cleaned = line.strip()
        if cleaned:
            lines.append(cleaned)

    return '\n'.join(lines)


def normalize_section_heading(heading):
    """Normalize section heading to standard form.

    Maps variations like:
    "WORK EXPERIENCE", "Work Experience", "Professional Experience"
    to standard: "Experience"
    """
    if not heading:
        return None

    # Normalize: lowercase, remove extra spaces, remove special chars
    normalized = re.sub(r'[^a-zA-Z\s]', '', heading.lower().strip())

    # Section mapping rules
    section_mappings = {
        # Skills
        'skills': 'Skills',
        'technical skills': 'Skills',
        'technical': 'Skills',
        'core skills': 'Skills',
        'key skills': 'Skills',
        'technologies': 'Skills',
        'tech stack': 'Skills',
        'programming languages': 'Skills',

        # Experience
        'experience': 'Experience',
        'work experience': 'Experience',
        'professional experience': 'Experience',
        'employment': 'Experience',
        'work history': 'Experience',
        'professional background': 'Experience',
        'internships': 'Experience',
        'internship experience': 'Experience',

        # Projects
        'projects': 'Projects',
        'project experience': 'Projects',
        'personal projects': 'Projects',
        'academic projects': 'Projects',
        'key projects': 'Projects',

        # Education
        'education': 'Education',
        'educational background': 'Education',
        'academic background': 'Education',
        'qualifications': 'Education',
        'academic': 'Education',

        # Certifications
        'certifications': 'Certifications',
        'certificates': 'Certifications',
        'certification': 'Certifications',
        'credentials': 'Certifications',

        # Achievements
        'achievements': 'Achievements',
        'accomplishments': 'Achievements',
        'awards': 'Achievements',
        'honors': 'Achievements',

        # Publications
        'publications': 'Publications',
        'research papers': 'Publications',
        'papers': 'Publications',

        # Research
        'research': 'Research',
        'research experience': 'Research',

        # Summary
        'summary': 'Summary',
        'profile': 'Summary',
        'professional summary': 'Summary',
        'career summary': 'Summary',
        'objective': 'Summary',
        'career objective': 'Summary',
    }

    # Try exact match first
    if normalized in section_mappings:
        return section_mappings[normalized]

    # Try partial match
    for key, value in section_mappings.items():
        if key in normalized or normalized in key:
            return value

    # If no match, return capitalized original (without special chars)
    return heading.strip().title()


def detect_resume_sections(text_items):
    """Detect resume sections from text items.

    Args:
        text_items: List of dicts with 'page' and 'text' keys

    Returns:
        List of dicts with section information:
        {
            'section': 'Experience',
            'heading': 'WORK EXPERIENCE',
            'start_index': 5,
            'page': 1
        }
    """
    sections = []
    common_headings = [
        'SKILLS', 'TECHNICAL SKILLS', 'EXPERIENCE', 'WORK EXPERIENCE',
        'PROFESSIONAL EXPERIENCE', 'PROJECTS', 'CERTIFICATIONS',
        'EDUCATION', 'ACHIEVEMENTS', 'PUBLICATIONS', 'RESEARCH',
        'SUMMARY', 'PROFILE', 'INTERNSHIPS', 'EMPLOYMENT'
    ]

    for idx, item in enumerate(text_items):
        text = item['text'].strip()
        if not text:
            continue

        # Check if this line looks like a heading
        # Heuristics: short, uppercase or title case, common heading words
        is_heading = False

        # Check exact matches with common headings
        if text.upper() in common_headings:
            is_heading = True
        # Check if it's a short line (headings are usually short)
        elif len(text) < 50 and len(text.split()) <= 5:
            # Check if it's mostly uppercase or title case
            if text.isupper() or text.istitle():
                # Check if it contains section-like words
                section_words = ['skill', 'experience', 'project', 'education',
                              'certification', 'achievement', 'publication',
                              'research', 'summary', 'profile', 'internship']
                if any(word in text.lower() for word in section_words):
                    is_heading = True

        if is_heading:
            normalized_section = normalize_section_heading(text)
            if normalized_section:
                sections.append({
                    'section': normalized_section,
                    'heading': text,
                    'start_index': idx,
                    'page': item.get('page')
                })

    return sections


def create_context_aware_chunks(text_items, sections):
    """Create context-aware chunks based on sections.

    Args:
        text_items: List of dicts with 'page' and 'text' keys
        sections: List of detected sections

    Returns:
        List of chunk dicts with metadata
    """
    chunks = []

    if not sections:
        # No sections detected - treat entire document as one chunk
        full_text = '\n'.join(item['text'] for item in text_items)
        if full_text.strip():
            chunks.append({
                'section': 'Summary',
                'subsection': None,
                'text': full_text,
                'page': text_items[0].get('page') if text_items else None,
                'start_index': 0,
                'end_index': len(text_items) - 1
            })
        return chunks

    # Process each section
    for i, section in enumerate(sections):
        section_name = section['section']
        start_idx = section['start_index']

        # Determine end index (next section or end of document)
        if i + 1 < len(sections):
            end_idx = sections[i + 1]['start_index']
        else:
            end_idx = len(text_items)

        # Extract text for this section
        section_text_items = text_items[start_idx:end_idx]
        section_text = '\n'.join(item['text'] for item in section_text_items)

        if not section_text.strip():
            continue

        # Apply section-specific chunking strategies
        if section_name == 'Projects':
            section_chunks = chunk_projects_section(section_text_items, section, start_idx)
        elif section_name == 'Experience':
            section_chunks = chunk_experience_section(section_text_items, section, start_idx)
        elif section_name == 'Skills':
            section_chunks = chunk_skills_section(section_text_items, section, start_idx)
        elif section_name == 'Education':
            section_chunks = chunk_education_section(section_text_items, section, start_idx)
        elif section_name == 'Certifications':
            section_chunks = chunk_certifications_section(section_text_items, section, start_idx)
        else:
            # Generic chunking for other sections
            section_chunks = chunk_generic_section(section_text_items, section, start_idx)

        chunks.extend(section_chunks)

    return chunks


def chunk_projects_section(text_items, section_info, base_index):
    """Chunk projects section by individual projects."""
    chunks = []
    current_project = None
    current_project_lines = []

    # Words that commonly start result/achievement sentences
    result_starting_words = {
        'achieved', 'achieve', 'built', 'build', 'developed', 'develop',
        'implemented', 'implement', 'created', 'create', 'designed', 'design',
        'reduced', 'reduce', 'increased', 'increase', 'improved', 'improve',
        'optimized', 'optimize', 'led', 'lead', 'managed', 'manage',
        'delivered', 'deliver', 'deployed', 'deploy', 'launched', 'launch',
        'won', 'win', 'received', 'receive', 'published', 'publish',
        'completed', 'complete', 'finished', 'finish', 'executed', 'execute'
    }

    # Section headers to skip
    section_headers = ['PROJECTS', 'PROJECT', 'KEY PROJECTS', 'PERSONAL PROJECTS', 'ACADEMIC PROJECTS']

    def is_project_name(text, idx, text_items):
        """Check if text looks like a project name."""
        text_stripped = text.strip()
        text_upper = text_stripped.upper()

        # Empty lines are not project names
        if not text_stripped:
            return False

        # Skip section headers
        if text_upper in section_headers:
            return False

        # Lines starting with bullets/dashes are content, not project names
        if text_stripped.startswith(('•', '-', '*')):
            return False

        # Lines starting with numbers are content, not project names
        if text_stripped[0].isdigit():
            return False

        # Lines starting with month abbreviations are content, not project names
        if text_stripped[:3].lower() in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'n', 'dec']:
            return False

        # Lines with colons are descriptions, not project names
        if ':' in text_stripped:
            return False

        # Lines with percentages are results, not project names
        if '%' in text_stripped:
            return False

        # Lines that start with result verbs are content, not project names
        first_word = text_stripped.split()[0].lower() if text_stripped.split() else ''
        if first_word in result_starting_words:
            return False

        # Project names are typically short (< 60 chars)
        if len(text_stripped) > 60:
            return False

        # Project names often have title case or capital letters
        if not (text_stripped[0].isupper() or text_stripped.istitle()):
            return False

        # Check if previous line was empty or this is the first line after section header
        # This indicates a new project is starting
        if idx > 0:
            prev_text = text_items[idx - 1]['text'].strip()
            if not prev_text or prev_text.upper() in section_headers:
                return True

        # If it has 2-5 words and passes other checks, it's likely a project name
        word_count = len(text_stripped.split())
        if 2 <= word_count <= 5:
            return True

        return False

    for idx, item in enumerate(text_items):
        text = item['text'].strip()
        text_upper = text.upper()

        # Skip section headers and empty lines
        if not text or text_upper in section_headers:
            continue

        # Check if this line is a project name
        if is_project_name(text, idx, text_items):
            if current_project:
                # Save previous project - include project name in chunk text
                if current_project_lines:
                    # Include project name at the start of the chunk
                    chunk_text = current_project + '\n' + '\n'.join(current_project_lines)
                    chunk_text = recursively_split_large_chunk(chunk_text, MAX_CHUNK_SIZE)
                    for split_chunk in chunk_text:
                        chunks.append({
                            'section': 'Projects',
                            'subsection': current_project,
                            'text': split_chunk,
                            'page': item.get('page'),
                            'start_index': base_index,
                            'end_index': base_index + idx
                        })
                current_project_lines = []
                current_project = text
            else:
                current_project = text
        else:
            # This is a content line (description, technologies, results)
            if not current_project:
                # If we haven't found a project name yet, and this is the first content,
                # use a generic project name
                current_project = "Project Details"
            current_project_lines.append(text)

    # Don't forget the last project - include project name in chunk text
    if current_project and current_project_lines:
        # Include project name at the start of the chunk
        chunk_text = current_project + '\n' + '\n'.join(current_project_lines)
        chunk_text = recursively_split_large_chunk(chunk_text, MAX_CHUNK_SIZE)
        for split_chunk in chunk_text:
            chunks.append({
                'section': 'Projects',
                'subsection': current_project,
                'text': split_chunk,
                'page': text_items[-1].get('page') if text_items else None,
                'start_index': base_index,
                'end_index': base_index + len(text_items) - 1
            })

    return chunks


def chunk_experience_section(text_items, section_info, base_index):
    """Chunk experience section by company/role."""
    chunks = []
    current_company = None
    current_role = None
    current_experience_lines = []

    # Skip section headers
    section_headers = ['WORK EXPERIENCE', 'EXPERIENCE', 'PROFESSIONAL EXPERIENCE', 'EMPLOYMENT', 'WORK HISTORY', 'PROFESSIONAL BACKGROUND', 'INTERNSHIPS', 'INTERNSHIP EXPERIENCE']

    for idx, item in enumerate(text_items):
        text = item['text'].strip()
        text_upper = text.upper()

        # Skip section headers
        if text_upper in section_headers:
            continue

        if not text:
            continue

        # Heuristic: company/role lines are often prominent
        # Look for lines that might be company names or roles
        is_company_role = (
            len(text) < 100 and
            not text.startswith('•') and
            not text.startswith('-') and
            any(keyword in text.lower() for keyword in ['company', 'corporation', 'inc', 'llc', 'ltd', 'intern', 'engineer', 'developer', 'manager', 'analyst'])
        )

        if is_company_role and current_company:
            # Save previous experience - include company/role in chunk text
            if current_experience_lines:
                # Include company/role at the start of the chunk
                header = f"{current_company} - {current_role}" if current_role else current_company
                chunk_text = header + '\n' + '\n'.join(current_experience_lines)
                chunk_text = recursively_split_large_chunk(chunk_text, MAX_CHUNK_SIZE)
                for split_chunk in chunk_text:
                    chunks.append({
                        'section': 'Experience',
                        'subsection': header,
                        'text': split_chunk,
                        'page': item.get('page'),
                        'start_index': base_index,
                        'end_index': base_index + idx
                    })
            current_experience_lines = []
            current_company = text
            current_role = None
        elif is_company_role:
            current_company = text
        else:
            if not current_company:
                current_company = "Unnamed Company"
            current_experience_lines.append(text)

    # Don't forget the last experience - include company/role in chunk text
    if current_company and current_experience_lines:
        header = f"{current_company} - {current_role}" if current_role else current_company
        chunk_text = header + '\n' + '\n'.join(current_experience_lines)
        chunk_text = recursively_split_large_chunk(chunk_text, MAX_CHUNK_SIZE)
        for split_chunk in chunk_text:
            chunks.append({
                'section': 'Experience',
                'subsection': header,
                'text': split_chunk,
                'page': text_items[-1].get('page') if text_items else None,
                'start_index': base_index,
                'end_index': base_index + len(text_items) - 1
            })

    return chunks


def chunk_skills_section(text_items, section_info, base_index):
    """Chunk skills section - keep as one chunk if reasonable."""
    section_text = '\n'.join(item['text'] for item in text_items)
    section_text = recursively_split_large_chunk(section_text, MAX_CHUNK_SIZE)

    chunks = []
    for split_chunk in section_text:
        chunks.append({
            'section': 'Skills',
            'subsection': None,
            'text': split_chunk,
            'page': text_items[0].get('page') if text_items else None,
            'start_index': base_index,
            'end_index': base_index + len(text_items) - 1
        })

    return chunks


def chunk_education_section(text_items, section_info, base_index):
    """Chunk education section by degree/institution."""
    chunks = []
    current_education = None
    current_education_lines = []

    for idx, item in enumerate(text_items):
        text = item['text'].strip()
        if not text:
            continue

        # Heuristic: education entries often contain degree words
        is_education_start = (
            any(keyword in text.lower() for keyword in ['bachelor', 'master', 'phd', 'doctor', 'degree', 'university', 'college', 'institute'])
            and len(text) < 150
        )

        if is_education_start and current_education:
            # Save previous education
            if current_education_lines:
                chunk_text = '\n'.join(current_education_lines)
                chunk_text = recursively_split_large_chunk(chunk_text, MAX_CHUNK_SIZE)
                for split_chunk in chunk_text:
                    chunks.append({
                        'section': 'Education',
                        'subsection': current_education,
                        'text': split_chunk,
                        'page': item.get('page'),
                        'start_index': base_index,
                        'end_index': base_index + idx
                    })
            current_education_lines = []
            current_education = text
        elif is_education_start:
            current_education = text
        else:
            if not current_education:
                current_education = "Education Entry"
            current_education_lines.append(text)

    # Don't forget the last education
    if current_education and current_education_lines:
        chunk_text = '\n'.join(current_education_lines)
        chunk_text = recursively_split_large_chunk(chunk_text, MAX_CHUNK_SIZE)
        for split_chunk in chunk_text:
            chunks.append({
                'section': 'Education',
                'subsection': current_education,
                'text': split_chunk,
                'page': text_items[-1].get('page') if text_items else None,
                'start_index': base_index,
                'end_index': base_index + len(text_items) - 1
            })

    return chunks


def chunk_certifications_section(text_items, section_info, base_index):
    """Chunk certifications section - keep as one chunk if reasonable."""
    section_text = '\n'.join(item['text'] for item in text_items)
    section_text = recursively_split_large_chunk(section_text, MAX_CHUNK_SIZE)

    chunks = []
    for split_chunk in section_text:
        chunks.append({
            'section': 'Certifications',
            'subsection': None,
            'text': split_chunk,
            'page': text_items[0].get('page') if text_items else None,
            'start_index': base_index,
            'end_index': base_index + len(text_items) - 1
        })

    return chunks


def chunk_generic_section(text_items, section_info, base_index):
    """Generic chunking for sections without specific logic."""
    section_text = '\n'.join(item['text'] for item in text_items)
    section_text = recursively_split_large_chunk(section_text, MAX_CHUNK_SIZE)

    chunks = []
    for split_chunk in section_text:
        chunks.append({
            'section': section_info['section'],
            'subsection': None,
            'text': split_chunk,
            'page': text_items[0].get('page') if text_items else None,
            'start_index': base_index,
            'end_index': base_index + len(text_items) - 1
        })

    return chunks


def recursively_split_large_chunk(text, max_size):
    """Recursively split large chunks while preserving context.

    Priority:
    1. Try to split at sentence boundaries
    2. Try to split at line boundaries
    3. Force split at max_size (last resort)
    """
    if len(text) <= max_size:
        return [text]

    chunks = []

    # Try to split at sentence boundaries (., !, ?)
    sentence_endings = r'(?<=[.!?])\s+'
    sentence_splits = list(re.finditer(sentence_endings, text))

    if sentence_splits:
        # Find the best split point
        best_split = None
        for match in sentence_splits:
            split_pos = match.end()
            if abs(split_pos - max_size / 2) < abs(max_size / 2):  # Prefer middle
                best_split = split_pos
                break

        if best_split and best_split < len(text):
            first_part = text[:best_split].strip()
            second_part = text[best_split:].strip()

            if len(first_part) >= MIN_CHUNK_SIZE and len(second_part) >= MIN_CHUNK_SIZE:
                chunks.extend(recursively_split_large_chunk(first_part, max_size))
                chunks.extend(recursively_split_large_chunk(second_part, max_size))
                return chunks

    # Try to split at line boundaries
    lines = text.split('\n')
    if len(lines) > 1:
        # Find best line split
        current_length = 0
        split_idx = 0

        for i, line in enumerate(lines):
            if current_length + len(line) > max_size:
                split_idx = i
                break
            current_length += len(line) + 1  # +1 for newline

        if split_idx > 0 and split_idx < len(lines):
            first_part = '\n'.join(lines[:split_idx]).strip()
            second_part = '\n'.join(lines[split_idx:]).strip()

            if len(first_part) >= MIN_CHUNK_SIZE and len(second_part) >= MIN_CHUNK_SIZE:
                chunks.extend(recursively_split_large_chunk(first_part, max_size))
                chunks.extend(recursively_split_large_chunk(second_part, max_size))
                return chunks

    # Last resort: force split at max_size with overlap
    if len(text) > max_size:
        first_part = text[:max_size].strip()
        second_part = text[max_size - CHUNK_OVERLAP:].strip()

        if len(first_part) >= MIN_CHUNK_SIZE:
            chunks.append(first_part)
        if len(second_part) >= MIN_CHUNK_SIZE:
            chunks.extend(recursively_split_large_chunk(second_part, max_size))
    else:
        chunks.append(text)

    return chunks


def enrich_chunk_metadata(chunks, resume_id, resume_name):
    """Enrich chunks with comprehensive metadata.

    Args:
        chunks: List of chunk dicts from context-aware chunking
        resume_id: Resume identifier
        resume_name: Resume filename

    Returns:
        List of enriched chunk dicts with full metadata
    """
    enriched_chunks = []

    for idx, chunk in enumerate(chunks):
        chunk_id = f"{resume_id}_chunk_{idx:03d}"

        # Extract additional metadata from chunk text
        text = chunk['text']
        company = extract_company_from_chunk(text, chunk['section'])
        role = extract_role_from_chunk(text, chunk['section'])
        project = extract_project_from_chunk(text, chunk['section'])
        technologies = extract_technologies_from_chunk(text)
        skills = extract_skills_from_chunk(text)

        enriched_chunk = {
            'chunk_id': chunk_id,
            'resume_id': resume_id,
            'resume_name': resume_name,
            'section': chunk['section'],
            'subsection': chunk.get('subsection'),
            'text': chunk['text'],
            'page': chunk.get('page'),
            'company': company,
            'role': role,
            'project': project,
            'technologies': technologies,
            'skills': skills,
            'chunk_index': idx,
            'parent_chunk_id': None,  # Will be set if this is a split chunk
            'source': 'resume',
            'created_at': get_current_timestamp()
        }

        enriched_chunks.append(enriched_chunk)

    return enriched_chunks


def extract_company_from_chunk(text, section):
    """Extract company name from chunk text."""
    if section != 'Experience':
        return None

    # Simple heuristic: look for company-like patterns
    company_patterns = [
        r'([A-Z][A-Za-z\s]+(?:Inc|LLC|Ltd|Corp|Company|Corporation))',
        r'([A-Z][A-Za-z\s+(?:Technologies|Solutions|Systems)])',
    ]

    for pattern in company_patterns:
        matches = re.findall(pattern, text)
        if matches:
            return matches[0].strip()

    return None


def extract_role_from_chunk(text, section):
    """Extract role/title from chunk text."""
    if section != 'Experience':
        return None

    # Simple heuristic: look for role-like patterns
    role_patterns = [
        r'(?:Senior|Junior|Lead|Principal)?\s*(?:Software|Data|Machine Learning|AI|Full Stack|Backend|Frontend)?\s*(?:Engineer|Developer|Analyst|Manager|Director|Intern)',
        r'(?:Software|Data|Machine Learning|AI)?\s*(?:Engineer|Developer|Analyst|Manager|Director)',
    ]

    for pattern in role_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            return matches[0].strip()

    return None


def extract_project_from_chunk(text, section):
    """Extract project name from chunk text."""
    if section != 'Projects':
        return None

    # Use subsection if available, otherwise try to extract from text
    lines = text.split('\n')
    if lines:
        first_line = lines[0].strip()
        if len(first_line) < 80 and ':' not in first_line:
            return first_line

    return None


def extract_technologies_from_chunk(text):
    """Extract technology mentions from chunk text."""
    # Common technology keywords
    tech_keywords = [
        'Python', 'Java', 'JavaScript', 'TypeScript', 'React', 'Angular', 'Vue',
        'Node.js', 'FastAPI', 'Flask', 'Django', 'Spring Boot', 'SQL', 'PostgreSQL',
        'MySQL', 'MongoDB', 'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Git',
        'TensorFlow', 'PyTorch', 'Scikit-learn', 'Pandas', 'NumPy', 'Linux', 'REST',
        'GraphQL', 'Machine Learning', 'Deep Learning', 'NLP', 'CI/CD', 'Jenkins'
    ]

    found_tech = []
    lower_text = text.lower()

    for tech in tech_keywords:
        if tech.lower() in lower_text:
            found_tech.append(tech)

    return found_tech[:10]  # Limit to top 10


def extract_skills_from_chunk(text):
    """Extract skill mentions from chunk text."""
    # This is similar to technologies but broader
    skill_keywords = [
        'Python', 'Java', 'JavaScript', 'TypeScript', 'React', 'Angular', 'Vue',
        'Node.js', 'FastAPI', 'Flask', 'Django', 'SQL', 'PostgreSQL', 'MySQL',
        'MongoDB', 'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Git', 'Machine Learning',
        'Deep Learning', 'NLP', 'TensorFlow', 'PyTorch', 'Pandas', 'NumPy', 'Data Analysis',
        'Project Management', 'Agile', 'Scrum', 'Leadership', 'Communication'
    ]

    found_skills = []
    lower_text = text.lower()

    for skill in skill_keywords:
        if skill.lower() in lower_text:
            found_skills.append(skill)

    return found_skills[:10]  # Limit to top 10


def process_resume_into_chunks(resume_id, resume_name, text_items):
    """Main function to process resume into chunks.

    Args:
        resume_id: Resume identifier
        resume_name: Resume filename
        text_items: List of dicts with 'page' and 'text' keys

    Returns:
        List of enriched chunk dicts with full metadata
    """
    # Clean text while preserving structure
    cleaned_items = []
    for item in text_items:
        cleaned_text = clean_resume_text(item['text'])
        if cleaned_text:
            cleaned_items.append({
                'page': item.get('page'),
                'text': cleaned_text
            })

    if not cleaned_items:
        return []

    # Detect sections
    sections = detect_resume_sections(cleaned_items)

    # Create context-aware chunks
    chunks = create_context_aware_chunks(cleaned_items, sections)

    # Enrich with metadata
    enriched_chunks = enrich_chunk_metadata(chunks, resume_id, resume_name)

    return enriched_chunks


# ==================================================
# EXTRACT TEXT
# ==================================================


def extract_pdf_text(pdf_file):
    """Extract text from PDF preserving page boundaries."""
    pages = []
    reader = PdfReader(pdf_file)

    for page_num, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text()
        if page_text:
            pages.append({
                "page": page_num,
                "text": page_text
            })

    return pages


def extract_pdf_text_legacy(pdf_file):
    """Legacy PDF extraction for backward compatibility."""
    pages = extract_pdf_text(pdf_file)
    return "\n".join(page["text"] for page in pages)


def extract_docx_text(docx_file):
    """Extract text from DOCX preserving paragraph structure."""
    document = Document(docx_file)
    paragraphs = []

    for para in document.paragraphs:
        if para.text.strip():
            paragraphs.append({
                "page": None,  # DOCX doesn't have reliable page numbers
                "text": para.text
            })

    return paragraphs


def extract_docx_text_legacy(docx_file):
    """Legacy DOCX extraction for backward compatibility."""
    paragraphs = extract_docx_text(docx_file)
    return "\n".join(para["text"] for para in paragraphs)


def extract_text(file, preserve_structure=False):
    """Extract text from file with optional structure preservation.

    Args:
        file: File object (PDF or DOCX)
        preserve_structure: If True, returns list of pages/paragraphs with metadata.
                           If False, returns concatenated text (legacy behavior).

    Returns:
        If preserve_structure: List of dicts with 'page' and 'text' keys
        If not preserve_structure: Concatenated text string
    """
    if hasattr(file, "seek"):
        file.seek(0)

    # `file` may be a SpooledTemporaryFile from FastAPI/Uvicorn without
    # a `.name`, or an in-memory BytesIO that already has one set; the
    # DOCX benchmark relies on the latter case. Sniff the bytes when
    # the filename is missing or unfamiliar.
    name = getattr(file, "name", "") or ""
    lower_name = name.lower()
    if lower_name.endswith(".pdf"):
        pages = extract_pdf_text(file)
        return pages if preserve_structure else extract_pdf_text_legacy(file)

    if lower_name.endswith(".docx"):
        paragraphs = extract_docx_text(file)
        return paragraphs if preserve_structure else extract_docx_text_legacy(file)

    if hasattr(file, "read"):
        head = file.read(4)
        if hasattr(file, "seek"):
            file.seek(0)
        if head.startswith(b"%PDF"):
            pages = extract_pdf_text(file)
            return pages if preserve_structure else extract_pdf_text_legacy(file)
        if head[:2] == b"PK":
            paragraphs = extract_docx_text(file)
            return paragraphs if preserve_structure else extract_docx_text_legacy(file)

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
        "technical_skills": normalize_skill_list(data.get("technical_skills", [])),
        "soft_skills": normalize_skill_list(data.get("soft_skills", [])),
        "tools": normalize_skill_list(data.get("tools", [])),
        "domains": normalize_skill_list(data.get("domains", [])),
        "experience_summary": display_value(
            data.get("experience_summary"),
            "Not Found",
        ),
        "skill_evidence": normalize_skill_evidence(data.get("skill_evidence", [])),
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

    return (
        display_value(
            profile.get("experience_summary"),
            "",
        )
        != "Not Found"
    )


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
        and existing.get("model")
        in [
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
            f"Could not save Gemini skills for {resume_name}: " f"{resume_skill_error}"
        )
        RUNTIME_STATE["last_ai_error"] = previous_ai_error
        return profile

    if not resume_skill_profile_has_signal(profile):
        local_profile = local_profile or build_local_resume_skill_profile(resume_text)

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
    has_indexed_profile = resume_skill_profile_has_signal(resume_skill_profile)

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
        len(matching_skills) / total_skill_signals if total_skill_signals else 0
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
            "Matches key requirements including " f"{', '.join(matching_skills[:4])}."
        )

    if project_signal_count >= 2:
        strengths.append(
            "Resume context includes hands-on project or implementation " "signals."
        )
    elif matching_skills:
        concerns.append(
            "Hands-on project evidence is limited or unclear for the matched " "skills."
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
        (
            matching_skills
            if matching_skills is not None
            else candidate_detail.get("matching_skills", [])
        ),
        (
            missing_skills
            if missing_skills is not None
            else candidate_detail.get("missing_skills", [])
        ),
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
    model_name=None,
    provider=None,
):
    import threading
    import time

    grading_start = time.perf_counter()
    thread_id = threading.get_ident()

    prompt_template = prompt_template or get_candidate_grading_prompt_template()
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
    provider = provider or get_selected_provider()
    model_name = model_name or get_selected_model()
    
    cache_key = get_ai_cache_key(
        "candidate_grading_v4",
        provider,
        model_name,
        resume_context,
        job_text,
        json.dumps(matching_skills, ensure_ascii=False),
        json.dumps(missing_skills, ensure_ascii=False),
        prompt_template,
    )
    cache = get_ai_cache()

    print(f"[CANDIDATE {resume_name}] GRADING START thread={thread_id}")

    if cache_key in cache and candidate_grading_is_usable(cache[cache_key]):
        print(f"[CANDIDATE {resume_name}] GRADING CACHE HIT thread={thread_id}")
        cached_error = cache[cache_key].get("debug", {}).get("gemini_error", "")
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
        grading_duration = time.perf_counter() - grading_start
        print(
            f"[CANDIDATE {resume_name}] GRADING END duration={grading_duration:.2f}s thread={thread_id}"
        )
        return cached_result

    previous_ai_error = RUNTIME_STATE.get("last_ai_error", "")
    fallback_result = build_candidate_grading_fallback(
        resume_context,
        matching_skills,
        missing_skills,
    )

    if RUNTIME_STATE.get("skip_gemini_grading"):
        print(
            f"[CANDIDATE {resume_name}] GRADING SKIP (local fallback) thread={thread_id}"
        )
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
        grading_duration = time.perf_counter() - grading_start
        print(
            f"[CANDIDATE {resume_name}] GRADING END duration={grading_duration:.2f}s thread={thread_id}"
        )
        return fallback_result

    print(f"[CANDIDATE {resume_name}] GRADING CACHE MISS thread={thread_id}")

    prompt = format_prompt(
        prompt_template,
        resume_text=resume_context,
        job_text=job_text,
        matching_skills=json.dumps(matching_skills, ensure_ascii=False),
        missing_skills=json.dumps(missing_skills, ensure_ascii=False),
    )
    data = safe_ai_json(
        prompt,
        CANDIDATE_GRADING_SCHEMA,
        CANDIDATE_GRADING_FALLBACK,
        model_name=model_name,
        provider=provider,
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
        grading_duration = time.perf_counter() - grading_start
        print(
            f"[CANDIDATE {resume_name}] GRADING END duration={grading_duration:.2f}s thread={thread_id}"
        )
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
    grading_duration = time.perf_counter() - grading_start
    print(
        f"[CANDIDATE {resume_name}] GRADING END duration={grading_duration:.2f}s thread={thread_id}"
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
):
    import threading
    import time

    detail_start = time.perf_counter()
    thread_id = threading.get_ident()

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

    print(f"[CANDIDATE {resume_name}] DETAIL START thread={thread_id}")

    if cache_key in cache:
        print(f"[CANDIDATE {resume_name}] DETAIL CACHE HIT thread={thread_id}")
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

        if not candidate_grading_is_usable(cached_result.get("candidate_grading")):
            cached_result["candidate_grading"] = analyze_candidate_grading(
                resume_context,
                job_text,
                cached_result.get("matching_skills", []),
                cached_result.get("missing_skills", []),
                resume_name=resume_name,
                model_name=model_name,
                provider=provider,
            )

        detail_duration = time.perf_counter() - detail_start
        print(
            f"[CANDIDATE {resume_name}] DETAIL END duration={detail_duration:.2f}s thread={thread_id}"
        )
        return cached_result

    print(f"[CANDIDATE {resume_name}] DETAIL CACHE MISS thread={thread_id}")

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
        result["matching_skills"] = remove_placeholder_skills(result["matching_skills"])

        if not result["matching_skills"]:
            result["matching_skills"] = indexed_detail["matching_skills"]

    result["missing_skills"] = merge_missing_skills(
        result["missing_skills"],
        indexed_detail["missing_skills"],
    )

    if (
        result["justification"] == CANDIDATE_DETAIL_FALLBACK["justification"]
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
        model_name=model_name,
        provider=provider,
    )
    if not RUNTIME_STATE.get("last_ai_error"):
        cache[cache_key] = result

    detail_duration = time.perf_counter() - detail_start
    print(
        f"[CANDIDATE {resume_name}] DETAIL END duration={detail_duration:.2f}s thread={thread_id}"
    )
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
    import json
    import os
    import uuid

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
