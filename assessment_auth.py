import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import jwt
from fastapi import HTTPException, Request

JWT_ALGORITHM = "HS256"
ASSESSMENT_TOKEN_TYPE = "assessment"
ASSESSMENT_TOKEN_TTL_SECONDS = 60 * 60 * 24
ASSESSMENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
USER_STORE_PATH = Path(__file__).resolve().parent / "backend" / "data" / "users.json"


def _jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="Authentication is not configured.")
    return secret


def _get_bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Authentication required.")
    return token.strip()


def validate_identifier(value: str, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not ASSESSMENT_ID_PATTERN.fullmatch(normalized):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}.")
    return normalized


def decode_access_token(request: Request) -> Dict[str, Any]:
    token = _get_bearer_token(request)
    try:
        payload = jwt.decode(
            token,
            _jwt_secret(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=401, detail="Invalid or expired session."
        ) from exc

    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("sub"), str)
        or not payload["sub"].strip()
    ):
        raise HTTPException(status_code=401, detail="Invalid session.")
    return payload


def _is_recruiter_user(subject: str) -> bool:
    try:
        records = USER_STORE_PATH.read_text(encoding="utf-8")
        users = json.loads(records)
    except (OSError, UnicodeError, ValueError, TypeError):
        return False

    if not isinstance(users, list):
        return False

    for user in users:
        if not isinstance(user, dict):
            continue
        user_id = user.get("_id", user.get("id"))
        if str(user_id) == subject and user.get("role") == "recruiter":
            return True
    return False


def require_recruiter(request: Request) -> Dict[str, Any]:
    payload = decode_access_token(request)
    if payload.get("token_type") == ASSESSMENT_TOKEN_TYPE:
        raise HTTPException(status_code=403, detail="Recruiter access required.")
    if not _is_recruiter_user(payload["sub"]):
        raise HTTPException(status_code=403, detail="Recruiter access required.")
    return payload


def require_assessment_access(
    request: Request,
    assessment_id: str,
    candidate_id: str,
) -> Dict[str, Any]:
    payload = decode_access_token(request)
    if payload.get("token_type") != ASSESSMENT_TOKEN_TYPE:
        raise HTTPException(status_code=403, detail="Assessment access token required.")
    if payload.get("assessment_id") != assessment_id:
        raise HTTPException(status_code=403, detail="Assessment access denied.")
    if payload.get("candidate_id") != candidate_id:
        raise HTTPException(status_code=403, detail="Candidate access denied.")
    return payload


def issue_assessment_token(
    recruiter_id: str,
    assessment_id: str,
    candidate_id: str,
) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": recruiter_id,
            "token_type": ASSESSMENT_TOKEN_TYPE,
            "assessment_id": assessment_id,
            "candidate_id": candidate_id,
            "iat": now,
            "exp": now + timedelta(seconds=ASSESSMENT_TOKEN_TTL_SECONDS),
        },
        _jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )
