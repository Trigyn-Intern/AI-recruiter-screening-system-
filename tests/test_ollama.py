from app import safe_ollama_json, JD_SCHEMA

def test_safe_ollama_json_success(mocker):

    mock_response = {
        "message": {
            "content": '''
            {
                "experience": "3 years",
                "primary_skills": ["Python"],
                "secondary_skills": ["SQL"],
                "education": "BTech"
            }
            '''
        }
    }

    mocker.patch(
        "app.ollama.chat",
        return_value=mock_response
    )

    fallback = {}

    result = safe_ollama_json(
        "test prompt",
        JD_SCHEMA,
        fallback
    )

    assert result["experience"] == "3 years"


def test_safe_ollama_json_invalid_schema(mocker):

    mock_response = {
        "message": {
            "content": '{"wrong":"format"}'
        }
    }

    mocker.patch(
        "app.ollama.chat",
        return_value=mock_response
    )

    fallback = {"fallback": True}

    result = safe_ollama_json(
        "test",
        JD_SCHEMA,
        fallback
    )

    assert result == fallback