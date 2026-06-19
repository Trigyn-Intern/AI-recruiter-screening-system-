"""Legacy UI smoke tests, kept for reference.

The new data-driven matrix in ``test_scenario_matrix.py`` covers upload,
JD input and the full ranking flow by running every entry in
``tests/data/scenarios.yaml``. These original tests are still useful for
quick smoke checks on a single happy path, so they are kept here but are
skipped automatically to avoid double-running the same scenario.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Covered by tests/ui/test_scenario_matrix.py")
def test_resume_upload(page):
    page.goto("http://localhost:8501", timeout=60000)

    page.wait_for_selector("input[type='file']", timeout=60000)

    page.set_input_files(
        "input[type='file']",
        "tests/data/sample_resume.pdf",
    )

    page.wait_for_timeout(5000)


@pytest.mark.skip(reason="Covered by tests/ui/test_scenario_matrix.py")
def test_job_description_input(page):
    page.goto("http://localhost:8501", timeout=60000)

    page.fill("textarea", "Python Developer with ML experience")
    page.wait_for_timeout(1000)