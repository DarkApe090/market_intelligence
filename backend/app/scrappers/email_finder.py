import html
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.scrappers.common import USER_AGENT


PAGE_TIMEOUT = 10
DOMAIN_TLDS = ("com", "pt", "de", "io", "co", "ai", "net", "eu", "dev", "org")
CANDIDATE_PATHS = (
    "/", "/careers", "/jobs", "/contact", "/contact-us", "/about", "/about-us",
    "/company", "/team", "/legal", "/terms", "/impressum", "/imprint", "/kontakt", "/privacy",
    "/contacts", "/contactos", "/contacto", "/pt/contactos", "/en/contact", "/support", "/help",
)
LINK_HINTS = ("contact", "career", "job", "impressum", "imprint", "kontakt", "about", "legal", "privacy", "carreira", "emprego", "team")
MAX_LINKED_PAGES = 6
USE_BROWSER_FALLBACK = True
BROWSER_MAX_PAGES = 6
BROWSER_TIMEOUT_MS = 15000
CAREERS_SUBDOMAINS = ("careers", "jobs")

EMAIL_PATTERN = re.compile(r"[a-z0-9._%+\-]+@[a-z0-9\-]+(?:\.[a-z0-9\-]+)*\.[a-z]{2,}")
INVALID_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js")
INVALID_WORDS = ("sentry", "noreply", "no-reply", "donotreply", "wixpress", "example.com", "domain.com")
CAREERS_PREFIXES = ("careers", "career", "jobs", "job", "recruitment", "recruiting", "talent", "hr", "rh", "emprego", "carreiras", "apply", "recruit", "hiring", "people", "join", "bewerbung", "jobs-pt", "work")
GENERAL_PREFIXES = ("info", "hello", "hi", "hey", "contact", "contacts", "contacto", "geral", "office", "mail", "general", "team", "support", "help", "hola", "ola", "kontakt", "enquiries", "enquiry", "admin", "sales", "business", "press")


def fetch_page(url: str) -> str | None:
    try:
        response = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=PAGE_TIMEOUT,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return None

    if "html" not in response.headers.get("content-type", "").casefold():
        return None
    return response.text


CF_EMAIL_PATTERN = re.compile(r'data-cfemail="([0-9a-f]+)"', re.IGNORECASE)
OBFUSCATED_PATTERN = re.compile(
    r"([a-z0-9._%+\-]+)\s*[\[\(\{]\s*(?:at|arroba)\s*[\]\)\}]\s*"
    r"([a-z0-9\-]+(?:\s*(?:[\[\(\{]\s*(?:dot|ponto)\s*[\]\)\}]|\.)\s*[a-z0-9\-]+)+)"
)
HREF_PATTERN = re.compile(r'href=["\']([^"\'#]+)["\']', re.IGNORECASE)


def _decode_cloudflare(encoded: str) -> str | None:
    try:
        raw = bytes.fromhex(encoded)
        key = raw[0]
        return bytes(byte ^ key for byte in raw[1:]).decode()
    except (ValueError, IndexError, UnicodeDecodeError):
        return None


def extract_emails(page: str) -> set[str]:
    candidates = [html.unescape(unquote(page)).casefold()]
    for encoded in CF_EMAIL_PATTERN.findall(page):
        decoded = _decode_cloudflare(encoded)
        if decoded:
            candidates.append(decoded.casefold())

    emails: set[str] = set()
    for text in candidates:
        emails.update(EMAIL_PATTERN.findall(text))
        for user, domain in OBFUSCATED_PATTERN.findall(text):
            domain = re.sub(r"\s*[\[\(\{]\s*(?:dot|ponto)\s*[\]\)\}]\s*", ".", domain)
            domain = re.sub(r"\s+", "", domain)
            emails.add(f"{user}@{domain}")
    return {email.strip(".") for email in emails if is_valid_email(email.strip("."))}


def _linked_urls(page: str, base_url: str, website: str) -> list[str]:
    host = (urlparse(website).hostname or "").removeprefix("www.")
    found: list[str] = []
    for href in HREF_PATTERN.findall(html.unescape(page)):
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        url = urljoin(base_url, href).split("#")[0]
        link_host = (urlparse(url).hostname or "").removeprefix("www.")
        if not (link_host == host or link_host.endswith(f".{host}")):
            continue
        if any(hint in url.casefold() for hint in LINK_HINTS) and url not in found:
            found.append(url)
    return found


def is_valid_email(email: str) -> bool:
    return not email.endswith(INVALID_SUFFIXES) and not any(word in email for word in INVALID_WORDS)


def classify_email(email: str) -> str | None:
    local_part = email.split("@", 1)[0]
    if local_part in CAREERS_PREFIXES:
        return "careers"
    if local_part in GENERAL_PREFIXES:
        return "general"
    return None


def _company_slug(name: str) -> str:
    slug = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().casefold()
    slug = re.sub(r"\b(?:lda|inc|llc|ltd|gmbh|ag|sa|sl|corp|co|limited|unipessoal)\b\.?", " ", slug)
    return re.sub(r"[^a-z0-9]", "", slug)


def _slug_candidates(name: str) -> list[tuple[str, list[str]]]:
    """(slug, palavras extra que a página deve mencionar quando o slug é parcial)."""
    candidates: list[tuple[str, list[str]]] = []
    seen: set[str] = set()
    for part in re.split(r"\s+[-–|/]\s+|\s*\(", name):
        ascii_part = unicodedata.normalize("NFKD", part).encode("ascii", "ignore").decode().casefold()
        words = [word for word in re.sub(r"[^a-z0-9 ]", " ", ascii_part).split() if _company_slug(word)]
        options = [(_company_slug(part), [])]
        if len(words) > 1:
            options.append((_company_slug(words[0]), [word for word in words[1:] if len(word) >= 4]))
            options.append((_company_slug(" ".join(words[:2])), [word for word in words[2:] if len(word) >= 4]))
        for slug, extra in options:
            if len(slug) >= 3 and slug not in seen:
                seen.add(slug)
                candidates.append((slug, extra))
    return candidates


def guess_website(company_name: str) -> str | None:
    """Tenta domínios derivados do nome; só aceita se a página existir e mencionar a empresa."""
    for slug, extra_words in _slug_candidates(company_name):
        for tld in DOMAIN_TLDS:
            for website in (f"https://www.{slug}.{tld}", f"https://{slug}.{tld}"):
                page = fetch_page(website)
                if page is None:
                    continue
                text = re.sub(r"[^a-z0-9]", "", page.casefold())
                if slug in text and (not extra_words or any(word in text for word in extra_words)):
                    return website
    return None


def _same_company_domain(email: str, website: str) -> bool:
    host = (urlparse(website).hostname or "").removeprefix("www.")
    email_domain = email.split("@", 1)[1]
    return email_domain == host or email_domain.endswith(f".{host}") or host.endswith(f".{email_domain}")


def _candidate_urls(website: str) -> list[str]:
    parsed = urlparse(website)
    host = (parsed.hostname or "").removeprefix("www.")
    urls = [urljoin(website, path) for path in CANDIDATE_PATHS]
    urls += [f"{parsed.scheme}://{prefix}.{host}/" for prefix in CAREERS_SUBDOMAINS]
    return urls


def _allowed_by_robots(website: str) -> "RobotFileParser | None":
    parsed = urlparse(website)
    robots = RobotFileParser()
    try:
        response = httpx.get(
            f"{parsed.scheme}://{parsed.netloc}/robots.txt",
            headers={"User-Agent": USER_AGENT},
            timeout=PAGE_TIMEOUT,
            follow_redirects=True,
        )
    except httpx.HTTPError:
        return None

    if response.status_code in (401, 403):
        robots.disallow_all = True
        return robots
    if response.status_code != 200:
        return None

    robots.parse(response.text.splitlines())
    return robots


def find_company_email(website: str) -> tuple[str, str, str] | None:
    """Devolve (email, tipo, url da página); prefere careers e, na falta, general."""
    if not website.startswith(("http://", "https://")):
        website = f"https://{website}"

    urls = _candidate_urls(website)
    robots = _allowed_by_robots(website)
    if robots is not None:
        urls = [url for url in urls if robots.can_fetch(USER_AGENT, url)]

    with ThreadPoolExecutor(max_workers=6) as executor:
        pages = list(executor.map(fetch_page, urls))

        linked: list[str] = []
        for page_url, page in zip(urls, pages):
            if page is None:
                continue
            for link in _linked_urls(page, page_url, website):
                if link not in urls and link not in linked and (robots is None or robots.can_fetch(USER_AGENT, link)):
                    linked.append(link)
        linked = linked[:MAX_LINKED_PAGES]
        urls += linked
        pages += list(executor.map(fetch_page, linked))

    found = _pick_email(urls, pages, website)
    if found is not None or not USE_BROWSER_FALLBACK:
        return found

    browser_urls = urls[:BROWSER_MAX_PAGES]
    return _pick_email(browser_urls, render_pages(browser_urls), website)


def _pick_email(urls: list[str], pages: list[str | None], website: str) -> tuple[str, str, str] | None:
    best_general: tuple[str, str, str] | None = None
    for page_url, page in zip(urls, pages):
        if page is None:
            continue

        for email in sorted(extract_emails(page)):
            if not _same_company_domain(email, website):
                continue
            email_type = classify_email(email)
            if email_type == "careers":
                return email, email_type, page_url
            if email_type == "general" and best_general is None:
                best_general = (email, email_type, page_url)

    return best_general


def render_pages(urls: list[str]) -> list[str | None]:
    """Renderiza páginas num Chromium headless para apanhar emails injetados por JavaScript."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return [None] * len(urls)

    pages: list[str | None] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(user_agent=USER_AGENT)
            for url in urls:
                page = context.new_page()
                try:
                    page.goto(url, wait_until="networkidle", timeout=BROWSER_TIMEOUT_MS)
                    pages.append(page.content())
                except Exception:
                    pages.append(None)
                finally:
                    page.close()
            browser.close()
    except Exception:
        return [None] * len(urls)
    return pages