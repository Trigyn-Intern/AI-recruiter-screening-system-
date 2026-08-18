import pytest
from backend import get_active_resume_db_records


def test_get_active_resume_db_records_loads_independently():
    """Test that get_active_resume_db_records() works without FAISS dependency."""
    records = get_active_resume_db_records()
    
    # Should return records with valid skills (count may vary based on uploads)
    assert len(records) >= 5, "Should have at least the 5 retained resumes"
    
    # Verify each record has required fields
    for resume_id, record in records.items():
        assert "resume_id" in record
        assert "resume_name" in record
        assert "resume_skill_profile" in record
        assert "skills_model" in record
        assert "last_updated_at" in record
    
    # Check that the 5 retained resumes are present (may have additional uploads)
    expected_ids = {
        "735ab33a8ed911639a4e8bd3f37f921beac3315552c422a7b53ab695916d0ac9",
        "1d42149dac25b414aad483bdb351671c32cf40e04b5cb8d9eaecbdd80757ac09",
        "fa125bca6ae296f8ef714e2a5e2b0ed9fa811c203648e77d18b11a1efbf8c0ed",
        "8fd27b4b9964ff7264236ceab79058a215681bf5aa6d38d8ff052a6f74d8710d",
        "d725846d61320a0a847b36c58684fc560bca16d6cd082dfacd0017108dcf0dfd",
    }
    
    # Verify all expected retained resumes are present
    assert expected_ids.issubset(set(records.keys())), "All 5 retained resumes should be present"


def test_get_active_resume_db_records_returns_empty_when_no_skills():
    """Test that get_active_resume_db_records() returns empty dict when skills store is empty."""
    import json
    from pathlib import Path
    from backend import RESUME_SKILLS_PATH
    
    # Backup current skills
    backup_path = RESUME_SKILLS_PATH.with_suffix('.json.test_backup')
    import shutil
    shutil.copy(RESUME_SKILLS_PATH, backup_path)
    
    try:
        # Write empty skills store
        with open(RESUME_SKILLS_PATH, 'w') as f:
            json.dump({}, f)
        
        records = get_active_resume_db_records()
        assert len(records) == 0
    finally:
        # Restore backup
        shutil.copy(backup_path, RESUME_SKILLS_PATH)
        backup_path.unlink()
