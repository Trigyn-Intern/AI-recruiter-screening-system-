from __future__ import annotations

import re
from pathlib import Path

import pytest


SCORE_PATTERN = re.compile(r"-?\d{1,3}(?:\.\d+)?")


# ---------------------------------------------------------------------------
# Streamlit-specific helpers
# ---------------------------------------------------------------------------

def _current_model(page) -> str:
    """Return the Ollama model currently selected in the Streamlit selectbox.

    Reads the ``aria-label`` of the hidden BaseWeb combobox, which has the
    shape ``Selected <model>. Ollama model``.
    """
    cb = page.locator("[data-testid=stSelectbox] input[role=combobox]").first
    aria = cb.get_attribute("aria-label") or ""
    # Strip the "Selected " prefix and the " Ollama model" suffix.
    if aria.startswith("Selected "):
        aria = aria[len("Selected "):]
    if aria.endswith(". Ollama model"):
        aria = aria[: -len(". Ollama model")]
    return aria.strip()


def _select_ollama_model(page, model_name: str) -> None:
    """Make sure the requested Ollama model is selected on the
    Configurations tab. Skips the dropdown if the model is already
    selected (a common case when consecutive scenarios use the same
    model)."""

    page.get_by_role("tab", name="Configurations").click()
    page.wait_for_timeout(800)

    cb = page.locator("[data-testid=stSelectbox] input[role=combobox]").first
    cb.wait_for(state="attached", timeout=15000)

    current = _current_model(page)
    if current == model_name or current.split(":", 1)[0] == model_name.split(":", 1)[0]:
        # Already on the right model; nothing to do.
        return

    cb.click()
    page.wait_for_timeout(800)

    option = page.locator("li[role=option]").filter(has_text=model_name).first
    option.wait_for(state="visible", timeout=10000)
    option.click()
    page.wait_for_timeout(600)


def _switch_to_analyzer(page) -> None:
    page.get_by_role("tab", name="Resume Analyzer").click()
    page.wait_for_timeout(500)


def _upload_resumes(page, resume_paths: list[Path]) -> None:
    file_input = page.locator(
        '[data-testid="stFileUploader"] input[type="file"]'
    )
    file_input.set_input_files([str(p) for p in resume_paths])
    page.wait_for_timeout(1500)


def _paste_jd(page, jd_text: str) -> None:
    textarea = page.locator('[data-testid="stTextArea"] textarea').first
    textarea.click()
    textarea.fill(jd_text)
    page.wait_for_timeout(500)
    # Streamlit text-areas only commit the value on Ctrl+Enter.
    page.keyboard.press("Control+Enter")
    page.wait_for_timeout(1500)


def _wait_for_dashboard(page, expected_rows: int, timeout_ms: int = 600000) -> None:
    """Block until the ranking dashboard shows the expected number of rows.

    The dashboard renders a Glide data grid; the row count is the number of
    ``[data-testid=stDataFrame] [data-testid^=glide-cell-1-]`` cells, i.e.
    the Resume Name column.
    """
    page.wait_for_selector("text=Candidate Ranking Dashboard", timeout=timeout_ms)

    page.wait_for_function(
        """([rows]) => {
            const cells = document.querySelectorAll(
                '[data-testid=stDataFrame] [data-testid^=glide-cell-1-]'
            );
            return cells.length >= rows;
        }""",
        arg=[expected_rows],
        timeout=timeout_ms,
    )


def _read_top_score_and_name(page, expected_rows: int) -> tuple[float, str]:
    """Read the top row of the ranking table.

    The glide data grid exposes cells as
    ``[data-testid=glide-cell-{col}-{row}]`` where col 1 is the Resume Name
    and col 2 is the Match Score (%).
    """
    raw = page.evaluate(
        """([rows]) => {
            const root = document.querySelector('[data-testid=stDataFrame]');
            if (!root) return null;
            const get = (col, row) => {
                const el = root.querySelector(
                    `[data-testid="glide-cell-${col}-${row}"]`
                );
                return el ? (el.textContent || '').trim() : '';
            };
            const out = [];
            for (let r = 0; r < rows; r++) {
                out.push({name: get(1, r), score: get(2, r)});
            }
            return out;
        }""",
        [expected_rows],
    )

    if not raw or not raw[0].get("name"):
        raise AssertionError(
            "Ranking grid is empty or has no Resume Name in row 0."
        )

    score_match = SCORE_PATTERN.search(raw[0]["score"] or "")
    if not score_match:
        raise AssertionError(
            f"Could not parse score from {raw[0]['score']!r}."
        )
    return float(score_match.group(0)), raw[0]["name"]


def _read_full_ranking(page, expected_rows: int) -> list[dict]:
    """Return [{rank, name, score}, ...] for the dashboard grid."""

    return page.evaluate(
        """([rows]) => {
            const root = document.querySelector('[data-testid=stDataFrame]');
            if (!root) return [];
            const get = (col, row) => {
                const el = root.querySelector(
                    `[data-testid="glide-cell-${col}-${row}"]`
                );
                return el ? (el.textContent || '').trim() : '';
            };
            const out = [];
            for (let r = 0; r < rows; r++) {
                out.push({
                    rank: get(0, r),
                    name: get(1, r),
                    score: get(2, r),
                });
            }
            return out;
        }""",
        [expected_rows],
    )


# ---------------------------------------------------------------------------
# The single parameterized test
# ---------------------------------------------------------------------------

def test_recruiter_scenario(
    page, app_base_url, screenshots_dir, scenario
):
    """Run one full (model, JD, resumes) scenario end-to-end."""

    scenario_id = scenario["id"]
    model = scenario["model"]
    jd_path = Path(scenario["jd_file"])
    resume_paths = [Path(p) for p in scenario["resume_files"]]

    if not jd_path.exists():
        pytest.fail(f"JD file missing for scenario {scenario_id}: {jd_path}")
    for resume in resume_paths:
        if not resume.exists():
            pytest.fail(
                f"Resume file missing for scenario {scenario_id}: {resume}"
            )

    jd_text = jd_path.read_text(encoding="utf-8")

    # 1) Open the app - Resume Analyzer tab is the default.
    page.goto(app_base_url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector(
        "text=AI Recruiter Screening System", timeout=60000
    )
    page.wait_for_timeout(2000)  # Let Streamlit fully hydrate.

    # 2) Switch to Configurations and ensure the requested model is selected.
    _select_ollama_model(page, model)

    # 3) Switch back to Resume Analyzer.
    _switch_to_analyzer(page)

    # 4) Upload resumes.
    _upload_resumes(page, resume_paths)

    # 5) Paste the JD and commit it.
    _paste_jd(page, jd_text)

    # 6) Wait for the ranking dashboard to render all rows.
    _wait_for_dashboard(page, expected_rows=len(resume_paths))

    # 7) Read the resulting ranking.
    ranking = _read_full_ranking(page, expected_rows=len(resume_paths))
    if not ranking:
        pytest.fail(f"[{scenario_id}] ranking grid is empty after wait.")

    top = ranking[0]
    top_score_match = SCORE_PATTERN.search(top.get("score") or "")
    if not top_score_match:
        pytest.fail(
            f"[{scenario_id}] could not parse top score {top.get('score')!r}"
        )
    top_score = float(top_score_match.group(0))
    top_resume = top.get("name", "")

    print(
        f"\n[scenario={scenario_id}] model={model} "
        f"top_resume={top_resume!r} top_score={top_score:.2f} "
        f"ranking={ranking}"
    )

    # 8) Optional assertions from the config.
    expected_min = scenario.get("expected_min_score")
    if expected_min is not None:
        assert top_score >= expected_min, (
            f"[{scenario_id}] expected top score >= {expected_min}, "
            f"got {top_score:.2f}"
        )

    expected_top_resume = scenario.get("expected_resume")
    expected_top_resumes_any = scenario.get("expected_resumes_any") or []

    if expected_top_resume:
        assert top_resume == expected_top_resume, (
            f"[{scenario_id}] expected top resume {expected_top_resume!r}, "
            f"got {top_resume!r}"
        )
    elif expected_top_resumes_any:
        assert top_resume in expected_top_resumes_any, (
            f"[{scenario_id}] expected top resume to be one of "
            f"{expected_top_resumes_any!r}, got {top_resume!r}"
        )

    # 9) Save a screenshot for visual review.
    screenshot = screenshots_dir / f"{scenario_id}.png"
    page.screenshot(path=str(screenshot), full_page=True)
    print(f"[scenario={scenario_id}] screenshot saved -> {screenshot}")