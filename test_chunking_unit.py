"""
Unit tests for production resume text and section functions.
"""

from backend import clean_resume_text, detect_resume_sections, normalize_section_heading


def test_cleaning():
    print("Testing text cleaning...")
    dirty = """
    Test


    Multiple    spaces.


    """
    cleaned = clean_resume_text(dirty)
    print(f"Result: {repr(cleaned)}")
    assert "\n\n\n" not in cleaned
    print("PASS: Text cleaning works")


def test_normalization():
    print("Testing section normalization...")
    tests = [
        ("SKILLS", "Skills"),
        ("TECHNICAL SKILLS", "Skills"),
        ("WORK EXPERIENCE", "Experience"),
        ("PROFESSIONAL EXPERIENCE", "Experience"),
        ("PROJECTS", "Projects"),
        ("EDUCATION", "Education"),
        ("CERTIFICATIONS", "Certifications"),
        ("ACHIEVEMENTS", "Achievements"),
        ("PUBLICATIONS", "Publications"),
        ("RESEARCH", "Research"),
        ("SUMMARY", "Summary"),
        ("PROFILE", "Summary"),
        ("INTERNSHIPS", "Experience"),
        ("Project Duration: 6 Months", None),
        ("TECHNICAL SKILLS AND EXPERIENCE", None),
        ("Unknown Heading", None),
    ]
    for inp, expected in tests:
        result = normalize_section_heading(inp)
        print(f"  {inp} -> {result}")
        assert result == expected
    print("PASS: Section normalization works")

def test_blacklist():
    print("Testing subsection normalization...")
    labels = [
        "Project Duration: 6 Months", "Project Description:",
        "Project Name", "Responsibilities", "Environment: SharePoint",
        "Technologies", "Team Size", "Role", "Client", "Location",
    ]
    sections = detect_resume_sections([{"text": label, "page": 1} for label in labels])
    assert sections == []
    print("PASS: Subsection labels are not headings")


def test_detection_with_blacklist():
    print("Testing section detection with blacklist...")

    # Test data with false positives
    text_items = [
        {'text': 'SUMMARY'},
        {'text': 'SKILLS'},
        {'text': 'PROJECTS'},
        {'text': 'Project Duration: 6 Months'},  # Should NOT be detected as section
        {'text': 'Project Description:'},  # Should NOT be detected as section
        {'text': 'Environment: SharePoint'},  # Should NOT be detected as section
        {'text': '3.Project Name: Delaval'},  # Should NOT be detected as section (numbered project name - allowed)
        {'text': 'Project: Tax Management System'},  # Should NOT be detected as section (blacklisted)
    ]

    sections = detect_resume_sections(text_items)

    print(f"  Detected sections: {[s['section'] for s in sections]}")

    # Should only detect Summary, Skills, Projects
    expected_sections = ['Summary', 'Skills', 'Projects']
    detected_sections = [s['section'] for s in sections]

    for exp in expected_sections:
        assert exp in detected_sections, f"Expected section {exp} not detected"

    # Ensure false positives are not detected
    assert 'Project Duration' not in detected_sections, "Project Duration should not be a section"
    assert 'Project Description' not in detected_sections, "Project Description should not be a section"
    assert 'Environment' not in detected_sections, "Environment should not be a section"
    assert 'Project Name' not in detected_sections, "Project Name should not be a section"
    assert 'Project' not in detected_sections, "Project should not be a section (when it's alone)"
    assert 'Tax Management System' not in detected_sections, "Tax Management System should not be a section"

    print("PASS: Section detection with blacklist works")

def test_numbered_project_names():
    print("Testing numbered project name preservation...")

    # Test that numbered project names are NOT blacklisted
    text_items = [
        {'text': 'PROJECTS'},
        {'text': '3.Project Name: Delaval'},
        {'text': '4.Project Name : Mercedes Benz'},
        {'text': '5.Project Name: Avaya Intranet Project'},
    ]

    sections = detect_resume_sections(text_items)
    detected_sections = [s['section'] for s in sections]

    print(f"  Detected sections: {detected_sections}")

    # Numbered project names should NOT be detected as sections
    assert 'Project Name' not in detected_sections, "Numbered project names should not be detected as sections"
    assert 'Projects' in detected_sections, "Projects section should be detected"

    print("PASS: Numbered project names are preserved")


def main():
    print("\n=== UNIT TESTS ===\n")
    test_cleaning()
    test_normalization()
    test_blacklist()
    test_detection_with_blacklist()
    test_numbered_project_names()
    print("\n=== ALL TESTS PASSED ===\n")


if __name__ == "__main__":
    main()
