"""Legacy ranking flow placeholder - see test_scenario_matrix.py."""
import pytest

@pytest.mark.skip(reason="Covered by tests/ui/test_scenario_matrix.py")
def test_ranking_flow(page):
    page.goto("http://localhost:8501", timeout=60000)