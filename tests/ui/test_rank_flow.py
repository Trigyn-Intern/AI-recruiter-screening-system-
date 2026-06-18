import pytest

@pytest.mark.skip(reason="Requires Ollama and full ranking pipeline")
def test_ranking_flow(page):
    page.goto("http://localhost:8501", timeout=60000)