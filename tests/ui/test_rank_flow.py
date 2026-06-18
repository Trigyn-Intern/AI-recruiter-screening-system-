def test_ranking_flow(page):
    page.goto("http://localhost:8501", timeout=60000)

    page.fill("textarea", "Data Science role")

    page.set_input_files(
        "input[type='file']",
        "tests/data/sample_resume.pdf"
    )

    page.wait_for_timeout(3000)

    content = page.content()

    assert "Rank" in content or "Score" in content