from concurrent.futures import ThreadPoolExecutor

from app.scrappers import (
    arbeitnow_portal,
    himalayas_portal,
    jobicy_portal,
    remoteok_portal,
    remotive_portal,
)


JOB_SOURCES = (
    jobicy_portal,
    remotive_portal,
    remoteok_portal,
    himalayas_portal,
    arbeitnow_portal,
)


def search_all_sources(tag: str, location: str, limit: int = 20) -> tuple[list[dict], list[str]]:
    """Pesquisa todas as fontes em paralelo; uma fonte a falhar não afeta as outras."""

    def run(source) -> tuple[str, list[dict] | None]:
        try:
            return source.SOURCE_NAME, source.search_jobs(tag, location=location, limit=limit)
        except Exception:
            return source.SOURCE_NAME, None

    with ThreadPoolExecutor(max_workers=len(JOB_SOURCES)) as executor:
        outcomes = list(executor.map(run, JOB_SOURCES))

    jobs: list[dict] = []
    failed_sources: list[str] = []
    for source_name, source_jobs in outcomes:
        if source_jobs is None:
            failed_sources.append(source_name)
        else:
            jobs.extend(source_jobs)
    return jobs, failed_sources
