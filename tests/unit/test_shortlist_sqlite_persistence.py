"""Unit tests for SQLite shortlist persistence functionality."""

import json
import os
import tempfile
import pytest
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import backend functions
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend import (
    create_shortlist,
    get_shortlists,
    get_user_shortlists,
    get_shortlist,
    add_candidate_to_shortlist,
    remove_candidate_from_shortlist,
    update_shortlist_status,
    delete_shortlist,
    verify_shortlist_ownership,
    verify_candidate_exists,
    get_active_resume_db_records,
    PROJECT_ROOT,
    initialize_shortlists_database,
    get_shortlists_db_connection,
)


class TestSQLiteShortlistPersistence:
    """Test suite for SQLite shortlist persistence operations."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary SQLite database for testing."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
        temp_file.close()
        yield temp_file.name
        # Cleanup
        try:
            os.unlink(temp_file.name)
        except:
            pass

    @pytest.fixture
    def mock_db_path(self, temp_db_path):
        """Mock the SHORTLISTS_DB_PATH to use temporary file."""
        import backend
        original_db_path = backend.SHORTLISTS_DB_PATH
        backend.SHORTLISTS_DB_PATH = Path(temp_db_path)
        yield temp_db_path
        backend.SHORTLISTS_DB_PATH = original_db_path

    @pytest.fixture
    def sample_job_description(self):
        """Sample job description for testing."""
        return {
            "experience": "5+ years",
            "primary_skills": "Python, FastAPI",
            "secondary_skills": "SQL, Docker",
            "education": "Bachelor's in CS"
        }

    @pytest.fixture
    def sample_evidence_snapshot(self):
        """Sample evidence assessment snapshot."""
        return {
            "strongest_candidate": "Candidate A",
            "assessment_summary": "Strong candidate with relevant experience",
            "supporting_points": ["Point 1", "Point 2"]
        }

    @pytest.fixture
    def sample_candidate_evidence(self):
        """Sample candidate evidence snapshot."""
        return {
            "strengths": ["Python", "FastAPI"],
            "gaps": ["Docker"],
            "jd_coverage": ["Primary skills covered"],
            "evidence": ["Built API with Python"]
        }

    def test_database_initialization(self, mock_db_path):
        """Test that database and tables are created correctly."""
        initialize_shortlists_database()

        # Check that database file exists
        assert Path(mock_db_path).exists()

        # Check that tables exist
        conn = sqlite3.connect(mock_db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        assert 'shortlists' in tables
        assert 'shortlisted_candidates' in tables
        assert 'candidate_evidence' in tables
        assert 'evidence_assessments' in tables

        conn.close()

    def test_create_shortlist(self, mock_db_path, sample_job_description, sample_evidence_snapshot):
        """Test creating a new shortlist in SQLite."""
        shortlist = create_shortlist(
            job_description=sample_job_description,
            user_id="test_user",
            created_by_role="recruiter",
            evidence_assessment_snapshot=sample_evidence_snapshot
        )

        assert shortlist is not None
        assert "shortlist_id" in shortlist
        assert shortlist["user_id"] == "test_user"
        assert shortlist["created_by_role"] == "recruiter"
        assert shortlist["status"] == "active"
        # Job description is stored as JSON string in SQLite
        assert json.loads(shortlist["job_description"]) == sample_job_description
        assert shortlist["evidence_assessment_snapshot"] == sample_evidence_snapshot
        assert shortlist["shortlisted_candidates"] == []

    def test_get_user_shortlists(self, mock_db_path, sample_job_description):
        """Test retrieving shortlists for a specific user."""
        # Create shortlists for different users
        create_shortlist(sample_job_description, "user1", "recruiter")
        create_shortlist(sample_job_description, "user2", "recruiter")
        create_shortlist(sample_job_description, "user1", "manager")

        # Get shortlists for user1
        user1_shortlists = get_user_shortlists("user1")
        assert len(user1_shortlists) == 2
        assert all(s["user_id"] == "user1" for s in user1_shortlists)

        # Get shortlists for user2
        user2_shortlists = get_user_shortlists("user2")
        assert len(user2_shortlists) == 1
        assert user2_shortlists[0]["user_id"] == "user2"

    def test_get_shortlist_by_id(self, mock_db_path, sample_job_description):
        """Test retrieving a specific shortlist by ID."""
        shortlist = create_shortlist(sample_job_description, "test_user", "recruiter")
        shortlist_id = shortlist["shortlist_id"]

        retrieved = get_shortlist(shortlist_id)
        assert retrieved is not None
        assert retrieved["shortlist_id"] == shortlist_id

        # Test non-existent shortlist
        non_existent = get_shortlist("non_existent_id")
        assert non_existent is None

    def test_add_candidate_to_shortlist(self, mock_db_path, sample_job_description, sample_candidate_evidence):
        """Test adding a candidate to a shortlist."""
        shortlist = create_shortlist(sample_job_description, "test_user", "recruiter")
        shortlist_id = shortlist["shortlist_id"]

        updated = add_candidate_to_shortlist(
            shortlist_id=shortlist_id,
            resume_id="test_resume_id",
            candidate_name="Test Candidate",
            match_score=85.5,
            match_position="Top Match",
            evidence_snapshot=sample_candidate_evidence
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

    def test_prevent_duplicate_candidate(self, mock_db_path, sample_job_description, sample_candidate_evidence):
        """Test that duplicate candidates are not added."""
        shortlist = create_shortlist(sample_job_description, "test_user", "recruiter")
        shortlist_id = shortlist["shortlist_id"]

        # Add candidate first time
        add_candidate_to_shortlist(shortlist_id, "test_resume_id", "Test Candidate", 85.5, "Top Match", sample_candidate_evidence)

        # Try to add same candidate again
        updated = add_candidate_to_shortlist(shortlist_id, "test_resume_id", "Test Candidate", 85.5, "Top Match", sample_candidate_evidence)

        # Should still have only one candidate
        assert len(updated["shortlisted_candidates"]) == 1

    def test_remove_candidate_from_shortlist(self, mock_db_path, sample_job_description, sample_candidate_evidence):
        """Test removing a candidate from a shortlist."""
        shortlist = create_shortlist(sample_job_description, "test_user", "recruiter")
        shortlist_id = shortlist["shortlist_id"]

        # Add two candidates
        add_candidate_to_shortlist(shortlist_id, "resume1", "Candidate 1", 85.5, "Top Match", sample_candidate_evidence)
        add_candidate_to_shortlist(shortlist_id, "resume2", "Candidate 2", 75.0, "Match #2", sample_candidate_evidence)

        # Remove first candidate
        updated = remove_candidate_from_shortlist(shortlist_id, "resume1")

        assert updated is not None
        assert len(updated["shortlisted_candidates"]) == 1
        assert updated["shortlisted_candidates"][0]["resume_id"] == "resume2"

    def test_update_shortlist_status(self, mock_db_path, sample_job_description):
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

    def test_delete_shortlist(self, mock_db_path, sample_job_description):
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

    def test_verify_shortlist_ownership(self, mock_db_path, sample_job_description):
        """Test shortlist ownership verification."""
        shortlist = create_shortlist(sample_job_description, "owner_user", "recruiter")
        shortlist_id = shortlist["shortlist_id"]

        # Owner should have access
        assert verify_shortlist_ownership(shortlist_id, "owner_user") is True

        # Different user should not have access
        assert verify_shortlist_ownership(shortlist_id, "other_user") is False

        # Non-existent shortlist
        assert verify_shortlist_ownership("non_existent_id", "owner_user") is False

    def test_evidence_assessment_persistence(self, mock_db_path, sample_job_description, sample_evidence_snapshot):
        """Test that evidence assessment snapshots are persisted correctly."""
        shortlist = create_shortlist(
            sample_job_description,
            "test_user",
            "recruiter",
            evidence_assessment_snapshot=sample_evidence_snapshot
        )

        # Retrieve and verify evidence assessment is preserved
        retrieved = get_shortlist(shortlist["shortlist_id"])
        assert retrieved["evidence_assessment_snapshot"] == sample_evidence_snapshot

    def test_candidate_evidence_persistence(self, mock_db_path, sample_job_description, sample_candidate_evidence):
        """Test that candidate evidence snapshots are persisted correctly."""
        shortlist = create_shortlist(sample_job_description, "test_user", "recruiter")
        shortlist_id = shortlist["shortlist_id"]

        add_candidate_to_shortlist(shortlist_id, "resume1", "Candidate 1", 85.5, "Top Match", sample_candidate_evidence)

        # Retrieve and verify candidate evidence is preserved
        retrieved = get_shortlist(shortlist_id)
        candidate = retrieved["shortlisted_candidates"][0]
        assert candidate["evidence_snapshot"] == sample_candidate_evidence

    def test_database_persistence_across_restart(self, mock_db_path, sample_job_description):
        """Test that data persists across multiple operations."""
        # Create shortlist
        shortlist1 = create_shortlist(sample_job_description, "test_user", "recruiter")
        shortlist_id = shortlist1["shortlist_id"]

        # Add candidate
        sample_evidence = {"strengths": ["Python"], "gaps": [], "jd_coverage": [], "evidence": []}
        add_candidate_to_shortlist(shortlist_id, "resume1", "Candidate 1", 85.5, "Top Match", sample_evidence)

        # Retrieve and verify
        retrieved = get_shortlist(shortlist_id)
        assert len(retrieved["shortlisted_candidates"]) == 1

        # Update status
        update_shortlist_status(shortlist_id, "archived")

        # Retrieve again and verify
        retrieved = get_shortlist(shortlist_id)
        assert retrieved["status"] == "archived"
        assert len(retrieved["shortlisted_candidates"]) == 1


class TestSQLiteShortlistValidation:
    """Test suite for SQLite shortlist validation and error handling."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary SQLite database for testing."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
        temp_file.close()
        yield temp_file.name
        # Cleanup
        try:
            os.unlink(temp_file.name)
        except:
            pass

    @pytest.fixture
    def mock_db_path(self, temp_db_path):
        """Mock the SHORTLISTS_DB_PATH to use temporary file."""
        import backend
        original_db_path = backend.SHORTLISTS_DB_PATH
        backend.SHORTLISTS_DB_PATH = Path(temp_db_path)
        yield temp_db_path
        backend.SHORTLISTS_DB_PATH = original_db_path

    @pytest.fixture
    def sample_job_description(self):
        """Sample job description for testing."""
        return {
            "experience": "5+ years",
            "primary_skills": "Python, FastAPI",
            "secondary_skills": "SQL, Docker",
            "education": "Bachelor's in CS"
        }

    @pytest.fixture
    def sample_candidate_evidence(self):
        """Sample candidate evidence snapshot."""
        return {
            "strengths": ["Python", "FastAPI"],
            "gaps": ["Docker"],
            "jd_coverage": ["Primary skills covered"],
            "evidence": ["Built API with Python"]
        }

    def test_candidate_existence_verification(self, monkeypatch):
        """Test candidate existence verification."""
        # Mock the resume database
        mock_db = {
            "existing_resume": {"resume_name": "Existing Resume"},
            "another_resume": {"resume_name": "Another Resume"}
        }

        with patch('backend.get_active_resume_db_records', return_value=mock_db):
            assert verify_candidate_exists("existing_resume") is True
            assert verify_candidate_exists("another_resume") is True
            assert verify_candidate_exists("non_existent_resume") is False

    def test_empty_database(self, mock_db_path):
        """Test handling of empty database."""
        initialize_shortlists_database()

        # Should work with empty database
        shortlists = get_shortlists()
        assert shortlists == []

    def test_foreign_key_constraints(self, mock_db_path, sample_job_description, sample_candidate_evidence):
        """Test that foreign key constraints work correctly."""
        shortlist = create_shortlist(sample_job_description, "test_user", "recruiter")
        shortlist_id = shortlist["shortlist_id"]

        # Add candidate
        add_candidate_to_shortlist(shortlist_id, "resume1", "Candidate 1", 85.5, "Top Match", sample_candidate_evidence)

        # Delete shortlist (should cascade delete candidates and evidence)
        delete_shortlist(shortlist_id)

        # Verify shortlist is gone
        assert get_shortlist(shortlist_id) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
