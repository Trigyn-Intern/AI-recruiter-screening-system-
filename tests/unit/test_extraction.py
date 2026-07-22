import io
from backend import extract_text


def test_unknown_extension():
    fake = io.BytesIO(b"abc")
    fake.name = "test.exe"

    result = extract_text(fake)

    assert result == ""
