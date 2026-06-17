from playwright.sync_api import sync_playwright

def test_ranking_flow():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto("http://localhost:8501")

        page.fill("textarea", "Data Science role")
        page.set_input_files("input[type='file']", "tests/data/sample_resume.pdf")

        page.wait_for_timeout(3000)

        assert "Rank" in page.content() or "Score" in page.content()

        browser.close()