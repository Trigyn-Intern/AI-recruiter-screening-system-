import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from fastapi import HTTPException
from starlette.requests import Request

import assessment_auth


def make_request(monkeypatch, payload, secret="test-secret"):
    monkeypatch.setenv("JWT_SECRET", secret)
    token = jwt.encode(
        {**payload, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        secret,
        algorithm="HS256",
    )
    return Request({
        "type": "http",
        "headers": [(b"authorization", f"Bearer {token}".encode())],
    })


def write_users(path: Path, users):
    path.write_text(json.dumps(users), encoding="utf-8")


def test_require_recruiter_accepts_existing_recruiter(tmp_path, monkeypatch):
    user_store = tmp_path / "users.json"
    write_users(user_store, [{"_id": "recruiter-1", "role": "recruiter", "password": "hidden"}])
    monkeypatch.setattr(assessment_auth, "USER_STORE_PATH", user_store)

    request = make_request(monkeypatch, {"sub": "recruiter-1"})

    assert assessment_auth.require_recruiter(request)["sub"] == "recruiter-1"


@pytest.mark.parametrize(
    "users, payload, expected_status",
    [
        ([{"_id": "manager-1", "role": "manager"}], {"sub": "manager-1"}, 403),
        ([{"_id": "other", "role": "recruiter"}], {"sub": "missing"}, 403),
        ([{"_id": "recruiter-1", "role": "recruiter"}], {"sub": "recruiter-1", "token_type": "assessment"}, 403),
        ([{"_id": "recruiter-1", "role": "recruiter"}], {"sub": "   "}, 401),
    ],
)
def test_require_recruiter_rejects_non_recruiter_tokens(tmp_path, monkeypatch, users, payload, expected_status):
    user_store = tmp_path / "users.json"
    write_users(user_store, users)
    monkeypatch.setattr(assessment_auth, "USER_STORE_PATH", user_store)
    request = make_request(monkeypatch, payload)

    with pytest.raises(HTTPException) as error:
        assessment_auth.require_recruiter(request)

    assert error.value.status_code == expected_status


def test_require_recruiter_rejects_invalid_jwt(tmp_path, monkeypatch):
    user_store = tmp_path / "users.json"
    write_users(user_store, [{"_id": "recruiter-1", "role": "recruiter"}])
    monkeypatch.setattr(assessment_auth, "USER_STORE_PATH", user_store)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    request = Request({
        "type": "http",
        "headers": [(b"authorization", b"Bearer not-a-jwt")],
    })

    with pytest.raises(HTTPException) as error:
        assessment_auth.require_recruiter(request)

    assert error.value.status_code == 401


@pytest.mark.parametrize("contents", ["not-json", "{}", "null"])
def test_require_recruiter_fails_closed_for_malformed_user_store(tmp_path, monkeypatch, contents):
    user_store = tmp_path / "users.json"
    user_store.write_text(contents, encoding="utf-8")
    monkeypatch.setattr(assessment_auth, "USER_STORE_PATH", user_store)
    request = make_request(monkeypatch, {"sub": "recruiter-1"})

    with pytest.raises(HTTPException) as error:
        assessment_auth.require_recruiter(request)

    assert error.value.status_code == 403


def test_require_recruiter_fails_closed_for_unreadable_user_store(tmp_path, monkeypatch):
    user_store = tmp_path / "users-directory"
    user_store.mkdir()
    monkeypatch.setattr(assessment_auth, "USER_STORE_PATH", user_store)
    request = make_request(monkeypatch, {"sub": "recruiter-1"})

    with pytest.raises(HTTPException) as error:
        assessment_auth.require_recruiter(request)

    assert error.value.status_code == 403