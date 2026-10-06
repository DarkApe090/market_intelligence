from playwright.sync_api import sync_playwright

selectors = [
    "a[data-jk]",
    "a[href*='/rc/']",
    "a.jcs-JobTitle",
    "a.jobtitle",
    "div.job_seen_beacon",
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://pt.indeed.com/jobs?q=python+developer", wait_until="domcontentloaded")
    page.wait_for_timeout(5000)

    print("TITLE:", page.title())
    for sel in selectors:
        print(sel, page.locator(sel).count())

    body = page.locator("body").inner_text()
    print("BODY_SAMPLE_START")
    print(body[:2000])
    print("BODY_SAMPLE_END")

    browser.close()