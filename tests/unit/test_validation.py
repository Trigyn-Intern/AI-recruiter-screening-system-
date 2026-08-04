import io

from backend import validate_upload


def test_valid_pdf():
    fake_pdf = io.BytesIO(b"%PDF-1.4 test content")
    fake_pdf.name = "resume.pdf"

    valid, _ = validate_upload(fake_pdf)

    assert valid is True


def test_invalid_extension():
    fake_file = io.BytesIO(b"random")
    fake_file.name = "malware.exe"

    valid, msg = validate_upload(fake_file)

    assert valid is False
    assert "Unsupported" in msg


def test_fake_pdf():
    fake_pdf = io.BytesIO(b"NOTPDF")
    fake_pdf.name = "resume.pdf"

    valid, _ = validate_upload(fake_pdf)

    assert valid is False


def test_large_file():
    big_content = b"x" * (11 * 1024 * 1024)

    fake_file = io.BytesIO(big_content)
    fake_file.name = "large.pdf"

    valid, _ = validate_upload(fake_file)

    assert valid is False
