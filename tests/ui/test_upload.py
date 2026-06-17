from playwright.sync_api import sync_playwright

def test_resume_upload():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto("http://localhost:8501")

        # wait for file input properly
        page.wait_for_selector("input[type='file']")

        # correct file upload
        page.locator("input[type='file']").set_input_files(
            "tests/data/sample_resume.pdf"
        )

        page.wait_for_timeout(3000)

        assert page.content() is not None

        browser.close()