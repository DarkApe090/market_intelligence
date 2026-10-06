from io import BytesIO
import re
import unicodedata

from docx import Document
from pypdf import PdfReader

from app.scrappers.job_sources import search_all_sources


MAX_CV_BYTES = 5 * 1024 * 1024
MAX_SEARCH_AREAS = 3
JOBS_PER_AREA = 20
LOCATION_ALIASES = {
    "lisboa": {"lisboa", "lisbon", "portugal", "pt"},
    "lisbon": {"lisboa", "lisbon", "portugal", "pt"},
    "porto": {"porto", "portugal", "pt"},
    "braga": {"braga", "portugal", "pt"},
    "coimbra": {"coimbra", "portugal", "pt"},
    "aveiro": {"aveiro", "portugal", "pt"},
    "faro": {"faro", "portugal", "pt"},
    "madeira": {"madeira", "portugal", "pt"},
    "azores": {"azores", "acores", "portugal", "pt"},
}
REGION_COUNTRIES = {
    "europe": {
        "albania", "andorra", "austria", "belarus", "belgium", "bosnia",
        "bulgaria", "croatia", "cyprus", "czechia", "denmark", "estonia",
        "finland", "france", "germany", "greece", "hungary", "iceland",
        "ireland", "italy", "kosovo", "latvia", "liechtenstein", "lithuania",
        "luxembourg", "malta", "moldova", "monaco", "montenegro", "netherlands",
        "north macedonia", "norway", "poland", "portugal", "romania", "san marino",
        "serbia", "slovakia", "slovenia", "spain", "sweden", "switzerland",
        "uk", "ukraine", "united kingdom", "vatican city", "pt",
    },
    "emea": {"europe", "middle east", "africa", "portugal", "pt"},
    "eu": {"europe", "portugal", "pt"},
}
REMOTE_LOCATIONS = {"remote", "worldwide", "global", "anywhere", "remote worldwide"}
KNOWN_LOCATIONS = {
    "argentina", "australia", "brazil", "brasil", "canada", "china", "india",
    "japan", "mexico", "new zealand", "singapore", "south korea", "usa",
    "united states", "united states of america", "portugal", "pt", "lisbon",
    "lisboa", "porto", "braga", "coimbra", "aveiro", "faro", "madeira",
    "azores", "acores", "europe", "emea", "eu", "latam", "latin america",
    "north america", "apac", "asia pacific", "middle east", "africa", "uk",
    "united kingdom", "spain", "france", "germany", "netherlands", "ireland",
}

CAREER_AREAS = [
    {
        "key": "software_engineering",
        "name": "Engenharia de Software",
        "search_query": "engenheiro de software",
        "search_tag": "software",
        "industries": ("software engineering",),
        "role_terms": (
            "engenheiro de software",
            "engenheira de software",
            "engenheiro/a de software",
            "software engineer",
            "engenharia de software",
            "engenheiro informatico",
            "engenheira informatica",
            "engenharia informatica",
            "software developer",
            "desenvolvedor de software",
            "programador de software",
            "software engineering",
            "full stack developer",
            "full stack engineer",
            "full-stack engineer",
            "frontend developer",
            "frontend engineer",
            "frontend engineering",
            "front end engineer",
            "backend developer",
            "backend engineer",
            "backend engineering",
            "back end engineer",
            "fullstack developer",
        ),
        "skill_terms": (
            "python", "java", "typescript", "javascript", "react", "node.js",
            "c#", ".net", "sql", "docker", "git", "angular", "kotlin",
        ),
    },
    {
        "key": "data_ai",
        "name": "Dados e Inteligência Artificial",
        "search_query": "engenheiro de dados machine learning",
        "search_tag": "data",
        "industries": ("data science", "data analytics", "artificial intelligence"),
        "role_terms": (
            "cientista de dados", "data scientist", "engenheiro de dados",
            "data engineer", "machine learning engineer", "engenharia de dados",
            "inteligencia artificial", "artificial intelligence",
        ),
        "skill_terms": (
            "machine learning", "deep learning", "pandas", "pytorch",
            "tensorflow", "scikit-learn", "generative ai",
        ),
    },
    {
        "key": "cybersecurity",
        "name": "Cibersegurança",
        "search_query": "analista cibersegurança",
        "search_tag": "cybersecurity",
        "industries": ("cybersecurity",),
        "role_terms": (
            "ciberseguranca", "cybersecurity", "seguranca informatica",
            "security engineer", "analista de seguranca", "penetration tester",
        ),
        "skill_terms": (
            "siem", "penetration testing", "incident response", "soc analyst",
            "kali linux", "owasp",
        ),
    },
    {
        "key": "cloud_devops",
        "name": "Cloud e DevOps",
        "search_query": "engenheiro DevOps cloud",
        "search_tag": "devops",
        "industries": ("devops", "infrastructure"),
        "role_terms": (
            "devops engineer", "engenheiro devops", "site reliability engineer",
            "platform engineer", "cloud engineer", "engenheiro cloud",
        ),
        "skill_terms": (
            "kubernetes", "terraform", "aws", "azure", "google cloud",
            "jenkins", "ci/cd", "infrastructure as code",
        ),
    },
    {
        "key": "product_design",
        "name": "Produto e UX/UI Design",
        "search_query": "product designer UX UI",
        "search_tag": "design",
        "industries": ("product", "design"),
        "role_terms": (
            "product designer", "ux designer", "ui designer", "ux/ui designer",
            "product manager", "gestor de produto", "design de produto",
        ),
        "skill_terms": ("figma", "user research", "usability testing", "wireframes"),
    },
    {
        "key": "marketing",
        "name": "Marketing e Comunicação",
        "search_query": "marketing digital",
        "search_tag": "marketing",
        "industries": ("marketing", "communications"),
        "role_terms": (
            "marketing manager", "digital marketing", "marketing digital",
            "gestor de marketing", "communication specialist", "comunicacao",
        ),
        "skill_terms": ("seo", "sem", "google analytics", "content marketing"),
    },
    {
        "key": "finance",
        "name": "Finanças e Contabilidade",
        "search_query": "analista financeiro contabilista",
        "search_tag": "finance",
        "industries": ("finance", "accounting"),
        "role_terms": (
            "financial analyst", "analista financeiro", "accountant",
            "contabilista", "contabilidade", "financas",
        ),
        "skill_terms": ("contabilidade", "financial modeling", "sap fi", "auditoria"),
    },
]

SECTION_NAMES = {
    "experiencia": ("experiência", "experiencia profissional", "professional experience", "experience"),
    "formacao": ("formação", "formacao academica", "educação", "education", "academic background"),
    "competencias": ("competências", "competencias", "skills", "technical skills"),
    "perfil": ("perfil", "profile", "summary", "resumo", "sobre mim", "about me"),
}


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.casefold().replace(".", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def _has_term(normalized_text: str, term: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(_normalize(term))}(?![a-z0-9])", normalized_text) is not None


# Tecnologias que, se aparecerem no título da vaga e não estiverem no CV, indicam outra stack.
OTHER_STACK_TERMS = (
    ".net", "c#", "java", "php", "ruby", "golang", "scala", "kotlin", "swift", "c++",
    "angular", "vue", "salesforce", "sap", "wordpress", "drupal", "laravel", "elixir",
    "android", "ios", "unity", "unreal",
)


def _location_priority(job_location: str, requested_location: str) -> int | None:
    location_parts = {
        _normalize(part)
        for part in re.split(r"[,;/|]", job_location)
        if _normalize(part)
    }
    if not location_parts:
        return 4

    requested = _normalize(requested_location)
    requested_aliases = LOCATION_ALIASES.get(requested, {requested})
    matching_locations = location_parts.intersection(requested_aliases)
    if matching_locations:
        return 0 if location_parts.issubset(requested_aliases) else 1

    remote_match = bool(location_parts.intersection(REMOTE_LOCATIONS))
    region_matches = any(
        region in location_parts and requested_aliases.intersection(countries)
        for region, countries in REGION_COUNTRIES.items()
    )
    known_regions = set(REGION_COUNTRIES)
    specific_locations = location_parts.intersection(KNOWN_LOCATIONS - known_regions - REMOTE_LOCATIONS)

    if specific_locations:
        return None

    if remote_match and region_matches:
        return 3

    if region_matches:
        return 2

    if remote_match:
        return 3

    return None


def extract_cv_text(filename: str, content: bytes) -> str:
    extension = filename.rsplit(".", 1)[-1].casefold() if "." in filename else ""

    if extension == "pdf":
        pages = PdfReader(BytesIO(content)).pages
        text = "\n".join(page.extract_text() or "" for page in pages)
    elif extension == "docx":
        document = Document(BytesIO(content))
        paragraphs = [paragraph.text for paragraph in document.paragraphs]
        table_cells = [cell.text for table in document.tables for row in table.rows for cell in row.cells]
        text = "\n".join(paragraphs + table_cells)
    else:
        raise ValueError("Formato não suportado. Carrega um ficheiro PDF ou DOCX.")

    text = text.strip()
    if not text:
        raise ValueError("Não foi possível extrair texto. PDFs digitalizados como imagem não são suportados nesta versão.")

    return text[:100_000]


def analyze_cv_text(text: str) -> list[dict]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    current_section = "perfil"
    contextual_lines: list[tuple[str, str]] = []

    for line in lines:
        normalized_line = _normalize(line)
        for section, headings in SECTION_NAMES.items():
            if normalized_line in {_normalize(heading) for heading in headings}:
                current_section = section
                break
        contextual_lines.append((line, current_section))

    detections = []
    for area in CAREER_AREAS:
        evidence = []
        score = 0
        matched_roles = []
        matched_skills = []
        normalized_role_terms = tuple((term, _normalize(term)) for term in area["role_terms"])
        normalized_skill_terms = tuple((term, _normalize(term)) for term in area["skill_terms"])

        for line, section in contextual_lines:
            normalized_line = _normalize(line)
            matching_roles = [term for term, normalized in normalized_role_terms if normalized in normalized_line]
            matching_skills = [term for term, normalized in normalized_skill_terms if normalized in normalized_line]
            if matching_roles or matching_skills:
                score += len(matching_roles) * 3 + len(matching_skills)
                evidence.append({"text": line[:240], "section": section})
                matched_roles.extend(term for term in matching_roles if term not in matched_roles)
                matched_skills.extend(term for term in matching_skills if term not in matched_skills)

        if not evidence:
            continue

        query_role = matched_roles[0] if matched_roles else area["name"]
        search_query = " ".join([query_role, *matched_skills[:3]])

        detections.append(
            {
                "key": area["key"],
                "name": area["name"],
                "search_query": search_query or area["search_query"],
                "matched_skills": matched_skills,
                "confidence": "high" if score >= 3 else "medium" if score >= 2 else "low",
                "evidence": evidence[:4],
            }
        )

    return sorted(
        detections,
        key=lambda detection: (detection["confidence"] != "high", -len(detection["evidence"])),
    )


def extract_candidate_name(text: str) -> str | None:
    """O nome costuma ser a primeira linha do CV; rejeita linhas que não pareçam um nome."""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        words = line.split()
        looks_like_name = (
            2 <= len(words) <= 5
            and len(line) <= 60
            and not re.search(r"[\d@:/|,]", line)
            and all(word[0].isalpha() for word in words)
        )
        return line if looks_like_name else None
    return None


def analyze_cv(filename: str, content: bytes, location: str = "Portugal") -> dict:
    if len(content) > MAX_CV_BYTES:
        raise ValueError("O CV excede o limite de 5 MB.")

    text = extract_cv_text(filename, content)
    candidate_name = extract_candidate_name(text)
    areas = analyze_cv_text(text)
    suggestions = []
    search_errors = []
    excluded_location_count = 0
    seen_jobs = set()

    area_configs = {area["key"]: area for area in CAREER_AREAS}
    cv_skills = list(dict.fromkeys(skill for area in areas for skill in area["matched_skills"]))
    normalized_cv_skills = {_normalize(skill) for skill in cv_skills}
    for area in areas[:MAX_SEARCH_AREAS]:
        area_config = area_configs[area["key"]]
        jobs, failed_sources = search_all_sources(
            area_config["search_tag"], location=location, limit=JOBS_PER_AREA
        )
        search_errors.extend(f"{area['name']} ({source})" for source in failed_sources)

        for job in jobs:
            company = (job.get("company") or "").strip()
            title = (job.get("title") or "").strip()
            url = (job.get("url") or "").strip()
            job_location = (job.get("location") or "").strip()
            if not company or not title or not url:
                continue

            location_priority = _location_priority(job_location, location)
            if location_priority not in {0, 1, 3}:
                excluded_location_count += 1
                continue

            normalized_title = _normalize(title)
            normalized_industries = [_normalize(item) for item in job.get("industry", [])]
            normalized_excerpt = _normalize(job.get("excerpt") or "")
            searchable_text = " ".join([normalized_title, *normalized_industries, normalized_excerpt])
            role_matches = [
                term for term in area_config["role_terms"]
                if _has_term(normalized_title, term)
            ]
            skill_matches = [
                skill for skill in cv_skills
                if _has_term(searchable_text, skill)
            ]
            title_skill_matches = [skill for skill in skill_matches if _has_term(normalized_title, skill)]
            industry_match = any(
                _normalize(industry) in job_industry
                for industry in area_config["industries"]
                for job_industry in normalized_industries
            )
            if not role_matches and not (industry_match and skill_matches):
                continue

            foreign_stack = [
                term for term in OTHER_STACK_TERMS
                if _normalize(term) not in normalized_cv_skills and _has_term(normalized_title, term)
            ]
            if foreign_stack and not title_skill_matches:
                continue
            if not skill_matches:
                continue

            key = (company.casefold(), url)
            if key in seen_jobs:
                continue
            seen_jobs.add(key)
            suggestions.append(
                {
                    "company": company,
                    "title": title,
                    "location": job_location or "Localização não confirmada",
                    "email": None,
                    "location_priority": location_priority,
                    "url": url,
                    "area": area["name"],
                    "source": job.get("source", "Desconhecida"),
                    "matched_skills": skill_matches,
                    "match_score": len(role_matches) * 4 + len(title_skill_matches) * 3 + len(skill_matches) * 2 + (2 if industry_match else 0),
                }
            )

    suggestions.sort(
        key=lambda suggestion: (
            suggestion["location_priority"],
            -suggestion["match_score"],
        )
    )
    unique_suggestions = []
    seen_companies = set()
    for suggestion in suggestions:
        company_key = _normalize(suggestion["company"])
        if company_key in seen_companies:
            continue
        seen_companies.add(company_key)
        unique_suggestions.append(suggestion)

    return {
        "candidate_name": candidate_name,
        "areas": areas,
        "suggestions": unique_suggestions,
        "location_priority_order": [
            "Localização exata",
            "Também elegível na localização escolhida",
            "Região compatível",
            "Remoto/global",
            "Localização por confirmar",
        ],
        "excluded_location_count": excluded_location_count,
        "search_errors": search_errors,
        "cv_saved": False,
        "excluded_location_count": excluded_location_count,
    }