import pytest

@pytest.mark.skip(
    reason=(
        "Requires React dev server on http://localhost:5173 and "
        "FastAPI on http://127.0.0.1:8000"
    )
)
def test_ranking_flow(page):
    page.goto("http://localhost:5173", timeout=60000)
