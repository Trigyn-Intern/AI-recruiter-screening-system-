"""
Simple test for Phase 1 chunking functionality without requiring full model loading.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def test_text_cleaning():
    """Test basic text cleaning."""
    print("Testing text cleaning...")

    from backend import clean_resume_text

    dirty_text = """
    This is a test.


    With too many    blank lines.



    And excessive    whitespace.
    """

    cleaned = clean_resume_text(dirty_text)

    assert "\n\n\n" not in cleaned, "Should not have triple newlines"
    assert (
        "excessive    whitespace" not in cleaned
    ), "Should normalize internal whitespace"
    assert "excessive whitespace" in cleaned, "Should preserve single spaces"

    print("✓ Text cleaning works")
    return True


def test_section_normalization():
    """Test section heading normalization."""
    print("Testing section normalization...")

    from backend import normalize_section_heading

    test_cases = [
        ("WORK EXPERIENCE", "Experience"),
        ("Work Experience", "Experience"),
        ("Professional Experience", "Experience"),
        ("SKILLS", "Skills"),
        ("Technical Skills", "Skills"),
        ("Projects", "Projects"),
        ("Education", "Education"),
    ]

    for input_heading, expected in test_cases:
        result = normalize_section_heading(input_heading)
        assert result == expected, f"Expected {expected}, got {result}"

    print("✓ Section normalization works")
    return True


def test_section_detection():
    """Test section detection."""
    print("Testing section detection...")

    from backend import detect_resume_sections

    sample_resume_items = [
        {"page": 1, "text": "SUMMARY"},
        {"page": 1, "text": "Experienced developer..."},
        {"page": 1, "text": ""},
        {"page": 1, "text": "WORK EXPERIENCE"},
        {"page": 1, "text": "ABC Company"},
        {"page": 1, "text": ""},
        {"page": 1, "text": "SKILLS"},
        {"page": 1, "text": "Python, Java"},
    ]

    sections = detect_resume_sections(sample_resume_items)

    detected_section_names = [s["section"] for s in sections]
    assert "Summary" in detected_section_names
    assert "Experience" in detected_section_names
    assert "Skills" in detected_section_names

    print(f"✓ Section detection works (found {len(sections)} sections)")
    return True


def test_recursive_splitting():
    """Test recursive splitting."""
    print("Testing recursive splitting...")

    from backend import MAX_CHUNK_SIZE, recursively_split_large_chunk

    large_text = "This is a test sentence. " * 100
    split_chunks = recursively_split_large_chunk(large_text, MAX_CHUNK_SIZE)

    assert len(split_chunks) > 1, "Should split large text"
    assert all(
        len(c) <= MAX_CHUNK_SIZE + 50 for c in split_chunks
    ), "Chunks should be within size limit"

    print(f"✓ Recursive splitting works (split into {len(split_chunks)} chunks)")
    return True


def test_chunk_creation():
    """Test chunk creation."""
    print("Testing chunk creation...")

    from backend import process_resume_into_chunks

    sample_resume_items = [
        {"page": 1, "text": "PROJECTS"},
        {"page": 1, "text": "AI Recruiter System"},
        {"page": 1, "text": "Built a resume screening system using Python"},
        {"page": 1, "text": "Implemented BGE embeddings and FAISS"},
        {"page": 1, "text": ""},
        {"page": 1, "text": "Medical AI Platform"},
        {"page": 1, "text": "Developed ML models for prediction"},
    ]

    resume_id = "test_resume"
    resume_name = "test.pdf"

    chunks = process_resume_into_chunks(resume_id, resume_name, sample_resume_items)

    assert len(chunks) > 0, "Should create chunks"
    assert all(
        c["section"] == "Projects" for c in chunks
    ), "All chunks should be in Projects"

    print(f"✓ Chunk creation works (created {len(chunks)} chunks)")
    return True


def main():
    """Run simple tests."""
    print("\n" + "=" * 60)
    print("PHASE 1 CHUNKING SIMPLE TESTS")
    print("=" * 60 + "\n")

    tests = [
        test_text_cleaning,
        test_section_normalization,
        test_section_detection,
        test_recursive_splitting,
        test_chunk_creation,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} FAILED: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
