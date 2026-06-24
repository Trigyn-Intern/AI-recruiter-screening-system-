import pytest


pytestmark = pytest.mark.skip(
    reason="Requires React dev server on http://localhost:5173"
)


def test_resume_upload(page):
    page.goto("http://localhost:5173", timeout=60000)

    page.wait_for_selector("input[type='file']", timeout=60000)

    page.set_input_files(
        "input[type='file']",
        "tests/data/sample_resume.pdf"
    )

    page.wait_for_timeout(5000)

    content = page.content().lower()

    assert (
        "analysis" in content
        or "score" in content
        or "rank" in content
        or "candidate" in content
    )
