"""Question generation engine and persistence for AI Recruiter Screening System.

This module is responsible for:
1. Validating assessment question schemas (10 MCQs, 5 Short Answer = 15 total).
2. Generating candidate-specific questions based primarily on JD requirements and contextualized by candidate resume/experience.
3. Persisting generated questions locally in vector_store/assessment_questions.json.
4. Exporting validation and generation functions for backend API & frontend consumption.
"""

import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import backend
from backend import (
    OPENAI_ASSESSMENT_MODEL,
    PROJECT_ROOT,
    VECTOR_STORE_DIR,
    get_active_resume_db_records,
    get_shortlists,
    read_json_file,
    safe_ai_json,
    write_json_file,
)

ASSESSMENT_QUESTIONS_PATH = VECTOR_STORE_DIR / "assessment_questions.json"
ASSESSMENT_ATTEMPTS_PATH = VECTOR_STORE_DIR / "assessment_attempts.json"
ASSESSMENT_BEHAVIOR_EVENTS_PATH = VECTOR_STORE_DIR / "assessment_behavior_events.json"
ASSESSMENT_RESULTS_PATH = VECTOR_STORE_DIR / "assessment_results.json"

QUESTION_SCHEMA = {
    "type": "object",
    "required": ["questions"],
    "properties": {
        "questions": {
            "type": "array",
            "minItems": 15,
            "maxItems": 15,
            "items": {
                "type": "object",
                "required": ["id", "question", "type", "skill", "difficulty"],
                "properties": {
                    "id": {"type": "string"},
                    "question": {"type": "string", "minLength": 5},
                    "type": {"type": "string", "enum": ["mcq", "short_answer"]},
                    "skill": {"type": "string", "minLength": 1},
                    "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "correct_answer": {"type": "string"},
                    "explanation": {"type": "string"},
                    "expected_answer": {"type": "string"},
                    "evaluation_points": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            }
        }
    }
}


def validate_question(q: Dict[str, Any]) -> tuple[bool, str]:
    """Validate an individual question dictionary against schema rules."""
    if not isinstance(q, dict):
        return False, "Question must be a dictionary"

    qid = q.get("id")
    if not qid or not isinstance(qid, str):
        return False, "Missing or invalid question id"

    qtext = q.get("question")
    if not qtext or not isinstance(qtext, str) or not qtext.strip():
        return False, f"Question {qid} has empty question text"

    qtype = q.get("type")
    if qtype not in ["mcq", "short_answer"]:
        return False, f"Question {qid} has invalid type: {qtype}"

    skill = q.get("skill")
    if not skill or not isinstance(skill, str) or not skill.strip():
        return False, f"Question {qid} has missing or empty skill"

    diff = q.get("difficulty")
    if diff not in ["easy", "medium", "hard"]:
        return False, f"Question {qid} has invalid difficulty: {diff}"

    if qtype == "mcq":
        options = q.get("options")
        if not isinstance(options, list) or len(options) != 4:
            return False, f"MCQ {qid} must have exactly 4 options"
        if any(not isinstance(opt, str) or not opt.strip() for opt in options):
            return False, f"MCQ {qid} contains empty or invalid option strings"

        correct = q.get("correct_answer")
        if not correct or not isinstance(correct, str) or not correct.strip():
            return False, f"MCQ {qid} missing correct_answer"
        if correct.strip() not in [opt.strip() for opt in options]:
            return False, f"MCQ {qid} correct_answer is not present in options"

    elif qtype == "short_answer":
        exp = q.get("expected_answer")
        if not exp or not isinstance(exp, str) or not exp.strip():
            return False, f"Short answer {qid} missing expected_answer"

        eval_pts = q.get("evaluation_points")
        if not isinstance(eval_pts, list) or len(eval_pts) == 0:
            return False, f"Short answer {qid} must have at least one evaluation point"
        if any(not isinstance(pt, str) or not pt.strip() for pt in eval_pts):
            return False, f"Short answer {qid} contains empty evaluation points"

    return True, "Valid"


def validate_questions_set(questions: List[Dict[str, Any]]) -> tuple[bool, str]:
    """Validate a set of 15 generated questions."""
    if not isinstance(questions, list):
        return False, "Questions payload must be a list"

    if len(questions) != 15:
        return False, f"Expected exactly 15 questions, got {len(questions)}"

    seen_ids = set()
    seen_texts = set()
    mcq_count = 0
    short_count = 0
    skills_found = set()

    for idx, q in enumerate(questions):
        valid, msg = validate_question(q)
        if not valid:
            return False, f"Validation failed at question index {idx}: {msg}"

        qid = q["id"]
        if qid in seen_ids:
            return False, f"Duplicate question id found: {qid}"
        seen_ids.add(qid)

        qnorm = q["question"].strip().lower()
        if qnorm in seen_texts:
            return False, f"Duplicate question text found: {q['question']}"
        seen_texts.add(qnorm)

        if q["type"] == "mcq":
            mcq_count += 1
        elif q["type"] == "short_answer":
            short_count += 1

        skills_found.add(q["skill"].strip().lower())

    if mcq_count != 10:
        return False, f"Expected 10 MCQ questions, got {mcq_count}"

    if short_count != 5:
        return False, f"Expected 5 short answer questions, got {short_count}"

    if len(skills_found) < 2:
        return False, "Questions lack skill coverage diversity (minimum 2 distinct skills required)"

    return True, "Questions set is valid"


def get_all_assessment_questions() -> Dict[str, Any]:
    """Load all persisted assessment questions from storage."""
    return read_json_file(ASSESSMENT_QUESTIONS_PATH, {})


def get_assessment_questions(assessment_id: str, candidate_id: str = None) -> Optional[Dict[str, Any]]:
    """Retrieve persisted questions for a specific assessment ID.

    Lookup order:
    1. Exact key match on assessment_id.
    2. Exact key match on candidate_id (if provided and different from assessment_id).
    3. Scan all records for one whose 'candidate_id' field matches either ID.

    This handles the case where the frontend passes an assessmentId like
    'resumeHash_shortlistId' but questions were stored under the raw resume hash.
    """
    store = get_all_assessment_questions()

    # 1. Direct key lookup
    result = store.get(assessment_id)
    if result and result.get("questions"):
        return result

    # 2. Try candidate_id as key (if provided and different)
    if candidate_id and candidate_id != assessment_id:
        result = store.get(candidate_id)
        if result and result.get("questions"):
            return result

    # 3. Scan records by candidate_id field
    lookup_ids = {assessment_id}
    if candidate_id:
        lookup_ids.add(candidate_id)
    
    # If the assessment_id is a composite key like 'resumeHash_shortlistId', also look for the resumeHash
    if "_" in assessment_id:
        lookup_ids.add(assessment_id.split("_")[0])

    for _key, record in store.items():
        if not isinstance(record, dict):
            continue
        rec_cid = record.get("candidate_id", "")
        rec_aid = record.get("assessment_id", "")
        if rec_cid in lookup_ids or rec_aid in lookup_ids:
            if record.get("questions"):
                return record

    return None


def save_assessment_questions(assessment_id: str, payload: Dict[str, Any]) -> None:
    """Save assessment questions for a specific assessment ID.

    Also stores a reference under candidate_id if it differs from assessment_id,
    so subsequent lookups by either key find the same question set.
    """
    store = get_all_assessment_questions()
    store[assessment_id] = payload

    # Cross-reference: also save under candidate_id key if different
    cid = payload.get("candidate_id", "")
    if cid and cid != assessment_id and cid not in store:
        store[cid] = payload

    write_json_file(ASSESSMENT_QUESTIONS_PATH, store)


def get_all_assessment_attempts() -> Dict[str, Any]:
    """Load all persisted assessment attempts from storage."""
    return read_json_file(ASSESSMENT_ATTEMPTS_PATH, {})


def get_assessment_attempt(assessment_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve persisted attempt for a specific assessment ID."""
    store = get_all_assessment_attempts()
    res = store.get(assessment_id)
    if res:
        return res
    if "_" in assessment_id:
        res = store.get(assessment_id.split("_")[0])
        if res:
            return res
    for _key, record in store.items():
        if isinstance(record, dict):
            if record.get("candidate_id") == assessment_id or record.get("resume_id") == assessment_id or record.get("assessment_id") == assessment_id:
                return record
            if "_" in assessment_id and (record.get("candidate_id") == assessment_id.split("_")[0] or record.get("resume_id") == assessment_id.split("_")[0]):
                return record
    return None


def save_assessment_attempt(assessment_id: str, payload: Dict[str, Any]) -> None:
    """Save assessment attempt for a specific assessment ID."""
    store = get_all_assessment_attempts()
    store[assessment_id] = payload
    cid = payload.get("candidate_id", "") or payload.get("resume_id", "")
    if cid and cid != assessment_id and cid not in store:
        store[cid] = payload
    write_json_file(ASSESSMENT_ATTEMPTS_PATH, store)


def get_all_assessment_results() -> Dict[str, Any]:
    """Load all persisted assessment results from storage."""
    return read_json_file(ASSESSMENT_RESULTS_PATH, {})


def get_assessment_result(assessment_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve persisted result for a specific assessment ID."""
    store = get_all_assessment_results()
    res = store.get(assessment_id)
    if res:
        return res
    if "_" in assessment_id:
        res = store.get(assessment_id.split("_")[0])
        if res:
            return res
    for _key, record in store.items():
        if isinstance(record, dict):
            if record.get("candidate_id") == assessment_id or record.get("assessment_id") == assessment_id:
                return record
    return None


def save_assessment_result(assessment_id: str, payload: Dict[str, Any]) -> None:
    """Save assessment result for a specific assessment ID."""
    store = get_all_assessment_results()
    store[assessment_id] = payload
    write_json_file(ASSESSMENT_RESULTS_PATH, store)


def calculate_behavior_score(events: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Calculate a bounded score from persisted behavior metadata.

    Scored signals are tab switches, tab-away duration, face absence, multiple
    faces, camera errors, and camera permission denial. Gaze, looking-away,
    audio, network, and copy/paste events remain informational only.
    """
    unique_events = []
    seen_events = set()
    for event in events or []:
        if not isinstance(event, dict) or not event.get("type"):
            continue
        event_type = str(event.get("type"))
        event_key = (
            event_type,
            repr(event.get("timestamp")),
            repr(event.get("duration_seconds")),
            repr(event.get("details")),
        )
        if event_key in seen_events:
            continue
        seen_events.add(event_key)
        unique_events.append({**event, "type": event_type})

    def valid_duration(event):
        value = event.get("duration_seconds", 0) or 0
        try:
            value = float(value)
        except (TypeError, ValueError):
            return 0.0
        return value if math.isfinite(value) and 0 <= value <= 14400 else 0.0

    tab_switches = sum(event.get("type") == "tab_hidden" for event in unique_events)
    total_tab_away_seconds = sum(
        valid_duration(event)
        for event in unique_events
        if event.get("type") == "tab_visible"
    )
    face_absent_events = sum(event.get("type") == "face_absent" for event in unique_events)
    multiple_faces_events = sum(
        event.get("type") == "multiple_faces_detected" for event in unique_events
    )
    camera_errors = sum(event.get("type") == "camera_error" for event in unique_events)
    permission_denied = sum(
        event.get("type") == "camera_permission_denied" for event in unique_events
    )

    deductions = tab_switches * 2
    if total_tab_away_seconds > 60:
        deductions += 8
    elif total_tab_away_seconds > 30:
        deductions += 5
    elif total_tab_away_seconds > 10:
        deductions += 2
    deductions += face_absent_events * 3
    deductions += multiple_faces_events * 5
    deductions += camera_errors
    deductions += min(permission_denied, 1) * 2

    return {
        "behavior_score": max(0, min(100, 100 - deductions)),
        "behavior_summary": {
            "tab_switches": tab_switches,
            "total_tab_away_seconds": round(total_tab_away_seconds, 2),
            "face_absent_events": face_absent_events,
            "multiple_faces_events": multiple_faces_events,
            "camera_errors": camera_errors,
            "permission_denied": permission_denied,
        },
    }


def score_assessment_attempt(assessment_id: str) -> Dict[str, Any]:
    """Score the assessment attempt for the given assessment ID.
    
    MCQs are scored strictly based on exact match.
    Short answers use OpenAI for evaluation.
    This function is idempotent.
    """
    # 1. Check if already scored
    existing = get_assessment_result(assessment_id)
    if existing:
        behavior_result = calculate_behavior_score(
            (get_assessment_behavior_events(assessment_id) or {}).get("events", [])
        )
        technical_score = float(existing.get("technical_score", existing.get("total_score", 0)))
        technical_max_score = float(existing.get("technical_max_score", existing.get("max_score", 0)))
        technical_percentage = float(
            existing.get(
                "technical_percentage",
                existing.get("percentage", (technical_score / technical_max_score) * 100
                if technical_max_score else 0),
            )
        )
        updated = dict(existing)
        updated.update({
            "technical_score": technical_score,
            "technical_max_score": technical_max_score,
            "technical_percentage": technical_percentage,
            "behavior_score": behavior_result["behavior_score"],
            "behavior_weight": 20,
            "technical_weight": 80,
            "overall_percentage": round(
                (technical_percentage * 0.80) + (behavior_result["behavior_score"] * 0.20), 2
            ),
            "behavior_summary": behavior_result["behavior_summary"],
        })
        if updated != existing:
            save_assessment_result(assessment_id, updated)
        return updated
        
    # 2. Get questions and attempt
    questions_data = get_assessment_questions(assessment_id)
    attempt_data = get_assessment_attempt(assessment_id)
    
    if not questions_data or "questions" not in questions_data:
        raise ValueError(f"Assessment questions not found for ID: {assessment_id}")
    if not attempt_data or "answers" not in attempt_data:
        raise ValueError(f"Assessment attempt not found for ID: {assessment_id}")
        
    questions = questions_data["questions"]
    answers = attempt_data["answers"]
    
    total_score = 0.0
    max_score = float(len(questions))
    
    skill_scores = {}
    question_results = []
    
    SHORT_ANSWER_SCORING_SCHEMA = {
        "type": "object",
        "required": ["score", "evaluation_points_met", "evaluation_points_missed", "reason"],
        "properties": {
            "score": {"type": "number", "enum": [0, 0.25, 0.5, 0.75, 1]},
            "evaluation_points_met": {"type": "array", "items": {"type": "string"}},
            "evaluation_points_missed": {"type": "array", "items": {"type": "string"}},
            "reason": {"type": "string"}
        }
    }
    
    for idx, q in enumerate(questions):
        q_id = q["id"]
        q_type = q.get("type")
        skill = q.get("skill", "Unknown")
        cand_ans = answers.get(q_id, "")
        
        score = 0.0
        q_result = {
            "question_id": q_id,
            "question_number": idx + 1,
            "question_type": q_type,
            "skill": skill,
            "candidate_answer": cand_ans,
            "max_score": 1.0
        }
        
        if skill not in skill_scores:
            skill_scores[skill] = {"score": 0.0, "max_score": 0.0, "percentage": 0.0}
            
        skill_scores[skill]["max_score"] += 1.0
        
        if q_type == "mcq":
            correct_ans = q.get("correct_answer", "")
            if cand_ans and isinstance(cand_ans, str) and cand_ans.strip().lower() == correct_ans.strip().lower():
                score = 1.0
            q_result["score"] = score
            
        elif q_type == "short_answer":
            if not cand_ans or not str(cand_ans).strip():
                score = 0.0
                q_result["score"] = score
                q_result["evaluation_points_met"] = []
                q_result["evaluation_points_missed"] = q.get("evaluation_points", [])
                q_result["reason"] = "No answer provided."
            else:
                prompt = f'''You are an expert technical evaluator. Evaluate the candidate's short answer against the expected answer and evaluation points.
Question: {q.get("question")}
Expected Answer: {q.get("expected_answer")}
Evaluation Points: {json.dumps(q.get("evaluation_points", []))}

Candidate's Answer: {cand_ans}

Assign a score of 0, 0.25, 0.5, 0.75, or 1 based on how many evaluation points the candidate met and the overall correctness.
Return JSON matching the provided schema.
'''
                ai_eval = safe_ai_json(
                    prompt=prompt,
                    schema=SHORT_ANSWER_SCORING_SCHEMA,
                    fallback=None,
                    model_name=OPENAI_ASSESSMENT_MODEL,
                    provider="OpenAI"
                )
                
                if ai_eval and "score" in ai_eval and ai_eval["score"] in [0, 0.25, 0.5, 0.75, 1]:
                    score = float(ai_eval["score"])
                    q_result["evaluation_points_met"] = ai_eval.get("evaluation_points_met", [])
                    q_result["evaluation_points_missed"] = ai_eval.get("evaluation_points_missed", [])
                    q_result["reason"] = ai_eval.get("reason", "")
                else:
                    score = 0.0
                    q_result["evaluation_points_met"] = []
                    q_result["evaluation_points_missed"] = q.get("evaluation_points", [])
                    q_result["reason"] = "Evaluation failed or returned invalid score."
                
                q_result["score"] = score
        
        total_score += score
        skill_scores[skill]["score"] += score
        question_results.append(q_result)
        
    for s_info in skill_scores.values():
        s_info["percentage"] = round((s_info["score"] / s_info["max_score"]) * 100, 2) if s_info["max_score"] > 0 else 0.0
        
    percentage = round((total_score / max_score) * 100, 2) if max_score > 0 else 0.0
    behavior_result = calculate_behavior_score(
        (get_assessment_behavior_events(assessment_id) or {}).get("events", [])
    )
    overall_percentage = round((percentage * 0.80) + (behavior_result["behavior_score"] * 0.20), 2)
    
    result_payload = {
        "assessment_id": assessment_id,
        "total_score": total_score,
        "max_score": max_score,
        "percentage": percentage,
        "technical_score": total_score,
        "technical_max_score": max_score,
        "technical_percentage": percentage,
        "behavior_score": behavior_result["behavior_score"],
        "behavior_weight": 20,
        "technical_weight": 80,
        "overall_percentage": overall_percentage,
        "behavior_summary": behavior_result["behavior_summary"],
        "skill_scores": [{"skill": k, **v} for k, v in skill_scores.items()],
        "question_results": question_results
    }
    
    save_assessment_result(assessment_id, result_payload)
    return result_payload


def get_all_assessment_behavior_events() -> Dict[str, Any]:
    """Load all persisted assessment behavior events from storage."""
    return read_json_file(ASSESSMENT_BEHAVIOR_EVENTS_PATH, {})


def get_assessment_behavior_events(assessment_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve persisted behavior events for a specific assessment ID."""
    store = get_all_assessment_behavior_events()
    return store.get(assessment_id)


def append_assessment_behavior_events(
    assessment_id: str,
    candidate_id: str,
    new_events: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Append new behavior monitoring events to an assessment ID."""
    store = get_all_assessment_behavior_events()
    record = store.get(assessment_id, {
        "assessment_id": assessment_id,
        "candidate_id": candidate_id,
        "events": []
    })

    if "events" not in record or not isinstance(record["events"], list):
        record["events"] = []

    for evt in new_events:
        if isinstance(evt, dict) and "type" in evt:
            record["events"].append(evt)

    store[assessment_id] = record
    write_json_file(ASSESSMENT_BEHAVIOR_EVENTS_PATH, store)
    return record


def extract_jd_skills(jd_text_or_dict: Any) -> List[str]:
    """Extract key technical skills from JD text or structured JD dict."""
    if isinstance(jd_text_or_dict, dict):
        p_skills = jd_text_or_dict.get("primary_skills") or ""
        s_skills = jd_text_or_dict.get("secondary_skills") or ""
        text = f"{p_skills}, {s_skills}"
        if not text.strip():
            text = str(jd_text_or_dict)
    else:
        text = str(jd_text_or_dict)

    candidates = [
        "Python", "JavaScript", "TypeScript", "React", "Node.js", "FastAPI",
        "SQL", "PostgreSQL", "MongoDB", "Docker", "Kubernetes", "AWS",
        "Machine Learning", "Deep Learning", "NLP", "RAG", "LLMs",
        "System Design", "REST API", "Git", "CI/CD", "Data Structures", "Algorithms"
    ]

    found = []
    for skill in candidates:
        pattern = r"\b" + re.escape(skill) + r"\b"
        if re.search(pattern, text, re.IGNORECASE):
            found.append(skill)

    if not found:
        # Fallback extract comma/space separated capitalized words
        raw_parts = [p.strip() for p in re.split(r"[,;\n]", text) if p.strip()]
        for p in raw_parts:
            if len(p) < 30 and re.match(r"^[A-Za-z0-9+#.\s-]+$", p):
                found.append(p)
            if len(found) >= 6:
                break

    if not found:
        found = ["Software Engineering", "Problem Solving", "System Architecture", "Coding Principles"]

    # Deduplicate preserving order
    seen = set()
    dedup = []
    for s in found:
        low = s.lower()
        if low not in seen:
            seen.add(low)
            dedup.append(s)

    return dedup[:8]


def generate_fallback_questions(
    skills: List[str], candidate_name: str = "Candidate", job_title: str = "Engineer"
) -> List[Dict[str, Any]]:
    """Generate a deterministic fallback set of 15 valid questions if LLM fails or is unavailable."""
    primary_skill = skills[0] if skills else "Software Development"
    secondary_skill = skills[1] if len(skills) > 1 else "System Design"
    third_skill = skills[2] if len(skills) > 2 else "Problem Solving"

    questions = [
        # 10 MCQs
        {
            "id": "q1",
            "question": f"In {primary_skill}, what is the primary advantage of using immutable data structures?",
            "type": "mcq",
            "skill": primary_skill,
            "difficulty": "easy",
            "options": [
                "Improves thread safety and predictable state management",
                "Decreases memory footprint by deleting old references",
                "Allows direct modification of global variables",
                "Disables runtime type checking completely"
            ],
            "correct_answer": "Improves thread safety and predictable state management",
            "explanation": "Immutable data structures prevent unintended side-effects and simplify concurrency."
        },
        {
            "id": "q2",
            "question": f"Which architectural pattern is best suited for decoupling microservices in a {job_title} ecosystem?",
            "type": "mcq",
            "skill": secondary_skill,
            "difficulty": "medium",
            "options": [
                "Event-driven architecture with message brokers",
                "Monolithic shared memory pool",
                "Direct synchronous HTTP calls with no retries",
                "Database triggers mutating remote tables"
            ],
            "correct_answer": "Event-driven architecture with message brokers",
            "explanation": "Event-driven architecture decouples services by allowing asynchronous event publishing."
        },
        {
            "id": "q3",
            "question": f"When optimizing performance in {primary_skill}, what is time complexity of accessing an element by key in a standard Hash Table?",
            "type": "mcq",
            "skill": primary_skill,
            "difficulty": "easy",
            "options": [
                "Average O(1)",
                "Always O(N log N)",
                "O(N^2)",
                "O(log N)"
            ],
            "correct_answer": "Average O(1)",
            "explanation": "Hash tables provide average O(1) time complexity for lookup."
        },
        {
            "id": "q4",
            "question": f"What is the main purpose of connection pooling when interacting with databases in {secondary_skill}?",
            "type": "mcq",
            "skill": secondary_skill,
            "difficulty": "medium",
            "options": [
                "Reuse existing database connections to reduce creation overhead",
                "Encrypt all data stored on disk automatically",
                "Bypass SQL syntax validation",
                "Automatically generate database indexes"
            ],
            "correct_answer": "Reuse existing database connections to reduce creation overhead",
            "explanation": "Connection pooling avoids the overhead of creating and tearing down connections repeatedly."
        },
        {
            "id": "q5",
            "question": f"In modern API design for {job_title} applications, what does idempotency mean?",
            "type": "mcq",
            "skill": third_skill,
            "difficulty": "medium",
            "options": [
                "Making identical requests multiple times has the same side effect as a single request",
                "An endpoint returns response in less than 10 milliseconds",
                "Requests must always use GET method without query parameters",
                "Data is cached permanently in client browser storage"
            ],
            "correct_answer": "Making identical requests multiple times has the same side effect as a single request",
            "explanation": "Idempotent operations can be applied multiple times without altering the result beyond the initial application."
        },
        {
            "id": "q6",
            "question": f"Which security vulnerability involves executing arbitrary commands injected into database queries?",
            "type": "mcq",
            "skill": third_skill,
            "difficulty": "easy",
            "options": [
                "SQL Injection (SQLi)",
                "Cross-Site Scripting (XSS)",
                "Cross-Site Request Forgery (CSRF)",
                "Buffer Overflow"
            ],
            "correct_answer": "SQL Injection (SQLi)",
            "explanation": "SQL Injection occurs when untrusted input is concatenated into database commands."
        },
        {
            "id": "q7",
            "question": f"When handling concurrency in {primary_skill}, what is a deadlock?",
            "type": "mcq",
            "skill": primary_skill,
            "difficulty": "hard",
            "options": [
                "A situation where two or more threads are blocked forever, waiting for each other",
                "A memory leak caused by uncollected cyclic references",
                "An uncaught exception thrown during garbage collection",
                "A network timeout occurring during high load"
            ],
            "correct_answer": "A situation where two or more threads are blocked forever, waiting for each other",
            "explanation": "Deadlocks occur when threads hold locks needed by each other in a circular chain."
        },
        {
            "id": "q8",
            "question": f"What is the primary role of indexing in database query optimization?",
            "type": "mcq",
            "skill": secondary_skill,
            "difficulty": "medium",
            "options": [
                "Speeds up data retrieval operations at the cost of additional storage and write speed",
                "Compresses tables on disk to reduce cloud storage cost",
                "Ensures foreign keys cannot be deleted",
                "Converts SQL queries into C++ bytecode"
            ],
            "correct_answer": "Speeds up data retrieval operations at the cost of additional storage and write speed",
            "explanation": "Indexes create data structures to quickly locate table rows without scanning every row."
        },
        {
            "id": "q9",
            "question": f"In distributed systems, according to CAP theorem, what does 'Consistency' guarantee?",
            "type": "mcq",
            "skill": third_skill,
            "difficulty": "hard",
            "options": [
                "Every read receives the most recent write or an error",
                "Every request receives a non-error response without guarantee of latest write",
                "System operates continuously despite arbitrary node failure",
                "All transactions complete in strictly under 100 milliseconds"
            ],
            "correct_answer": "Every read receives the most recent write or an error",
            "explanation": "Linearizability/Consistency guarantees all nodes see the same data at the same time."
        },
        {
            "id": "q10",
            "question": f"What design pattern allows an object to alter its behavior when its internal state changes?",
            "type": "mcq",
            "skill": primary_skill,
            "difficulty": "medium",
            "options": [
                "State Pattern",
                "Singleton Pattern",
                "Factory Method Pattern",
                "Adapter Pattern"
            ],
            "correct_answer": "State Pattern",
            "explanation": "The State pattern allows an object to change its behavior dynamically based on state."
        },
        # 5 Short Answers
        {
            "id": "q11",
            "question": f"Describe how you would design a rate limiter in {secondary_skill} to protect an API from traffic spikes. Mention key algorithms or data structures.",
            "type": "short_answer",
            "skill": secondary_skill,
            "difficulty": "hard",
            "expected_answer": "Explain Token Bucket or Leaky Bucket algorithm using Redis/in-memory store with sliding window counter.",
            "evaluation_points": [
                "Mentions Token Bucket, Leaky Bucket, or Sliding Window algorithm",
                "Discusses centralized storage like Redis for distributed API instances",
                "Addresses handling edge cases like concurrency and rate limit headers (HTTP 429)"
            ]
        },
        {
            "id": "q12",
            "question": f"Explain the difference between synchronous and asynchronous execution in {primary_skill} and when to use each.",
            "type": "short_answer",
            "skill": primary_skill,
            "difficulty": "medium",
            "expected_answer": "Synchronous blocks execution until task finishes; asynchronous releases control for non-blocking I/O operations.",
            "evaluation_points": [
                "Clear explanation of blocking vs non-blocking behavior",
                "Identifies I/O bound tasks (network, disk) as prime candidates for async execution",
                "Understands CPU bound limitations and worker threads/processes"
            ]
        },
        {
            "id": "q13",
            "question": f"How do you ensure data integrity during database transactions in a {job_title} project?",
            "type": "short_answer",
            "skill": third_skill,
            "difficulty": "medium",
            "expected_answer": "Use ACID compliant transactions, proper isolation levels, and explicit error rollback handling.",
            "evaluation_points": [
                "Mentions ACID properties (Atomicity, Consistency, Isolation, Durability)",
                "Explains transaction rollbacks on failure",
                "Discusses locking mechanisms or optimistic/pessimistic concurrency control"
            ]
        },
        {
            "id": "q14",
            "question": f"Walk through your approach to debugging a memory leak or sudden latency spike in a production environment using {primary_skill}.",
            "type": "short_answer",
            "skill": primary_skill,
            "difficulty": "hard",
            "expected_answer": "Check APM metrics, analyze heap dumps/profiler traces, inspect log correlations, and isolate leak source.",
            "evaluation_points": [
                "Structured debugging methodology starting with metrics/alerts",
                "Mentions profiling tools, heap analysis, or log aggregation",
                "Proposes verification through load testing or canary deployment"
            ]
        },
        {
            "id": "q15",
            "question": f"Explain key considerations for API versioning and backward compatibility when refactoring core endpoints.",
            "type": "short_answer",
            "skill": secondary_skill,
            "difficulty": "medium",
            "expected_answer": "Use URI/header versioning, avoid breaking field deletions, deprecate gracefully, and maintain documentation.",
            "evaluation_points": [
                "Suggests explicit versioning strategies (URI path vs HTTP headers)",
                "Emphasizes non-breaking changes (additive schema updates)",
                "Mentions deprecation timelines and backward compatibility layers"
            ]
        }
    ]

    return questions


def generate_candidate_assessment(
    assessment_id: str,
    candidate_id: str,
    job_description: Any,
    candidate_resume: Any = None,
    job_role: str = "Engineer"
) -> Dict[str, Any]:
    """Generate or retrieve candidate-specific 15-question assessment.

    Tied strictly to assessment_id, candidate_id, JD, and resume_id.
    """
    # 1. Check if already generated and persisted (search by both assessment_id and candidate_id)
    existing = get_assessment_questions(assessment_id, candidate_id=candidate_id)
    if existing and existing.get("questions") and len(existing.get("questions", [])) == 15:
        return existing

    # 2. Extract JD text & candidate experience
    jd_str = ""
    if isinstance(job_description, dict):
        title = job_description.get("job_title") or job_description.get("title") or job_role
        p_skills = job_description.get("primary_skills") or ""
        s_skills = job_description.get("secondary_skills") or ""
        exp = job_description.get("experience") or ""
        jd_str = f"Role: {title}\nPrimary Skills: {p_skills}\nSecondary Skills: {s_skills}\nExperience: {exp}"
    else:
        jd_str = str(job_description or f"Job Role: {job_role}")

    extracted_skills = extract_jd_skills(job_description or jd_str)

    resume_summary = ""
    candidate_name = "Candidate"
    if isinstance(candidate_resume, dict):
        candidate_name = candidate_resume.get("candidate_name") or candidate_name
        skills_data = candidate_resume.get("skills", {})
        tech = ", ".join(skills_data.get("technical_skills", []))
        exp_sum = skills_data.get("experience_summary", "")
        resume_summary = f"Candidate Name: {candidate_name}\nTechnical Skills: {tech}\nExperience Summary: {exp_sum}"

    prompt = f"""
You are an expert AI Technical Recruiter and Assessment Designer.

Task: Generate an assessment containing EXACTLY 15 questions for the candidate based on the Job Description and candidate profile below.

JOB DESCRIPTION:
{jd_str}

CANDIDATE PROFILE CONTEXT (Use for subtle personalization/contextualization, but the JD is primary):
{resume_summary or "Candidate ID: " + str(candidate_id)}

REQUIREMENTS:
1. Total questions: EXACTLY 15 questions.
2. Question Types:
   - EXACTLY 10 MCQs ('type': 'mcq')
   - EXACTLY 5 Short Answer ('type': 'short_answer')
3. Skill Distribution:
   - Distribute questions across the core technical skills from the JD ({", ".join(extracted_skills)}).
4. Question Format:
   - For MCQs: Include 'options' (array of 4 options), 'correct_answer' (must match one option), 'explanation'.
   - For Short Answer: Include 'expected_answer', 'evaluation_points' (array of criteria points).
5. Difficulty: A mix of easy, medium, and hard.
6. Skill Tag Accuracy:
   - The 'skill' field MUST correspond to the actual topic being tested by the question.
   - For example, a question about REST API versioning should NOT have skill = "SQL".
   - A question about rate limiting should NOT have skill = "SQL" unless it genuinely tests SQL.
   - Only use skills from the JD skill list above.

Return ONLY valid JSON matching this structure:
{{
  "questions": [
    {{
      "id": "q1",
      "question": "Clear, precise technical question text?",
      "type": "mcq",
      "skill": "Python",
      "difficulty": "medium",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "Option A",
      "explanation": "Detailed rationale"
    }},
    ...
  ]
}}
"""

    fallback_questions = generate_fallback_questions(
        extracted_skills, candidate_name=candidate_name, job_title=job_role
    )

    fallback_payload = {
        "assessment_id": assessment_id,
        "candidate_id": candidate_id,
        "job_role": job_role,
        "extracted_skills": extracted_skills,
        "questions": fallback_questions,
        "generation_source": "fallback"
    }

    try:
        data = safe_ai_json(
            prompt=prompt,
            schema=QUESTION_SCHEMA,
            fallback=None,
            model_name=OPENAI_ASSESSMENT_MODEL,
            provider="OpenAI"
        )

        if data and isinstance(data, dict) and "questions" in data:
            questions = data["questions"]
            valid, msg = validate_questions_set(questions)
            if valid:
                payload = {
                    "assessment_id": assessment_id,
                    "candidate_id": candidate_id,
                    "job_role": job_role,
                    "extracted_skills": extracted_skills,
                    "questions": questions,
                    "generation_source": "llm"
                }
                save_assessment_questions(assessment_id, payload)
                return payload
            else:
                print(f"[QUESTION_GEN] LLM generated invalid question set: {msg}. Using validated fallback.")
    except Exception as exc:
        print(f"[QUESTION_GEN] LLM call failed with exception: {exc}. Using validated fallback.")

    # Save and return fallback if LLM failed or failed validation
    save_assessment_questions(assessment_id, fallback_payload)
    return fallback_payload
