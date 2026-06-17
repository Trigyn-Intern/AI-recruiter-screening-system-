from playwright.sync_api import Page

def test_demo_failure(page: Page):
    page.goto("https://example.com")
    assert "Example Domain" in page.title()