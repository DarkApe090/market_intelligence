from app.scrappers.common import (
    build_job,
    get_cached_text,
    is_european_market,
    matches_tag,
    rss_items,
    take_fresh,
)


SOURCE_NAME = "We Work Remotely"
GENERAL_FEED = "https://weworkremotely.com/remote-jobs.rss"
FEEDS = {
    "software": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "data": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "cybersecurity": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "devops": "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
    "design": "https://weworkremotely.com/categories/remote-design-jobs.rss",
    "marketing": "https://weworkremotely.com/categories/remote-marketing-jobs.rss",
    "finance": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
}


def _feed_for(tag: str) -> str:
    folded = tag.casefold()
    if folded in FEEDS:
        return FEEDS[folded]
    for key, url in FEEDS.items():
        if key in folded:
            return url
    return GENERAL_FEED


def search_jobs(tag: str, location: str, limit: int = 10) -> list[dict]:
    feed = _feed_for(tag)
    xml_text = get_cached_text(feed)
    results = []
    for item in rss_items(xml_text):
        raw_title = item["title"]
        company, separator, title = raw_title.partition(": ")
        if not separator:
            continue
        if not matches_tag(tag, f"{title} {item['category']} {item['description']}"):
            continue
        if not is_european_market(item["region"], item["description"], requested=location):
            continue
        built = build_job(
            company=company,
            title=title,
            location=item["region"] or "Remote",
            url=item["link"],
            industry=[item["category"]] if item["category"] else [],
            excerpt=item["description"],
            source=SOURCE_NAME,
            posted_at=item["pubDate"],
        )
        if built:
            results.append(built)
    return take_fresh(results, limit)
