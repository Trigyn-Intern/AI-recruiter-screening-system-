from api import restore_candidate_profile_fields


def test_candidate_detail_restores_github_without_changing_existing_fields(monkeypatch):
    contact_info = {
        "email": "sapna.test@example.com",
        "phone": "+91-90000-00000",
        "linkedin": "linkedin.com/in/test-candidate",
        "github": "github.com/test-candidate",
    }
    github_evidence = {
        "status": "available",
        "profile": {"username": "test-candidate"},
        "repositories": [],
    }
    verification = {
        "overall_status": "corroborated",
        "corroborated": [],
        "partially_corroborated": [],
        "unverifiable": [],
        "discrepancies": [],
        "supporting_repositories": [],
    }
    calls = {}

    monkeypatch.setattr(
        "api.fetch_captapi_linkedin_profile",
        lambda url: {"name": "Test Candidate"},
    )

    def get_evidence(url):
        calls["github_url"] = url
        return github_evidence

    def verify(profile, evidence):
        calls["profile"] = profile
        calls["evidence"] = evidence
        return verification

    monkeypatch.setattr("api.get_github_evidence", get_evidence)
    monkeypatch.setattr("api.verify_github_evidence_against_resume", verify)

    restored = restore_candidate_profile_fields({"skills": {
        "technical_skills": ["Python"],
        "contact_info": contact_info,
    }})

    assert restored["github_verification"] == verification
    assert calls["github_url"] == "github.com/test-candidate"
    assert calls["profile"]["contact_info"] == contact_info
    assert calls["evidence"] is github_evidence
    assert restored["contact_info"] == contact_info
    assert restored["linkedin_profile"] == {"name": "Test Candidate"}
    assert restored["github_verification"] is not restored["contact_info"]
    assert restored["github_verification"].get("match_score") is None
    assert restored["github_verification"].get("selection") is None
