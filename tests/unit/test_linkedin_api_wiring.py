from api import restore_candidate_profile_fields
from backend import LINKEDIN_VERIFICATION_FALLBACK


def make_profile():
    return {
        "skills": {
            "technical_skills": ["Python"],
            "skill_evidence": [
                {
                    "skill": "Python",
                    "evidence": "Built Python services.",
                    "chunk_id": "resume_chunk_001",
                }
            ],
            "contact_info": {
                "email": "candidate@example.com",
                "phone": "+91 98765 43210",
                "linkedin": "linkedin.com/in/candidate",
                "github": "github.com/candidate",
            },
        }
    }


def test_candidate_detail_wires_existing_linkedin_profile_to_verifier(monkeypatch):
    linkedin_profile = {"name": "Candidate Name", "email": "candidate@example.com"}
    github_verification = {"overall_status": "corroborated"}
    linkedin_verification = {"overall_status": "CORROBORATED", "findings": []}
    captured = {}
    captapi_calls = []

    def fetch_profile(url):
        captapi_calls.append(url)
        return linkedin_profile

    def verify(resume_profile, profile, jd_structured):
        captured["resume"] = resume_profile
        captured["linkedin"] = profile
        captured["jd"] = jd_structured
        return linkedin_verification

    monkeypatch.setattr("api.fetch_captapi_linkedin_profile", fetch_profile)
    monkeypatch.setattr("api.get_github_evidence", lambda url: {"status": "available"})
    monkeypatch.setattr(
        "api.verify_github_evidence_against_resume",
        lambda resume, evidence: github_verification,
    )
    monkeypatch.setattr("api.verify_linkedin_evidence_against_resume", verify)

    jd_structured = {"primary_skills": ["Python"]}
    restored = restore_candidate_profile_fields(make_profile(), jd_structured)

    assert restored["linkedin_verification"] is linkedin_verification
    assert captured["resume"] is not None
    assert captured["resume"]["contact_info"]["linkedin"] == "linkedin.com/in/candidate"
    assert captured["linkedin"] is linkedin_profile
    assert captured["jd"] == jd_structured
    assert captapi_calls == ["linkedin.com/in/candidate"]
    assert restored["linkedin_profile"] is linkedin_profile
    assert restored["contact_info"]["email"] == "candidate@example.com"
    assert restored["github_verification"] is github_verification


def test_verification_failure_preserves_existing_candidate_detail_fields(monkeypatch):
    linkedin_profile = {"name": "Candidate Name"}
    existing_detail = {
        "match_score": 87.5,
        "candidate_grading": {"grade": "A"},
        "selection": "Selected",
        "linkedin_profile": linkedin_profile,
        "contact_info": {"email": "candidate@example.com"},
        "github_verification": {"overall_status": "corroborated"},
    }

    monkeypatch.setattr("api.fetch_captapi_linkedin_profile", lambda url: linkedin_profile)
    monkeypatch.setattr("api.get_github_evidence", lambda url: {"status": "available"})
    monkeypatch.setattr(
        "api.verify_github_evidence_against_resume",
        lambda resume, evidence: existing_detail["github_verification"],
    )

    def fail_verification(resume, profile, jd_structured):
        raise RuntimeError("verification unavailable")

    monkeypatch.setattr("api.verify_linkedin_evidence_against_resume", fail_verification)

    restored = restore_candidate_profile_fields(make_profile(), {"primary_skills": ["Python"]})
    existing_detail.update(restored)

    assert existing_detail["linkedin_profile"] is linkedin_profile
    assert existing_detail["contact_info"]["email"] == "candidate@example.com"
    assert existing_detail["github_verification"]["overall_status"] == "corroborated"
    assert existing_detail["match_score"] == 87.5
    assert existing_detail["candidate_grading"] == {"grade": "A"}
    assert existing_detail["selection"] == "Selected"
    assert existing_detail["linkedin_verification"] == LINKEDIN_VERIFICATION_FALLBACK


def test_missing_linkedin_profile_uses_fallback_without_captapi_fetch(monkeypatch):
    calls = []

    def fetch_profile(url):
        calls.append(url)
        return {"name": "Unexpected"}

    monkeypatch.setattr("api.fetch_captapi_linkedin_profile", fetch_profile)
    monkeypatch.setattr("api.get_github_evidence", lambda url: {"status": "available"})
    monkeypatch.setattr(
        "api.verify_github_evidence_against_resume",
        lambda resume, evidence: {"overall_status": "unverifiable"},
    )

    profile = make_profile()
    profile["skills"]["contact_info"]["linkedin"] = None
    restored = restore_candidate_profile_fields(profile, {})

    assert calls == []
    assert "linkedin_profile" not in restored
    assert restored["linkedin_verification"]["identity_confirmed"] is False
    assert restored["linkedin_verification"]["overall_status"] == "UNVERIFIABLE"
    assert "LinkedIn profile data not available" in restored["linkedin_verification"]["summary"]
