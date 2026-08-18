import pytest
from backend import get_resume_id
import hashlib
from io import BytesIO


def test_get_resume_id_generates_consistent_sha256():
    """Test that get_resume_id generates consistent SHA-256 hashes."""
    
    # Test with same content
    content = b"test resume content"
    file1 = BytesIO(content)
    file2 = BytesIO(content)
    
    id1 = get_resume_id(file1)
    id2 = get_resume_id(file2)
    
    assert id1 == id2, "Same content should produce same resume_id"
    
    # Verify it's a valid SHA-256 hash
    assert len(id1) == 64, "SHA-256 should be 64 characters"
    assert all(c in '0123456789abcdef' for c in id1), "Should be hex string"


def test_get_resume_id_different_content_different_hash():
    """Test that different content produces different hashes."""
    
    content1 = b"resume content 1"
    content2 = b"resume content 2"
    
    file1 = BytesIO(content1)
    file2 = BytesIO(content2)
    
    id1 = get_resume_id(file1)
    id2 = get_resume_id(file2)
    
    assert id1 != id2, "Different content should produce different resume_id"


def test_duplicate_detection_logic():
    """Test that duplicate detection works via SHA-256 comparison."""
    
    # Simulate duplicate upload scenario
    original_content = b"original resume"
    duplicate_content = b"original resume"  # Same content
    
    file1 = BytesIO(original_content)
    file2 = BytesIO(duplicate_content)
    
    id1 = get_resume_id(file1)
    id2 = get_resume_id(file2)
    
    # If IDs match, it's a duplicate
    assert id1 == id2, "Duplicate uploads should have matching resume_id"
    
    # This matching ID would be used to look up existing data
    # instead of re-processing
