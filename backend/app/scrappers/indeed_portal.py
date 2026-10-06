from urllib.parse import quote_plus

from playwright.sync_api import sync_playwright


def scrape_jobs(query: str, location: str | None = None, limit: int = 10):
    search_url = f"https://pt.indeed.com/jobs?q={quote_plus(query)}"
    if location:
        search_url += f"&l={quote_plus(location)}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
            page.locator(".job_seen_beacon").first.wait_for(timeout=10000)

            jobs = []
            cards = page.locator(".job_seen_beacon")
            for index in range(min(cards.count(), limit)):
                card = cards.nth(index)
                title_link = card.locator("a[data-jk]").first
                title = title_link.inner_text().strip()
                job_id = title_link.get_attribute("data-jk")
                company_locator = card.locator('[data-testid="company-name"]').first
                location_locator = card.locator('[data-testid="text-location"]').first
                company = company_locator.inner_text().strip() if company_locator.count() else ""
                job_location = location_locator.inner_text().strip() if location_locator.count() else ""

                if title and company and job_id:
                    jobs.append(
                        {
                            "title": title,
                            "company": company,
                            "url": f"https://pt.indeed.com/viewjob?jk={job_id}",
                            "location": job_location,
                        }
                    )

            return jobs
        finally:
            browser.close()