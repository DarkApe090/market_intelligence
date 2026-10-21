import html
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.scrappers.common import USER_AGENT, http_get


PAGE_TIMEOUT = 10
DOMAIN_TLDS = ("com", "pt", "de", "io", "co", "ai", "net", "eu", "dev", "org")
CANDIDATE_PATHS = (
    "/careers", "/jobs", "/carreiras", "/emprego", "/recrutamento", "/join", "/join-us",
    "/contact", "/contact-us", "/contacts", "/contactos", "/contacto", "/kontakt",
    "/", "/about", "/about-us", "/company", "/team", "/legal", "/terms",
    "/impressum", "/imprint", "/privacy", "/pt/contactos", "/en/contact", "/support", "/help",
)
LINK_HINTS = ("contact", "career", "job", "impressum", "imprint", "kontakt", "about", "legal", "privacy", "carreira", "emprego", "team", "recrut")
JOB_BOARD_HOSTS = (
    "itjobs.pt", "remoteok.com", "remotive.com", "remotive.io", "jobicy.com",
    "weworkremotely.com", "linkedin.com", "greenhouse.io", "lever.co",
    "indeed.com", "glassdoor.com", "net-empregos.com", "net-empregos.pt",
    "teamlyzer.com",
)
SOCIAL_HOSTS = ("facebook.com", "twitter.com", "x.com", "instagram.com", "youtube.com", "tiktok.com")
MAX_LINKED_PAGES = 6
USE_BROWSER_FALLBACK = True
BROWSER_MAX_PAGES = 6
BROWSER_TIMEOUT_MS = 15000
CAREERS_SUBDOMAINS = ("careers", "jobs")

EMAIL_PATTERN = re.compile(r"[a-z0-9._%+\-]+@[a-z0-9\-]+(?:\.[a-z0-9\-]+)*\.[a-z]{2,}")
INVALID_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js")
INVALID_WORDS = (
    "sentry", "noreply", "no-reply", "donotreply", "wixpress", "example.com", "domain.com",
    "itjobs", "remoteok", "remotive", "weworkremotely", "jobicy", "greenhouse", "lever.co",
    "net-empregos", "teamlyzer", "dpo@", "gdpr@", "privacy@", "cookies@",
)
CAREERS_PREFIXES = (
    "careers", "career", "jobs", "job", "recruitment", "recruiting", "recrutamento",
    "talent", "talento", "hr", "rh", "emprego", "carreiras", "apply", "recruit",
    "hiring", "people", "join", "bewerbung", "jobs-pt", "work", "candidatura", "candidaturas",
)
GENERAL_PREFIXES = (
    "info", "hello", "hi", "hey", "sayhello", "geral", "office", "mail", "general", "team",
    "hola", "ola", "enquiries", "enquiry", "admin", "business", "press",
    "contact", "contacts", "contacto", "contactos", "kontakt",
)
INVALID_LOCAL_MARKS = ("sales", "ventas", "venda", "support", "helpdesk", "suporte")
INVALID_LOCAL_EXACT = ("help", "legal", "abuse", "billing", "invoice", "webmaster", "postmaster")
RELATED_SLUG_TAILS = (
    "consulting", "consultores", "consultoria", "consult", "group", "digital",
    "tech", "solutions", "studio", "labs",
)
LOCATION_TLDS = {
    "portugal": ("pt",),
    "pt": ("pt",),
    "lisboa": ("pt",),
    "lisbon": ("pt",),
    "porto": ("pt",),
    "alemanha": ("de",),
    "germany": ("de",),
    "deutschland": ("de",),
    "spain": ("es",),
    "espanha": ("es",),
    "espana": ("es",),
}


def fetch_page(url: str) -> str | None:
    try:
        response = http_get(url, timeout=PAGE_TIMEOUT)
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
    if email.endswith(INVALID_SUFFIXES) or any(word in email for word in INVALID_WORDS):
        return False
    local_part = email.split("@", 1)[0]
    if local_part in INVALID_LOCAL_EXACT:
        return False
    return not any(mark in local_part for mark in INVALID_LOCAL_MARKS)


def classify_email(email: str) -> str | None:
    local_part = email.split("@", 1)[0]
    head = re.split(r"[._+\-]", local_part, maxsplit=1)[0]
    if local_part in CAREERS_PREFIXES or head in CAREERS_PREFIXES:
        return "careers"
    if local_part in GENERAL_PREFIXES or head in GENERAL_PREFIXES:
        return "general"
    return None


def _company_slugs(name: str | None) -> list[str]:
    return [slug for slug, _extra in _slug_candidates(name or "")]


def _is_branded_mailbox(email: str, company_name: str | None = None) -> bool:
    local_part, domain = email.split("@", 1)
    labels = {domain.split(".")[0], *_company_slugs(company_name)}
    return bool(local_part) and local_part in labels


def pick_contact_email(emails: set[str], company_name: str | None = None) -> str | None:
    """Jobs/carreiras, depois o email com o nome da empresa, depois o geral; caixas como legal@ ficam de fora."""
    best_branded = None
    best_general = None
    best_other = None
    for email in sorted(email for email in emails if is_valid_email(email)):
        email_type = classify_email(email)
        if email_type == "careers":
            return email
        if _is_branded_mailbox(email, company_name) and best_branded is None:
            best_branded = email
        elif email_type == "general" and best_general is None:
            best_general = email
        elif email_type is None and best_other is None:
            best_other = email
    return best_branded or best_general or best_other


def emails_matching_company(page: str, company_name: str) -> set[str]:
    emails = extract_emails(page)
    slugs = [slug for slug in _company_slugs(company_name) if len(slug) >= 3]
    if not slugs:
        return emails
    return {
        email for email in emails
        if any(_related_slugs(slug, email.split("@", 1)[1].split(".")[0]) for slug in slugs)
    }


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


def _tlds_for(location: str | None) -> tuple[str, ...]:
    folded = unicodedata.normalize("NFKD", location or "")
    folded = "".join(char for char in folded.casefold() if not unicodedata.combining(char))
    preferred: tuple[str, ...] = ()
    for key, tlds in LOCATION_TLDS.items():
        if key in folded:
            preferred = tlds
            break
    return preferred + tuple(tld for tld in DOMAIN_TLDS if tld not in preferred)


def guess_website(company_name: str, location: str | None = None) -> str | None:
    """Tenta domínios derivados do nome; só aceita se a página existir e mencionar a empresa."""
    tasks: list[tuple[str, str, list[str]]] = []
    seen: set[str] = set()
    tlds = _tlds_for(location)
    for slug, extra_words in _slug_candidates(company_name):
        for tld in tlds:
            for website in (f"https://www.{slug}.{tld}", f"https://{slug}.{tld}"):
                if website in seen:
                    continue
                seen.add(website)
                tasks.append((website, slug, extra_words))

    def matches(item: tuple[str, str, list[str]]) -> str | None:
        website, slug, extra_words = item
        page = fetch_page(website)
        if page is None:
            return None
        text = re.sub(r"[^a-z0-9]", "", page.casefold())
        if slug in text and (not extra_words or any(word in text for word in extra_words)):
            return website
        return None

    executor = ThreadPoolExecutor(max_workers=10)
    try:
        for found in executor.map(matches, tasks):
            if found:
                return found
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    return None


def _related_slugs(left: str, right: str) -> bool:
    if left == right:
        return True
    shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
    if len(shorter) < 4 or not longer.startswith(shorter):
        return False
    return longer[len(shorter):] in RELATED_SLUG_TAILS


def _same_company_domain(email: str, website: str) -> bool:
    host = (urlparse(website).hostname or "").removeprefix("www.")
    email_domain = email.split("@", 1)[1]
    if email_domain == host or email_domain.endswith(f".{host}") or host.endswith(f".{email_domain}"):
        return True
    return _related_slugs(host.split(".")[0], email_domain.split(".")[0])


def _is_third_party_host(host: str) -> bool:
    host = host.removeprefix("www.")
    known = JOB_BOARD_HOSTS + SOCIAL_HOSTS
    return any(host == name or host.endswith(f".{name}") for name in known)


def company_site(url: str | None) -> str | None:
    """Normaliza um site de empresa e rejeita job boards."""
    if not url or not url.strip():
        return None
    website = url.strip()
    if not website.startswith(("http://", "https://")):
        website = f"https://{website}"
    host = urlparse(website).hostname or ""
    if not host or _is_third_party_host(host):
        return None
    return f"{urlparse(website).scheme}://{urlparse(website).netloc}"


def _host_names_company(host: str, company_name: str) -> bool:
    compact = host.removeprefix("www.").replace(".", "")
    if not compact or _is_third_party_host(host):
        return False
    return any(
        len(slug) >= 3 and (slug in compact or compact in slug)
        for slug in _company_slugs(company_name)
    )


def website_from_job_url(url: str, company_name: str) -> str | None:
    """Se a vaga está num domínio com o nome da empresa, esse é o site."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if not _host_names_company(host, company_name):
        return None
    return f"{parsed.scheme or 'https'}://{host}"


def website_from_job_page(page: str, page_url: str, company_name: str) -> str | None:
    """Procura no anúncio um link para o site da empresa (pelo nome)."""
    for href in HREF_PATTERN.findall(html.unescape(page)):
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        url = urljoin(page_url, href).split("#")[0]
        host = urlparse(url).hostname or ""
        if _host_names_company(host, company_name):
            return f"{urlparse(url).scheme}://{host}"
    return None


def _candidate_urls(website: str) -> list[str]:
    parsed = urlparse(website)
    host = (parsed.hostname or "").removeprefix("www.")
    urls = [f"{parsed.scheme}://{prefix}.{host}/" for prefix in CAREERS_SUBDOMAINS]
    urls += [urljoin(website, path) for path in CANDIDATE_PATHS]
    return urls


def _allowed_by_robots(website: str) -> "RobotFileParser | None":
    parsed = urlparse(website)
    robots = RobotFileParser()
    try:
        response = http_get(
            f"{parsed.scheme}://{parsed.netloc}/robots.txt",
            timeout=PAGE_TIMEOUT,
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


def find_company_email(website: str, use_browser: bool = True) -> tuple[str, str, str] | None:
    """Devolve (email, tipo, url da página); prefere contactos/carreiras e, na falta, general."""
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
    if found is not None or not use_browser or not USE_BROWSER_FALLBACK:
        return found

    browser_urls = urls[:BROWSER_MAX_PAGES]
    return _pick_email(browser_urls, render_pages(browser_urls), website)


def _pick_email(urls: list[str], pages: list[str | None], website: str) -> tuple[str, str, str] | None:
    best_general: tuple[str, str, str] | None = None
    for page_url, page in zip(urls, pages):
        if page is None:
            continue
        company_emails = {
            email for email in extract_emails(page) if _same_company_domain(email, website)
        }
        picked = pick_contact_email(company_emails, website)
        if picked is None:
            continue
        email_type = classify_email(picked) or "general"
        if email_type == "careers":
            return picked, "careers", page_url
        if best_general is None:
            best_general = (picked, "general", page_url)
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