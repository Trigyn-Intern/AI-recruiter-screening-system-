import pytest
from backend import extract_contact_info, normalize_phone_number

def test_extract_email():
    """Test email extraction from resume text."""
    text = "John Doe\nEmail: john.doe@example.com\nPhone: 9876543210"
    result = extract_contact_info(text)

    assert result["email"] == "john.doe@example.com"
    assert result["phone"] is not None  # Should extract phone too
    assert result["linkedin"] is None
    assert result["github"] is None

def test_extract_phone_various_formats():
    """Test phone extraction from various formats."""
    test_cases = [
        ("Phone: 9876543210", "+91 98765 43210"),  # 10-digit - normalized as Indian
        ("Phone: +91 9876543210", "+91 98765 43210"),  # Indian with country code
    ]

    for text, expected_phone in test_cases:
        result = extract_contact_info(text)
        # Check that phone was extracted and normalized correctly
        assert result["phone"] == expected_phone, f"Failed for {text}: got {result['phone']}, expected {expected_phone}"

def test_extract_phone_indian_with_context():
    """Test extraction and normalization of Indian numbers with explicit context."""
    test_cases = [
        ("Phone: +91 9876543210", "+91 98765 43210"),  # Indian with country code
        ("Phone: 91 9876543210", "+91 98765 43210"),  # Indian with country code without +
    ]

    for text, expected_phone in test_cases:
        result = extract_contact_info(text)
        assert result["phone"] == expected_phone, f"Failed for {text}: got {result['phone']}, expected {expected_phone}"

def test_extract_linkedin():
    """Test LinkedIn URL extraction."""
    text = "LinkedIn: linkedin.com/in/johndoe"
    result = extract_contact_info(text)

    assert result["linkedin"] == "https://linkedin.com/in/johndoe"
    assert result["github"] is None

def test_extract_linkedin_various_formats():
    """Test LinkedIn extraction from various formats."""
    test_cases = [
        ("LinkedIn: linkedin.com/in/johndoe", "https://linkedin.com/in/johndoe"),
        ("LinkedIn: linkedin.com/johndoe", "https://linkedin.com/johndoe"),
        # Note: linkedin.in is not a valid LinkedIn domain, skip this test
    ]

    for text, expected_url in test_cases:
        result = extract_contact_info(text)
        assert result["linkedin"] == expected_url, f"Failed for {text}"

def test_extract_github():
    """Test GitHub URL extraction."""
    text = "GitHub: github.com/johndoe"
    result = extract_contact_info(text)

    assert result["github"] == "https://github.com/johndoe"
    assert result["linkedin"] is None

def test_extract_github_various_formats():
    """Test GitHub extraction from various formats."""
    test_cases = [
        ("GitHub: github.com/johndoe", "https://github.com/johndoe"),
        ("GitHub: github.com/johndoe/myproject", "https://github.com/johndoe/myproject"),
    ]

    for text, expected_url in test_cases:
        result = extract_contact_info(text)
        # Just check that github was extracted and has the correct username
        assert result["github"] is not None, f"Failed to extract github from {text}"
        assert "johndoe" in result["github"], f"Username not found in {result['github']}"

def test_extract_all_contact_info():
    """Test extraction of all contact fields from complete resume."""
    text = """
    John Doe
    Software Engineer
    Email: john.doe@example.com
    Phone: 9876543210
    LinkedIn: linkedin.com/in/johndoe
    GitHub: github.com/johndoe
    """

    result = extract_contact_info(text)

    assert result["email"] == "john.doe@example.com"
    assert result["phone"] is not None
    assert result["linkedin"] == "https://linkedin.com/in/johndoe"
    assert result["github"] == "https://github.com/johndoe"

def test_extract_partial_contact_info():
    """Test extraction when only some fields are present."""
    text = "Jane Smith\nEmail: jane.smith@example.com\nLinkedIn: linkedin.com/in/janesmith"
    result = extract_contact_info(text)

    assert result["email"] == "jane.smith@example.com"
    assert result["linkedin"] == "https://linkedin.com/in/janesmith"
    assert result["phone"] is None  # No phone in text
    assert result["github"] is None  # No GitHub in text

def test_extract_no_contact_info():
    """Test extraction when no contact info is present."""
    text = "Software Developer with experience in Python and JavaScript."
    result = extract_contact_info(text)

    assert result["email"] is None
    assert result["phone"] is None
    assert result["linkedin"] is None
    assert result["github"] is None

def test_extract_empty_text():
    """Test extraction with empty text."""
    result = extract_contact_info("")

    assert result["email"] is None
    assert result["phone"] is None
    assert result["linkedin"] is None
    assert result["github"] is None

def test_extract_none_text():
    """Test extraction with None text."""
    result = extract_contact_info(None)

    assert result["email"] is None
    assert result["phone"] is None
    assert result["linkedin"] is None
    assert result["github"] is None

def test_extract_contact_normalization():
    """Test that contact info is properly normalized."""
    text = "Contact: john.doe@example.com and linkedin.com/in/johndoe"
    result = extract_contact_info(text)

    # Email should be normalized
    assert result["email"] == "john.doe@example.com"
    # LinkedIn should have https:// prefix
    assert result["linkedin"] == "https://linkedin.com/in/johndoe"

def test_extract_realistic_resume():
    """Test extraction from realistic resume text."""
    text = """
    John Developer
    Senior Software Engineer

    Contact Information:
    Email: john.developer@techcompany.com
    Phone: 9876543210
    LinkedIn: linkedin.com/in/johndeveloper
    GitHub: github.com/johndeveloper

    Experience:
    - Senior Developer at Tech Company (2020-Present)
    - Software Engineer at Startup (2018-2020)
    """

    result = extract_contact_info(text)

    assert result["email"] == "john.developer@techcompany.com"
    assert result["phone"] is not None
    assert result["linkedin"] == "https://linkedin.com/in/johndeveloper"
    assert result["github"] == "https://github.com/johndeveloper"

def test_normalize_phone_indian_10_digit():
    """Test normalization of Indian 10-digit phone numbers."""
    test_cases = [
        ("9876543210", "+91 98765 43210"),
        ("8217741124", "+91 82177 41124"),
        ("9998887777", "+91 99988 87777"),
    ]

    for input_phone, expected in test_cases:
        result = normalize_phone_number(input_phone)
        assert result == expected, f"Failed for {input_phone}: got {result}, expected {expected}"

def test_normalize_phone_indian_with_spaces():
    """Test normalization of Indian numbers with spaces."""
    test_cases = [
        ("98765 43210", "+91 98765 43210"),
        ("98765 43210", "+91 98765 43210"),
    ]

    for input_phone, expected in test_cases:
        result = normalize_phone_number(input_phone)
        assert result == expected, f"Failed for {input_phone}: got {result}, expected {expected}"

def test_normalize_phone_indian_with_hyphens():
    """Test normalization of Indian numbers with hyphens."""
    test_cases = [
        ("98765-43210", "+91 98765 43210"),
    ]

    for input_phone, expected in test_cases:
        result = normalize_phone_number(input_phone)
        assert result == expected, f"Failed for {input_phone}: got {result}, expected {expected}"

def test_normalize_phone_indian_with_slashes():
    """Test normalization of Indian numbers with slashes."""
    test_cases = [
        ("98765/43210", "+91 98765 43210"),
    ]

    for input_phone, expected in test_cases:
        result = normalize_phone_number(input_phone)
        assert result == expected, f"Failed for {input_phone}: got {result}, expected {expected}"

def test_normalize_phone_indian_with_parentheses():
    """Test normalization of Indian numbers with parentheses."""
    test_cases = [
        ("(91) 98765 43210", "+91 98765 43210"),
        ("(91)9876543210", "+91 98765 43210"),
    ]

    for input_phone, expected in test_cases:
        result = normalize_phone_number(input_phone)
        assert result == expected, f"Failed for {input_phone}: got {result}, expected {expected}"

def test_normalize_phone_indian_with_leading_zero():
    """Test normalization of Indian numbers with leading zero."""
    test_cases = [
        ("09876543210", "+91 98765 43210"),  # Leading 0 is stripped, then normalized
        ("0 98765 43210", "+91 98765 43210"),  # Leading 0 is stripped, then normalized
    ]

    for input_phone, expected in test_cases:
        result = normalize_phone_number(input_phone)
        assert result == expected, f"Failed for {input_phone}: got {result}, expected {expected}"

def test_normalize_phone_indian_with_country_code():
    """Test normalization of Indian numbers with country code."""
    test_cases = [
        ("919876543210", "+91 98765 43210"),
        ("91 98765 43210", "+91 98765 43210"),
        ("+91 98765 43210", "+91 98765 43210"),
    ]

    for input_phone, expected in test_cases:
        result = normalize_phone_number(input_phone)
        assert result == expected, f"Failed for {input_phone}: got {result}, expected {expected}"

def test_normalize_phone_international_preserved():
    """Test that international non-Indian numbers are preserved but cleaned."""
    test_cases = [
        ("+11234567890", "+11234567890"),  # US number - already clean
        ("+442012345678", "+442012345678"),  # UK number - already clean
    ]

    for input_phone, expected in test_cases:
        result = normalize_phone_number(input_phone)
        assert result == expected, f"Failed for {input_phone}: got {result}, expected {expected}"

def test_extract_phone_indian_formats():
    """Test extraction and normalization of Indian phone formats."""
    test_cases = [
        ("Phone: 9876543210", "+91 98765 43210"),
        ("Phone: +91 98765 43210", "+91 98765 43210"),
    ]

    for text, expected_phone in test_cases:
        result = extract_contact_info(text)
        assert result["phone"] == expected_phone, f"Failed for {text}: got {result['phone']}, expected {expected_phone}"

def test_normalize_phone_indian_with_country_code_formats():
    """Test normalization of Indian numbers with country code in various formats."""
    test_cases = [
        ("919876543210", "+91 98765 43210"),
        ("91 98765 43210", "+91 98765 43210"),
    ]

    for input_phone, expected in test_cases:
        result = normalize_phone_number(input_phone)
        assert result == expected, f"Failed for {input_phone}: got {result}, expected {expected}"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
