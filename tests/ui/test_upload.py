from playwright.sync_api import sync_playwright

def test_resume_upload():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # wait longer for CI stability
        page.goto("http://localhost:8501", timeout=60000)

        page.wait_for_selector("input[type='file']", timeout=60000)

        page.locator("input[type='file']").set_input_files(
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

        browser.close()