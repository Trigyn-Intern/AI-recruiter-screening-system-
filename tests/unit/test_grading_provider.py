import pytest
from backend import analyze_candidate_grading


def test_grading_respects_provider_ollama(mocker):
    """Test that grading uses safe_ai_json with Ollama provider when provider='Ollama'."""
    # Mock safe_ai_json to verify it's called with correct provider
    mock_safe_ai_json = mocker.patch("backend.safe_ai_json", return_value={
        "grade": "A",
        "summary": "Strong match",
        "strengths": ["Python"],
        "concerns": [],
    })
    
    mocker.patch("backend.get_ai_cache", return_value={})
    mocker.patch("backend.get_selected_provider", return_value="Ollama")
    mocker.patch("backend.get_selected_model", return_value="llama3.2")
    
    # Call grading with Ollama provider
    result = analyze_candidate_grading(
        "Built Python APIs.",
        "Need Python.",
        ["Python"],
        [],
        provider="Ollama",
        model_name="llama3.2",
    )
    
    # Verify safe_ai_json was called with provider="Ollama"
    mock_safe_ai_json.assert_called_once()
    call_kwargs = mock_safe_ai_json.call_args.kwargs
    assert call_kwargs["provider"] == "Ollama", "Grading should use Ollama provider"
    assert call_kwargs["model_name"] == "llama3.2", "Grading should use llama3.2 model"
    
    # Verify result structure
    assert result["grade"] == "A"


def test_grading_respects_provider_gemini(mocker):
    """Test that grading uses safe_ai_json with Gemini provider when provider='Gemini'."""
    # Mock safe_ai_json to verify it's called with correct provider
    mock_safe_ai_json = mocker.patch("backend.safe_ai_json", return_value={
        "grade": "B",
        "summary": "Good match",
        "strengths": ["Python"],
        "concerns": ["AWS"],
    })
    
    mocker.patch("backend.get_ai_cache", return_value={})
    mocker.patch("backend.get_selected_provider", return_value="Gemini")
    mocker.patch("backend.get_selected_model", return_value="gemini-2.5-flash")
    
    # Call grading with Gemini provider
    result = analyze_candidate_grading(
        "Built Python APIs.",
        "Need Python and AWS.",
        ["Python"],
        ["AWS"],
        provider="Gemini",
        model_name="gemini-2.5-flash",
    )
    
    # Verify safe_ai_json was called with provider="Gemini"
    mock_safe_ai_json.assert_called_once()
    call_kwargs = mock_safe_ai_json.call_args.kwargs
    assert call_kwargs["provider"] == "Gemini", "Grading should use Gemini provider"
    assert call_kwargs["model_name"] == "gemini-2.5-flash", "Grading should use gemini-2.5-flash model"
    
    # Verify result structure
    assert result["grade"] == "B"


def test_grading_defaults_to_selected_provider(mocker):
    """Test that grading defaults to get_selected_provider when provider=None."""
    # Mock safe_ai_json
    mock_safe_ai_json = mocker.patch("backend.safe_ai_json", return_value={
        "grade": "A",
        "summary": "Strong match",
        "strengths": ["Python"],
        "concerns": [],
    })
    
    mocker.patch("backend.get_ai_cache", return_value={})
    mocker.patch("backend.get_selected_provider", return_value="Ollama")
    mocker.patch("backend.get_selected_model", return_value="llama3.2")
    
    # Call grading without provider (should default)
    result = analyze_candidate_grading(
        "Built Python APIs.",
        "Need Python.",
        ["Python"],
        [],
    )
    
    # Verify safe_ai_json was called with default provider
    mock_safe_ai_json.assert_called_once()
    call_kwargs = mock_safe_ai_json.call_args.kwargs
    assert call_kwargs["provider"] == "Ollama", "Grading should default to Ollama"
    assert call_kwargs["model_name"] == "llama3.2", "Grading should default to llama3.2"
