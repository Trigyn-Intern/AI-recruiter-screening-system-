from jsonschema import validate

from backend import (
    CANDIDATE_DETAIL_SCHEMA,
    CANDIDATE_GRADING_SCHEMA,
    DEFAULT_CANDIDATE_DETAIL_PROMPT_TEMPLATE,
    DEFAULT_CANDIDATE_GRADING_PROMPT_TEMPLATE,
    DEFAULT_OLLAMA_MODEL,
    GEMINI_RESUME_SKILL_MODEL,
    GEMINI_MODEL_OPTIONS,
    JD_RESPONSE_SCHEMA,
    JD_SCHEMA,
    OLLAMA_MODEL_OPTIONS,
    DEFAULT_JD_PROMPT_TEMPLATE,
    analyze_candidate_detail,
    analyze_candidate_grading,
    analyze_match_justification,
    get_resume_skill_profile,
    get_model_options,
    is_complete_resume_skill_profile,
    normalize_configuration,
    summarize_gemini_error,
    safe_ollama_json,
)

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
        "backend.ollama.chat",
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
        "backend.ollama.chat",
        return_value=mock_response
    )

    fallback = {"fallback": True}

    result = safe_ollama_json(
        "test",
        JD_SCHEMA,
        fallback
    )

    assert result == fallback


def test_get_model_options_includes_installed_and_recommended(mocker):
    mocker.patch(
        "backend.get_available_ollama_models",
        return_value=["custom-local-model", DEFAULT_OLLAMA_MODEL],
    )

    result = get_model_options("Ollama")

    assert result[0] == "custom-local-model"
    assert DEFAULT_OLLAMA_MODEL in result
    assert "qwen3" in result
    assert len(result) == len(set(result))


def test_get_model_options_uses_recommended_when_ollama_unavailable(mocker):
    mocker.patch(
        "backend.get_available_ollama_models",
        return_value=[],
    )

    assert get_model_options("Ollama") == OLLAMA_MODEL_OPTIONS


def test_get_model_options_returns_gemini_models():
    result = get_model_options("Gemini")

    assert result == GEMINI_MODEL_OPTIONS
    assert "gemini-3.5-flash" in result
    assert "gemini-2.5-flash" in result


def test_jd_response_schema_requires_display_fields():
    assert JD_RESPONSE_SCHEMA["required"] == [
        "experience",
        "primary_skills",
        "secondary_skills",
        "education",
    ]

    assert set(JD_RESPONSE_SCHEMA["properties"]) == {
        "experience",
        "primary_skills",
        "secondary_skills",
        "education",
    }


def test_jd_response_schema_allows_list_skills():
    validate(
        instance={
            "experience": "3 years",
            "primary_skills": ["Python", "SQL"],
            "secondary_skills": ["Docker"],
            "education": "BTech",
        },
        schema=JD_RESPONSE_SCHEMA,
    )


def test_analyze_match_justification_returns_summary(mocker):
    mocker.patch(
        "backend.safe_ai_json",
        return_value={
            "justification": (
                "Strong Python and SQL experience match the role. "
                "Cloud experience is less clear."
            ),
        },
    )

    result = analyze_match_justification(
        "Python SQL resume",
        "Python SQL cloud job",
        78.5,
        model_name="test-model",
    )

    assert "Strong Python" in result
    assert "Cloud experience" in result


def test_candidate_detail_schema_requires_display_fields():
    assert CANDIDATE_DETAIL_SCHEMA["required"] == [
        "matching_skills",
        "missing_skills",
        "justification",
    ]


def test_candidate_grading_schema_requires_display_fields():
    assert CANDIDATE_GRADING_SCHEMA["required"] == [
        "grade",
        "summary",
        "strengths",
        "concerns",
    ]


def test_analyze_candidate_detail_returns_skills_and_justification(mocker):
    mocker.patch("backend.get_selected_provider", return_value="Gemini")
    mocker.patch("backend.get_selected_model", return_value="gemini-2.5-flash")
    mocker.patch("backend.get_ai_cache", return_value={})
    mock_ai = mocker.patch(
        "backend.safe_ai_json",
        return_value={
            "matching_skills": ["Python", "SQL"],
            "missing_skills": ["AWS"],
            "justification": "Strong Python and SQL match. AWS is missing.",
        },
    )

    result = analyze_candidate_detail(
        "Python SQL resume",
        "Python SQL AWS job",
        81.25,
        model_name="gemini-2.5-flash",
    )

    assert result["matching_skills"] == ["Python", "SQL"]
    assert result["missing_skills"] == ["AWS"]
    assert "Strong Python" in result["justification"]
    mock_ai.assert_called_once()


def test_analyze_candidate_detail_uses_cache(mocker):
    cached_result = {
        "matching_skills": ["Python"],
        "missing_skills": [],
        "justification": "Cached justification.",
    }
    mocker.patch("backend.get_selected_provider", return_value="Gemini")
    mocker.patch("backend.get_selected_model", return_value="gemini-2.5-flash")
    mocker.patch(
        "backend.get_ai_cache",
        return_value={
            (
                "candidate_detail_with_grading_v1|Gemini|gemini-2.5-flash|90|"
                f"resume text|job text|{DEFAULT_CANDIDATE_DETAIL_PROMPT_TEMPLATE}"
            ): cached_result,
        },
    )
    mock_ai = mocker.patch("backend.safe_ai_json")

    result = analyze_candidate_detail(
        "resume text",
        "job text",
        90,
        model_name="gemini-2.5-flash",
    )

    assert result == cached_result
    mock_ai.assert_not_called()


def test_analyze_candidate_detail_falls_back_to_indexed_skills(mocker):
    mocker.patch("backend.get_selected_provider", return_value="Ollama")
    mocker.patch("backend.get_selected_model", return_value="llama3.2")
    mocker.patch("backend.get_ai_cache", return_value={})
    mocker.patch(
        "backend.safe_ai_json",
        return_value={
            "matching_skills": [],
            "missing_skills": [],
            "justification": "Justification could not be generated.",
        },
    )

    result = analyze_candidate_detail(
        "resume text",
        "Need Python, SQL, Docker, and FastAPI.",
        64.5,
        model_name="llama3.2",
        resume_skill_profile={
            "technical_skills": ["Python", "SQL"],
            "soft_skills": ["Communication"],
            "tools": ["Jira"],
            "domains": ["Recruiting"],
            "experience_summary": "Backend developer.",
            "skill_evidence": [
                {
                    "skill": "Python",
                    "evidence": "Built FastAPI services using Python.",
                    "source": "Payments project",
                }
            ],
        },
        provider="Ollama",
        job_skill_requirements={
            "primary_skills": "Python, SQL, Docker",
            "secondary_skills": "FastAPI",
        },
    )

    assert result["matching_skills"] == ["Python", "SQL"]
    assert result["missing_skills"] == ["Docker", "FastAPI"]
    assert "indexed resume skills" in result["justification"]
    assert result["matching_evidence"][0] == {
        "skill": "Python",
        "evidence": "Built FastAPI services using Python.",
        "source": "Payments project",
    }
    assert result["matching_evidence"][1]["source"] == (
        "Indexed experience summary"
    )


def test_candidate_detail_replaces_not_found_missing_skills(mocker):
    mocker.patch("backend.get_selected_provider", return_value="Gemini")
    mocker.patch("backend.get_selected_model", return_value="gemini-2.5-flash")
    mocker.patch("backend.get_ai_cache", return_value={})
    mocker.patch(
        "backend.safe_ai_json",
        return_value={
            "matching_skills": ["Python"],
            "missing_skills": ["Not Found"],
            "justification": "Python matches.",
        },
    )

    result = analyze_candidate_detail(
        "resume text",
        "Need Python, AWS, Docker.",
        70,
        model_name="gemini-2.5-flash",
        resume_skill_profile={
            "technical_skills": ["Python"],
            "soft_skills": [],
            "tools": [],
            "domains": [],
            "experience_summary": "Python developer.",
            "skill_evidence": [],
        },
        job_skill_requirements={
            "primary_skills": "Python, AWS, Docker",
        },
    )

    assert result["missing_skills"] == ["AWS", "Docker"]


def test_candidate_grading_falls_back_without_not_found(mocker):
    mocker.patch(
        "backend.safe_gemini_json",
        return_value={
            "grade": "Not Found",
            "summary": "Candidate grading could not be generated.",
            "strengths": [],
            "concerns": [],
        },
    )
    mocker.patch("backend.get_ai_cache", return_value={})

    result = analyze_candidate_grading(
        "Built Python APIs and deployed Docker projects.",
        "Need Python, Docker, AWS.",
        ["Python", "Docker"],
        ["AWS"],
    )

    assert result["grade"] in ["A", "B", "C", "D", "F"]
    assert result["grade"] != "Not Found"
    assert "does not use the generated match score" in result["summary"]
    assert result["strengths"]
    assert result["concerns"]


def test_summarize_gemini_quota_error():
    assert summarize_gemini_error("429 RESOURCE_EXHAUSTED details") == (
        "Gemini quota exhausted; local fallback used."
    )


def test_resume_skill_profile_cache_is_complete():
    assert is_complete_resume_skill_profile(
        {
            "technical_skills": [],
            "soft_skills": [],
            "tools": [],
            "domains": [],
            "experience_summary": "Summary",
            "skill_evidence": [],
        }
    )

    assert not is_complete_resume_skill_profile(
        {
            "technical_skills": [],
        }
    )


def test_get_resume_skill_profile_uses_cached_gemini_flash_data(mocker):
    cached_profile = {
        "technical_skills": ["Python"],
        "soft_skills": ["Communication"],
        "tools": ["Jira"],
        "domains": ["Recruiting"],
        "experience_summary": "Cached summary.",
        "skill_evidence": [
            {
                "skill": "Python",
                "evidence": "Python automation project.",
                "source": "Projects",
            }
        ],
    }
    mocker.patch(
        "backend.read_json_file",
        return_value={
            "resume-1": {
                "resume_id": "resume-1",
                "resume_name": "resume.pdf",
                "skills": cached_profile,
                "model": GEMINI_RESUME_SKILL_MODEL,
            }
        },
    )
    mock_gemini = mocker.patch("backend.safe_gemini_json")

    result = get_resume_skill_profile(
        "resume-1",
        "resume.pdf",
        "resume text",
    )

    assert result == cached_profile
    mock_gemini.assert_not_called()


def test_normalize_configuration_prefills_blank_prompts():
    result = normalize_configuration(
        {
            "ai_provider": "Gemini",
            "jd_prompt_template": "",
        }
    )

    assert result["ai_provider"] == "Gemini"
    assert result["jd_prompt_template"] == DEFAULT_JD_PROMPT_TEMPLATE
    assert (
        result["candidate_grading_prompt_template"]
        == DEFAULT_CANDIDATE_GRADING_PROMPT_TEMPLATE
    )
