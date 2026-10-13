"""Unit tests for shortlist persistence functionality."""

import os

# Import backend functions
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend import (
    add_candidate_to_shortlist,
    create_shortlist,
    delete_shortlist,
    get_shortlist,
    get_shortlists,
    get_user_shortlists,
    remove_candidate_from_shortlist,
    update_shortlist_status,
    verify_candidate_exists,
    verify_shortlist_ownership,
)


class TestShortlistPersistence:
    """Test suite for shortlist persistence operations."""

    @pytest.fixture
    def temp_shortlists_file(self):
        """Create a temporary shortlists.json file for testing."""
        temp_file = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json")
        temp_file.write("[]")
        temp_file.close()
        yield temp_file.name
        # Cleanup
        try:
            os.unlink(temp_file.name)
        except OSError:
            pass

    @pytest.fixture
    def mock_shortlists_path(self, temp_shortlists_file):
        """Mock the SHORTLISTS_PATH to use temporary file."""
        with patch("backend.SHORTLISTS_PATH", Path(temp_shortlists_file)):
            yield

    @pytest.fixture
    def sample_job_description(self):
        """Sample job description for testing."""
        return {
            "experience": "5+ years",
            "primary_skills": "Python, FastAPI",
            "secondary_skills": "SQL, Docker",
            "education": "Bachelor's in CS",
        }

    @pytest.fixture
    def sample_evidence_snapshot(self):
        """Sample evidence assessment snapshot."""
        return {
            "strongest_candidate": "Candidate A",
            "assessment_summary": "Strong candidate with relevant experience",
            "supporting_points": ["Point 1", "Point 2"],
        }

    @pytest.fixture
    def sample_candidate_evidence(self):
        """Sample candidate evidence snapshot."""
        return {
            "strengths": ["Python", "FastAPI"],
            "gaps": ["Docker"],
            "jd_coverage": ["Primary skills covered"],
            "evidence": ["Built API with Python"],
        }

    def test_create_shortlist(
        self, mock_shortlists_path, sample_job_description, sample_evidence_snapshot
    ):
        """Test creating a new shortlist."""
        shortlist = create_shortlist(
            job_description=sample_job_description,
            created_by="test_user",
            created_by_role="recruiter",
            evidence_assessment_snapshot=sample_evidence_snapshot,
        )

        assert shortlist is not None
        assert "shortlist_id" in shortlist
        assert shortlist["created_by"] == "test_user"
        assert shortlist["created_by_role"] == "recruiter"
        assert shortlist["status"] == "active"
        assert shortlist["job_description"] == sample_job_description
        assert shortlist["evidence_assessment_snapshot"] == sample_evidence_snapshot
        assert shortlist["shortlisted_candidates"] == []

    def test_get_user_shortlists(self, mock_shortlists_path, sample_job_description):
        """Test retrieving shortlists for a specific user."""
        # Create shortlists for different users
        create_shortlist(sample_job_description, "user1", "recruiter")
        create_shortlist(sample_job_description, "user2", "recruiter")
        create_shortlist(sample_job_description, "user1", "manager")

        # Get shortlists for user1
        user1_shortlists = get_user_shortlists("user1")
        assert len(user1_shortlists) == 2
        assert all(s["created_by"] == "user1" for s in user1_shortlists)

        # Get shortlists for user2
        user2_shortlists = get_user_shortlists("user2")
        assert len(user2_shortlists) == 1
        assert user2_shortlists[0]["created_by"] == "user2"

    def test_get_shortlist_by_id(self, mock_shortlists_path, sample_job_description):
        """Test retrieving a specific shortlist by ID."""
        shortlist = create_shortlist(sample_job_description, "test_user", "recruiter")
        shortlist_id = shortlist["shortlist_id"]

        retrieved = get_shortlist(shortlist_id)
        assert retrieved is not None
        assert retrieved["shortlist_id"] == shortlist_id

        # Test non-existent shortlist
        non_existent = get_shortlist("non_existent_id")
        assert non_existent is None

    def test_add_candidate_to_shortlist(
        self, mock_shortlists_path, sample_job_description, sample_candidate_evidence
    ):
        """Test adding a candidate to a shortlist."""
        shortlist = create_shortlist(sample_job_description, "test_user", "recruiter")
        shortlist_id = shortlist["shortlist_id"]

        updated = add_candidate_to_shortlist(
            shortlist_id=shortlist_id,
            resume_id="test_resume_id",
            candidate_name="Test Candidate",
            match_score=85.5,
            match_position="Top Match",
            evidence_snapshot=sample_candidate_evidence,
        )

        assert updated is not None
        assert len(updated["shortlisted_candidates"]) == 1
        candidate = updated["shortlisted_candidates"][0]
        assert candidate["resume_id"] == "test_resume_id"
        assert candidate["candidate_name"] == "Test Candidate"
        assert candidate["match_score"] == 85.5
        assert candidate["match_position"] == "Top Match"
        assert candidate["evidence_snapshot"] == sample_candidate_evidence
        assert "shortlisted_at" in candidate

    def test_prevent_duplicate_candidate(
        self, mock_shortlists_path, sample_job_description, sample_candidate_evidence
    ):
        """Test that duplicate candidates are not added."""
        shortlist = create_shortlist(sample_job_description, "test_user", "recruiter")
        shortlist_id = shortlist["shortlist_id"]

        # Add candidate first time
        add_candidate_to_shortlist(
            shortlist_id,
            "test_resume_id",
            "Test Candidate",
            85.5,
            "Top Match",
            sample_candidate_evidence,
        )

        # Try to add same candidate again
        updated = add_candidate_to_shortlist(
            shortlist_id,
            "test_resume_id",
            "Test Candidate",
            85.5,
            "Top Match",
            sample_candidate_evidence,
        )

        # Should still have only one candidate
        assert len(updated["shortlisted_candidates"]) == 1

    def test_remove_candidate_from_shortlist(
        self, mock_shortlists_path, sample_job_description, sample_candidate_evidence
    ):
        """Test removing a candidate from a shortlist."""
        shortlist = create_shortlist(sample_job_description, "test_user", "recruiter")
        shortlist_id = shortlist["shortlist_id"]

        # Add two candidates
        add_candidate_to_shortlist(
            shortlist_id,
            "resume1",
            "Candidate 1",
            85.5,
            "Top Match",
            sample_candidate_evidence,
        )
        add_candidate_to_shortlist(
            shortlist_id,
            "resume2",
            "Candidate 2",
            75.0,
            "Match #2",
            sample_candidate_evidence,
        )

        # Remove first candidate
        updated = remove_candidate_from_shortlist(shortlist_id, "resume1")

        assert updated is not None
        assert len(updated["shortlisted_candidates"]) == 1
        assert updated["shortlisted_candidates"][0]["resume_id"] == "resume2"

    def test_update_shortlist_status(
        self, mock_shortlists_path, sample_job_description
    ):
        """Test updating shortlist status."""
        shortlist = create_shortlist(sample_job_description, "test_user", "recruiter")
        shortlist_id = shortlist["shortlist_id"]

        # Update to archived
        updated = update_shortlist_status(shortlist_id, "archived")
        assert updated is not None
        assert updated["status"] == "archived"

        # Update back to active
        updated = update_shortlist_status(shortlist_id, "active")
        assert updated["status"] == "active"

        # Test invalid status
        invalid = update_shortlist_status(shortlist_id, "invalid_status")
        assert invalid is None

    def test_delete_shortlist(self, mock_shortlists_path, sample_job_description):
        """Test deleting a shortlist."""
        shortlist = create_shortlist(sample_job_description, "test_user", "recruiter")
        shortlist_id = shortlist["shortlist_id"]

        # Delete shortlist
        success = delete_shortlist(shortlist_id)
        assert success is True

        # Verify it's gone
        retrieved = get_shortlist(shortlist_id)
        assert retrieved is None

        # Test deleting non-existent shortlist
        success = delete_shortlist("non_existent_id")
        assert success is False

    def test_verify_shortlist_ownership(
        self, mock_shortlists_path, sample_job_description
    ):
        """Test shortlist ownership verification."""
        shortlist = create_shortlist(sample_job_description, "owner_user", "recruiter")
        shortlist_id = shortlist["shortlist_id"]

        # Owner should have access
        assert verify_shortlist_ownership(shortlist_id, "owner_user") is True

        # Different user should not have access
        assert verify_shortlist_ownership(shortlist_id, "other_user") is False

        # Non-existent shortlist
        assert verify_shortlist_ownership("non_existent_id", "owner_user") is False

    def test_malformed_json_handling(self, monkeypatch):
        """Test handling of malformed JSON in shortlists file."""
        # Create a temporary file with malformed JSON
        temp_file = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json")
        temp_file.write('{"invalid": json}')
        temp_file.close()

        try:
            # Mock the path to use the malformed file
            with patch("backend.SHORTLISTS_PATH", Path(temp_file.name)):
                # Should handle gracefully and return empty list
                shortlists = get_shortlists()
                assert shortlists == []
        finally:
            os.unlink(temp_file.name)

    def test_persistence_across_operations(
        self, mock_shortlists_path, sample_job_description, sample_candidate_evidence
    ):
        """Test that data persists across multiple operations."""
        # Create shortlist
        shortlist1 = create_shortlist(sample_job_description, "test_user", "recruiter")
        shortlist_id = shortlist1["shortlist_id"]

        # Add candidate
        add_candidate_to_shortlist(
            shortlist_id,
            "resume1",
            "Candidate 1",
            85.5,
            "Top Match",
            sample_candidate_evidence,
        )

        # Retrieve and verify
        retrieved = get_shortlist(shortlist_id)
        assert len(retrieved["shortlisted_candidates"]) == 1

        # Update status
        update_shortlist_status(shortlist_id, "archived")

        # Retrieve again and verify
        retrieved = get_shortlist(shortlist_id)
        assert retrieved["status"] == "archived"
        assert len(retrieved["shortlisted_candidates"]) == 1


class TestShortlistValidation:
    """Test suite for shortlist validation and error handling."""

    def test_candidate_existence_verification(self, monkeypatch):
        """Test candidate existence verification."""
        # Mock the resume database
        mock_db = {
            "existing_resume": {"resume_name": "Existing Resume"},
            "another_resume": {"resume_name": "Another Resume"},
        }

        with patch("backend.get_active_resume_db_records", return_value=mock_db):
            assert verify_candidate_exists("existing_resume") is True
            assert verify_candidate_exists("another_resume") is True
            assert verify_candidate_exists("non_existent_resume") is False

    def test_empty_shortlists_file(self, monkeypatch):
        """Test handling of empty shortlists file."""
        temp_file = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json")
        temp_file.write("[]")
        temp_file.close()

        try:
            with patch("backend.SHORTLISTS_PATH", Path(temp_file.name)):
                shortlists = get_shortlists()
                assert shortlists == []
        finally:
            os.unlink(temp_file.name)

    def test_missing_shortlists_file(self, monkeypatch):
        """Test handling of missing shortlists file."""
        # Use a non-existent file path
        non_existent_path = Path(tempfile.gettempdir()) / "non_existent_shortlists.json"

        with patch("backend.SHORTLISTS_PATH", non_existent_path):
            with patch("backend.initialize_project_storage_files"):
                with patch("backend.read_json_file", return_value=[]):
                    shortlists = get_shortlists()
                    assert shortlists == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
