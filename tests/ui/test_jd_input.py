def test_job_description_input(page):
    page.goto("http://localhost:8501", timeout=60000)

    page.fill("textarea", "Python Developer with ML experience")
    page.wait_for_timeout(1000)

    assert "Python" in page.content()