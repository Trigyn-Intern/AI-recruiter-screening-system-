"""
Unit test for individual chunking functions without backend dependencies.
"""

import re


def clean_resume_text(text):
    """Clean resume text while preserving structure."""
    if not text:
        return ""

    # Remove excessive blank lines (more than 2 consecutive)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)

    # Normalize whitespace within lines
    lines = []
    for line in text.split('\n'):
        # Remove leading/trailing whitespace but preserve internal spacing
        cleaned = line.strip()
        if cleaned:
            lines.append(cleaned)

    return '\n'.join(lines)


def normalize_section_heading(heading):
    """Normalize section heading to standard form."""
    if not heading:
        return None

    # Normalize: lowercase, remove extra spaces, remove special chars
    normalized = re.sub(r'[^a-zA-Z\s]', '', heading.lower().strip())

    # Section mapping rules
    section_mappings = {
        'skills': 'Skills',
        'technical skills': 'Skills',
        'experience': 'Experience',
        'work experience': 'Experience',
        'professional experience': 'Experience',
        'projects': 'Projects',
        'education': 'Education',
        'certifications': 'Certifications',
        'summary': 'Summary',
    }

    # Try exact match first
    if normalized in section_mappings:
        return section_mappings[normalized]

    # Try partial match
    for key, value in section_mappings.items():
        if key in normalized or normalized in key:
            return value

    return heading.strip().title()


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
        ("WORK EXPERIENCE", "Experience"),
        ("Work Experience", "Experience"),
        ("SKILLS", "Skills"),
    ]
    for inp, expected in tests:
        result = normalize_section_heading(inp)
        print(f"  {inp} -> {result}")
        assert result == expected
    print("PASS: Section normalization works")


def main():
    print("\n=== UNIT TESTS ===\n")
    test_cleaning()
    test_normalization()
    print("\n=== ALL TESTS PASSED ===\n")


if __name__ == "__main__":
    main()
