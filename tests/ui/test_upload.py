from playwright.sync_api import sync_playwright

def test_homepage():

    with sync_playwright() as p:

        browser = p.chromium.launch()

        page = browser.new_page()

        page.goto("http://localhost:8501")

        assert "AI Recruiter Screening System" in page.content()

        browser.close()