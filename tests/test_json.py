from backend import safe_json_extract

def test_valid_json():
    text = 'hello {"a": 1} world'

    result = safe_json_extract(text)

    assert result == {"a": 1}


def test_invalid_json():
    text = "not json"

    result = safe_json_extract(text)

    assert result is None