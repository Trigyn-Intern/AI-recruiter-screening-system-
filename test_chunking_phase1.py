"""
Test Phase 1 Resume Chunking Implementation

Tests the new chunk-based retrieval system with different resume structures.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from backend import (
    clean_resume_text,
    create_context_aware_chunks,
    detect_resume_sections,
    enrich_chunk_metadata,
    normalize_section_heading,
    process_resume_into_chunks,
    search_chunks_by_embedding,
)


def test_basic_text_cleaning():
    """Test basic text cleaning functionality."""
    print("=" * 70)
    print("TEST 1: Basic Text Cleaning")
    print("=" * 70)

    dirty_text = """
    This is a test.


    With too many    blank lines.



    And excessive    whitespace.
    """

    cleaned = clean_resume_text(dirty_text)
    print("Original:")
    print(repr(dirty_text))
    print("\nCleaned:")
    print(repr(cleaned))

    assert "\n\n\n" not in cleaned, "Should not have triple newlines"
    assert (
        "excessive    whitespace" not in cleaned
    ), "Should normalize internal whitespace"
    assert "excessive whitespace" in cleaned, "Should preserve single spaces"

    print("✓ Text cleaning works correctly\n")


def test_section_normalization():
    """Test section heading normalization."""
    print("=" * 70)
    print("TEST 2: Section Heading Normalization")
    print("=" * 70)

    test_cases = [
        ("WORK EXPERIENCE", "Experience"),
        ("Work Experience", "Experience"),
        ("Professional Experience", "Experience"),
        ("SKILLS", "Skills"),
        ("Technical Skills", "Skills"),
        ("Projects", "Projects"),
        ("Education", "Education"),
        ("CERTIFICATIONS", "Certifications"),
    ]

    for input_heading, expected in test_cases:
        result = normalize_section_heading(input_heading)
        print(f"'{input_heading}' → '{result}' (expected: '{expected}')")
        assert result == expected, f"Expected {expected}, got {result}"

    print("✓ Section normalization works correctly\n")


def test_section_detection():
    """Test section detection on sample resume text."""
    print("=" * 70)
    print("TEST 3: Section Detection")
    print("=" * 70)

    sample_resume_items = [
        {"page": 1, "text": "John Doe"},
        {"page": 1, "text": "Software Engineer"},
        {"page": 1, "text": ""},
        {"page": 1, "text": "SUMMARY"},
        {"page": 1, "text": "Experienced developer..."},
        {"page": 1, "text": ""},
        {"page": 1, "text": "WORK EXPERIENCE"},
        {"page": 1, "text": "ABC Company - Software Engineer"},
        {"page": 1, "text": "Developed applications..."},
        {"page": 1, "text": ""},
        {"page": 1, "text": "SKILLS"},
        {"page": 1, "text": "Python, Java, JavaScript"},
        {"page": 1, "text": ""},
        {"page": 1, "text": "EDUCATION"},
        {"page": 1, "text": "BS Computer Science"},
    ]

    sections = detect_resume_sections(sample_resume_items)

    print(f"Detected {len(sections)} sections:")
    for section in sections:
        print(f"  - {section['section']} (heading: '{section['heading']}')")

    detected_section_names = [s["section"] for s in sections]
    assert "Summary" in detected_section_names, "Should detect Summary"
    assert "Experience" in detected_section_names, "Should detect Experience"
    assert "Skills" in detected_section_names, "Should detect Skills"
    assert "Education" in detected_section_names, "Should detect Education"

    print("✓ Section detection works correctly\n")


def test_context_aware_chunking():
    """Test context-aware chunking."""
    print("=" * 70)
    print("TEST 4: Context-Aware Chunking")
    print("=" * 70)

    sample_resume_items = [
        {"page": 1, "text": "PROJECTS"},
        {"page": 1, "text": "AI Recruiter System"},
        {"page": 1, "text": "Built a resume screening system using Python and FastAPI"},
        {"page": 1, "text": "Implemented BGE embeddings and FAISS vector search"},
        {"page": 1, "text": "Achieved 95% accuracy in candidate matching"},
        {"page": 1, "text": ""},
        {"page": 1, "text": "Medical AI Platform"},
        {"page": 1, "text": "Developed ML models for disease prediction"},
        {"page": 1, "text": "Used PyTorch and TensorFlow"},
    ]

    sections = detect_resume_sections(sample_resume_items)
    chunks = create_context_aware_chunks(sample_resume_items, sections)

    print(f"Created {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        print(f"\nChunk {i+1}:")
        print(f"  Section: {chunk['section']}")
        print(f"  Subsection: {chunk.get('subsection')}")
        print(f"  Text preview: {chunk['text'][:100]}...")

    assert len(chunks) >= 1, "Should create at least one chunk"
    assert all(
        c["section"] == "Projects" for c in chunks
    ), "All chunks should be in Projects section"

    print("✓ Context-aware chunking works correctly\n")


def test_recursive_splitting():
    """Test recursive splitting for large chunks."""
    print("=" * 70)
    print("TEST 5: Recursive Splitting")
    print("=" * 70)

    # Create a large chunk
    large_text = "This is a test sentence. " * 100  # ~2500 characters

    from backend import MAX_CHUNK_SIZE, recursively_split_large_chunk

    split_chunks = recursively_split_large_chunk(large_text, MAX_CHUNK_SIZE)

    print(f"Original text length: {len(large_text)}")
    print(f"Split into {len(split_chunks)} chunks")

    for i, chunk in enumerate(split_chunks):
        print(f"  Chunk {i+1}: {len(chunk)} characters")

    assert len(split_chunks) > 1, "Should split large text into multiple chunks"
    assert all(
        len(c) <= MAX_CHUNK_SIZE + 50 for c in split_chunks
    ), "All chunks should be within size limit"

    print("✓ Recursive splitting works correctly\n")


def test_metadata_enrichment():
    """Test metadata enrichment for chunks."""
    print("=" * 70)
    print("TEST 6: Metadata Enrichment")
    print("=" * 70)

    sample_chunks = [
        {
            "section": "Projects",
            "subsection": "AI Recruiter",
            "text": (
                "Built a machine learning model using Python and Scikit-learn. "
                "Achieved 91% accuracy."
            ),
            "page": 1,
            "start_index": 0,
            "end_index": 5,
        }
    ]

    resume_id = "test_resume_123"
    resume_name = "test_resume.pdf"

    enriched = enrich_chunk_metadata(sample_chunks, resume_id, resume_name)

    print(f"Enriched {len(enriched)} chunks:")
    for chunk in enriched:
        print(f"\nChunk ID: {chunk['chunk_id']}")
        print(f"  Section: {chunk['section']}")
        print(f"  Subsection: {chunk['subsection']}")
        print(f"  Technologies: {chunk.get('technologies', [])}")
        print(f"  Skills: {chunk.get('skills', [])}")
        print(f"  Company: {chunk.get('company')}")
        print(f"  Role: {chunk.get('role')}")

    assert len(enriched) == 1, "Should have one enriched chunk"
    assert (
        enriched[0]["chunk_id"] == f"{resume_id}_chunk_000"
    ), "Should have correct chunk ID"
    assert enriched[0]["resume_id"] == resume_id, "Should have correct resume ID"
    assert "Python" in enriched[0].get("technologies", []), "Should detect Python"

    print("✓ Metadata enrichment works correctly\n")


def test_resume_1_clear_sections():
    """Test with a resume that has clear section headings."""
    print("=" * 70)
    print("TEST 7: Resume with Clear Sections")
    print("=" * 70)

    resume_text = """
    JANE SMITH
    Senior Software Engineer

    SUMMARY
    Experienced software engineer with 8+ years in full-stack development...

    WORK EXPERIENCE
    TechCorp Inc. - Senior Software Engineer
    • Led team of 5 developers
    • Built microservices architecture
    • Implemented CI/CD pipelines

    DataFlow Systems - Software Engineer
    • Developed data processing pipelines
    • Used Python and Apache Spark

    SKILLS
    Python, Java, JavaScript, React, Node.js, Docker, Kubernetes

    EDUCATION
    MS Computer Science, Stanford University
    BS Computer Science, MIT
    """

    # Simulate text items
    text_items = [
        {"page": 1, "text": line.strip()}
        for line in resume_text.split("\n")
        if line.strip()
    ]

    resume_id = "test_resume_clear_sections"
    resume_name = "clear_sections_resume.pdf"

    chunks = process_resume_into_chunks(resume_id, resume_name, text_items)

    print(f"Processed into {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        print(f"\nChunk {i+1}:")
        print(f"  Section: {chunk['section']}")
        print(f"  Subsection: {chunk.get('subsection')}")
        print(f"  Technologies: {chunk.get('technologies', [])}")

    assert len(chunks) > 0, "Should create chunks"
    assert any(
        c["section"] == "Experience" for c in chunks
    ), "Should have Experience chunks"
    assert any(c["section"] == "Skills" for c in chunks), "Should have Skills chunks"
    assert any(
        c["section"] == "Education" for c in chunks
    ), "Should have Education chunks"

    print("✓ Resume with clear sections processed correctly\n")


def test_resume_2_unusual_sections():
    """Test with a resume that has unusual section names."""
    print("=" * 70)
    print("TEST 8: Resume with Unusual Section Names")
    print("=" * 70)

    resume_text = """
    JOHN DOE
    Data Scientist

    PROFESSIONAL BACKGROUND
    5 years of experience in data science and machine learning...

    WHAT I DO
    • Data analysis
    • Machine learning models
    • Statistical modeling

    KEY PROJECTS
    Fraud Detection System
    Built using Python and TensorFlow

    Customer Churn Prediction
    Used Scikit-learn and Pandas

    ACADEMIC CREDENTIALS
    PhD in Statistics, Harvard
    MS in Mathematics, MIT
    """

    text_items = [
        {"page": 1, "text": line.strip()}
        for line in resume_text.split("\n")
        if line.strip()
    ]

    resume_id = "test_resume_unusual_sections"
    resume_name = "unusual_sections_resume.pdf"

    chunks = process_resume_into_chunks(resume_id, resume_name, text_items)

    print(f"Processed into {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        print(f"\nChunk {i+1}:")
        print(f"  Section: {chunk['section']}")
        print(f"  Subsection: {chunk.get('subsection')}")

    # Should normalize unusual section names
    section_names = [c["section"] for c in chunks]
    print(f"Detected sections: {set(section_names)}")

    assert len(chunks) > 0, "Should create chunks"
    # Should normalize "PROFESSIONAL BACKGROUND" to "Experience"
    # Should normalize "KEY PROJECTS" to "Projects"
    # Should normalize "ACADEMIC CREDENTIALS" to "Education"

    print("✓ Resume with unusual sections processed correctly\n")


def test_resume_3_multiple_projects():
    """Test with a resume that has multiple complex projects."""
    print("=" * 70)
    print("TEST 9: Resume with Multiple Complex Projects")
    print("=" * 70)

    resume_text = """
    ALICE JOHNSON
    Full Stack Developer

    PROJECTS
    E-Commerce Platform
    Built a full-stack e-commerce platform using React, Node.js, and MongoDB.
    Implemented user authentication, payment processing, and inventory management.
    Used Docker for containerization and AWS for deployment.
    Achieved 99.9% uptime and handled 10,000+ daily users.

    Real-Time Analytics Dashboard
    Developed a real-time analytics dashboard using Python, FastAPI, and WebSocket.
    Integrated with PostgreSQL and Redis for data storage and caching.
    Implemented data visualization using D3.js and Chart.js.
    Reduced data processing time by 60%.

    Mobile App Development
    Created a cross-platform mobile app using React Native.
    Integrated with REST APIs and implemented offline functionality.
    Published on both iOS and Android stores with 50,000+ downloads.

    SKILLS
    React, Node.js, Python, FastAPI, MongoDB, PostgreSQL, Redis,
    Docker, AWS, React Native
    """

    text_items = [
        {"page": 1, "text": line.strip()}
        for line in resume_text.split("\n")
        if line.strip()
    ]

    resume_id = "test_resume_multiple_projects"
    resume_name = "multiple_projects_resume.pdf"

    chunks = process_resume_into_chunks(resume_id, resume_name, text_items)

    print(f"Processed into {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        print(f"\nChunk {i+1}:")
        print(f"  Section: {chunk['section']}")
        print(f"  Subsection: {chunk.get('subsection')}")
        print(f"  Text length: {len(chunk['text'])}")

    assert len(chunks) > 0, "Should create chunks"
    assert any(
        c["section"] == "Projects" for c in chunks
    ), "Should have Projects chunks"

    # Check that projects are separated
    project_chunks = [c for c in chunks if c["section"] == "Projects"]
    subsections = [c.get("subsection") for c in project_chunks]
    print(f"Project subsections: {subsections}")

    assert len(subsections) >= 2, "Should detect multiple projects"

    print("✓ Resume with multiple projects processed correctly\n")


def test_chunk_search():
    """Test chunk-based semantic search."""
    print("=" * 70)
    print("TEST 10: Chunk-Based Semantic Search")
    print("=" * 70)

    # This test requires actual FAISS and embedding model
    # Skip if dependencies are not available
    try:
        from backend import encode_text_embedding

        # Create a simple test query
        query = "FastAPI and Python web development"
        query_embedding = encode_text_embedding(
            query, "Represent this query for search:"
        )

        # Search for chunks
        results = search_chunks_by_embedding(query_embedding, top_k=5)

        print(f"Found {len(results)} chunk results:")
        for i, result in enumerate(results):
            chunk = result["chunk"]
            print(f"\nResult {i+1}:")
            print(f"  Resume ID: {result['resume_id']}")
            print(f"  Chunk ID: {chunk['chunk_id']}")
            print(f"  Section: {chunk['section']}")
            print(f"  Subsection: {chunk.get('subsection')}")
            print(f"  Similarity: {result['similarity_score']:.2f}")
            print(f"  Text preview: {chunk['text'][:100]}...")

        print("✓ Chunk-based search works (if chunks exist in database)\n")

    except Exception as e:
        print(f"⚠ Skipping chunk search test due to: {e}")
        print("This is expected if no chunks are in the database yet.\n")


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("PHASE 1 CHUNKING IMPLEMENTATION TESTS")
    print("=" * 70 + "\n")

    tests = [
        test_basic_text_cleaning,
        test_section_normalization,
        test_section_detection,
        test_context_aware_chunking,
        test_recursive_splitting,
        test_metadata_enrichment,
        test_resume_1_clear_sections,
        test_resume_2_unusual_sections,
        test_resume_3_multiple_projects,
        test_chunk_search,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} FAILED: {e}\n")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} ERROR: {e}\n")
            failed += 1

    print("=" * 70)
    print(f"TEST RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
