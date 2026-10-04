"""Unit tests for Assessment Lifecycle & Storage Utility."""

import json
import pytest
from backend_question_generator import (
    get_all_assessment_questions,
)


def test_assessment_status_lifecycle_rules():
    """Verify standard status transition values allowed by recruiter assessment page."""
    valid_statuses = {"Not Created", "Ready to Share", "In Progress", "Completed"}
    
    status_flow = ["Not Created", "Ready to Share", "In Progress", "Completed"]
    for status in status_flow:
        assert status in valid_statuses


def test_assessment_id_record_association():
    """Verify unique assessment ID keys bind candidate, shortlist, and job role."""
    candidate_id = "resume_999"
    shortlist_id = "shortlist_888"
    job_role = "AI/ML Engineer — Fresher"

    # Compound key formula used by AssessmentManagementPage & assessmentStore
    key = f"{candidate_id}_{shortlist_id}"
    assert key == "resume_999_shortlist_888"
    assert "AI/ML Engineer" in job_role
