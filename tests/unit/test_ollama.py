from jsonschema import validate

from backend import (
    CANDIDATE_DETAIL_SCHEMA,
    CANDIDATE_GRADING_SCHEMA,
    DEFAULT_CANDIDATE_DETAIL_PROMPT_TEMPLATE,
    DEFAULT_CANDIDATE_GRADING_PROMPT_TEMPLATE,
    DEFAULT_EXPERIENCE_TIMELINE_PROMPT_TEMPLATE,
    DEFAULT_CANDIDATE_SNAPSHOT_PROMPT_TEMPLATE,
    DEFAULT_OLLAMA_MODEL,
    CLAUDE_MODEL_OPTIONS,
    GEMINI_RESUME_SKILL_MODEL,
    GEMINI_MODEL_OPTIONS,
    JD_RESPONSE_SCHEMA,
    JD_SCHEMA,
    OLLAMA_MODEL_OPTIONS,
    DEFAULT_JD_PROMPT_TEMPLATE,
    analyze_candidate_detail,
    analyze_candidate_grading,
    get_resume_skill_profile,
    get_model_options,
    is_complete_resume_skill_profile,
    normalize_configuration,
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


def test_get_model_options_returns_claude_models():
    result = get_model_options("Claude")

    assert result == CLAUDE_MODEL_OPTIONS
    assert "claude-haiku-4-5" in result


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
        "additional_insights",
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


def test_candidate_detail_schema_requires_display_fields():
    assert CANDIDATE_DETAIL_SCHEMA["required"] == [
        "matching_skills",
        "missing_skills",
        "justification",
    ]


def test_candidate_grading_schema_requires_display_fields():
    assert CANDIDATE_GRADING_SCHEMA["required"] == [
        "grade_percentage",
        "criteria_scores",
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
        side_effect=[
            {
                "matching_skills": ["Python", "SQL"],
                "missing_skills": ["AWS"],
                "justification": "Strong Python and SQL match. AWS is missing.",
            },
            {
                "total_experience": "Not Found",
                "timeline": [],
            },
            {
                "candidate_name": "Python Candidate",
                "likely_role": "Python Developer",
                "current_title": "Python Developer",
                "current_company": "Not Found",
                "location": "Not Found",
                "total_experience": "Not Found",
            },
            {
                "grade_percentage": 84,
                "criteria_scores": {
                    "skill_gap": 70,
                    "years_experience": 60,
                    "project_experience": 80,
                    "education": 75,
                    "seniority": 65,
                },
                "summary": "Gemini grading summary.",
                "strengths": ["Python and SQL"],
                "concerns": ["AWS missing"],
            },
        ],
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
    assert result["candidate_snapshot"]["candidate_name"] == "Python Candidate"
    assert result["candidate_grading"]["source"] == "Gemini"
    assert mock_ai.call_count >= 3


def test_analyze_candidate_detail_uses_cache(mocker):
    cached_result = {
        "matching_skills": ["Python"],
        "missing_skills": [],
        "justification": "Cached justification.",
        "candidate_grading": {
            "grade": "B",
            "grade_percentage": 80,
            "criteria_scores": {
                "skill_gap": 80,
                "years_experience": 80,
                "project_experience": 80,
                "education": 80,
                "seniority": 80,
            },
            "summary": "Cached Gemini grading.",
            "strengths": ["Python"],
            "concerns": [],
            "source": "Gemini",
        },
    }
    mocker.patch("backend.get_selected_provider", return_value="Gemini")
    mocker.patch("backend.get_selected_model", return_value="gemini-2.5-flash")
    mocker.patch(
        "backend.get_ai_cache",
        return_value={
            (
                "candidate_detail_with_grading_v12|Gemini|gemini-2.5-flash|90|"
                f"resume text|job text|{DEFAULT_CANDIDATE_DETAIL_PROMPT_TEMPLATE}|"
                f"{DEFAULT_EXPERIENCE_TIMELINE_PROMPT_TEMPLATE}|"
                f"{DEFAULT_CANDIDATE_SNAPSHOT_PROMPT_TEMPLATE}|"
                '{"education": 5, "project_experience": 15, '
                '"seniority": 10, "skill_gap": 50, '
                '"years_experience": 20}'
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


def test_cached_fallback_grading_refreshes_with_gemini(mocker):
    cached_result = {
        "matching_skills": ["Python"],
        "missing_skills": ["AWS"],
        "justification": "Cached justification.",
        "candidate_grading": {
            "grade": "C",
            "grade_percentage": 55,
            "criteria_scores": {
                "skill_gap": 55,
                "years_experience": 55,
                "project_experience": 55,
                "education": 55,
                "seniority": 55,
            },
            "summary": "Fallback summary.",
            "strengths": ["Python"],
            "concerns": ["AWS"],
            "source": "local_fallback",
        },
    }
    mocker.patch("backend.get_selected_provider", return_value="Gemini")
    mocker.patch("backend.get_selected_model", return_value="gemini-2.5-flash")
    mocker.patch.dict("backend.RUNTIME_STATE", {"skip_gemini_grading": False})
    mocker.patch(
        "backend.get_ai_cache",
        return_value={
            (
                "candidate_detail_with_grading_v11|Gemini|gemini-2.5-flash|90|"
                f"resume text|job text|{DEFAULT_CANDIDATE_DETAIL_PROMPT_TEMPLATE}|"
                f"{DEFAULT_EXPERIENCE_TIMELINE_PROMPT_TEMPLATE}|"
                f"{DEFAULT_CANDIDATE_SNAPSHOT_PROMPT_TEMPLATE}|"
                '{"education": 5, "project_experience": 15, '
                '"seniority": 10, "skill_gap": 50, '
                '"years_experience": 20}'
            ): cached_result,
        },
    )
    mocker.patch(
        "backend.safe_ai_json",
        return_value={
            "grade_percentage": 82,
            "criteria_scores": {
                "skill_gap": 70,
                "years_experience": 80,
                "project_experience": 100,
                "education": 60,
                "seniority": 90,
            },
            "summary": "Gemini grading summary.",
            "strengths": ["Python experience"],
            "concerns": ["AWS is unclear"],
        },
    )

    result = analyze_candidate_detail(
        "resume text",
        "job text",
        90,
        model_name="gemini-2.5-flash",
    )

    assert result["candidate_grading"]["grade_percentage"] == 82
    assert result["candidate_grading"]["source"] == "Gemini"


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
        "backend.safe_ai_json",
        return_value={
            "grade": "Not Found",
            "summary": "Candidate grading could not be generated.",
            "strengths": [],
            "concerns": [],
        },
    )
    mocker.patch("backend.get_ai_cache", return_value={})
    mocker.patch("backend.get_persistent_candidate_grading", return_value=None)

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


def test_candidate_grading_uses_persistent_gemini_cache(mocker):
    cached_grading = {
        "grade": "A",
        "grade_percentage": 90,
        "criteria_scores": {
            "skill_gap": 90,
            "years_experience": 90,
            "project_experience": 90,
            "education": 90,
            "seniority": 90,
        },
        "summary": "Cached Gemini grading.",
        "strengths": ["Strong Python"],
        "concerns": ["AWS unclear"],
        "source": "Gemini",
    }
    mocker.patch("backend.get_ai_cache", return_value={})
    mocker.patch(
        "backend.get_persistent_candidate_grading",
        return_value=cached_grading,
    )
    mock_ai = mocker.patch("backend.safe_ai_json")

    result = analyze_candidate_grading(
        "Python resume",
        "Python job",
        ["Python"],
        [],
        provider="Gemini",
        model_name="gemini-2.5-flash",
    )

    assert result["grade_percentage"] == cached_grading["grade_percentage"]
    assert result["weights"] == {
        "skill_gap": 50,
        "years_experience": 20,
        "project_experience": 15,
        "education": 5,
        "seniority": 10,
    }
    mock_ai.assert_not_called()


def test_candidate_grading_saves_successful_gemini_result(mocker):
    mocker.patch("backend.get_ai_cache", return_value={})
    mocker.patch("backend.get_persistent_candidate_grading", return_value=None)
    mock_save = mocker.patch("backend.save_persistent_candidate_grading")
    mocker.patch(
        "backend.safe_ai_json",
        return_value={
            "grade": "B",
            "grade_percentage": 80,
            "criteria_scores": {
                "skill_gap": 50,
                "years_experience": 70,
                "project_experience": 90,
                "education": 60,
                "seniority": 80,
            },
            "summary": "Gemini grading summary.",
            "strengths": ["Python experience"],
            "concerns": ["AWS unclear"],
        },
    )

    result = analyze_candidate_grading(
        "Python resume",
        "Python and AWS job",
        ["Python"],
        ["AWS"],
        provider="Gemini",
        model_name="gemini-2.5-flash",
    )

    assert result["grade"] == "B"
    assert result["source"] == "Gemini"
    mock_save.assert_called_once()


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
