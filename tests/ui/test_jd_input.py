from playwright.sync_api import sync_playwright

def test_job_description_input():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto("http://localhost:8501")

        page.fill("textarea", "Python Developer with ML experience")
        page.wait_for_timeout(1000)

        assert "Python" in page.content()

        browser.close()