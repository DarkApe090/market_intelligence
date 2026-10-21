from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

from app.scrappers import (
    arbeitnow_portal,
    himalayas_portal,
    itjobs_portal,
    jobicy_portal,
    netempregos_portal,
    remoteok_portal,
    remotive_portal,
    teamlyzer_portal,
    weworkremotely_portal,
)


LOCAL_JOB_SOURCES = (
    netempregos_portal,
    itjobs_portal,
    teamlyzer_portal,
)
REMOTE_JOB_SOURCES = (
    weworkremotely_portal,
    remotive_portal,
    remoteok_portal,
    jobicy_portal,
    himalayas_portal,
    arbeitnow_portal,
)
JOB_SOURCES = LOCAL_JOB_SOURCES + REMOTE_JOB_SOURCES

logger = logging.getLogger(__name__)


def iter_source_results(tag: str, location: str, limit: int = 20, include_remote: bool = True):
    """Devolve (fonte, vagas) à medida que cada board responde."""
    sources = JOB_SOURCES if include_remote else LOCAL_JOB_SOURCES

    def run(source) -> tuple[str, list[dict] | None]:
        try:
            return source.SOURCE_NAME, source.search_jobs(tag, location=location, limit=limit)
        except Exception as exc:
            logger.warning("%s search failed for %r: %s", source.SOURCE_NAME, tag, exc)
            return source.SOURCE_NAME, None

    with ThreadPoolExecutor(max_workers=max(len(sources), 1)) as executor:
        futures = [executor.submit(run, source) for source in sources]
        for future in as_completed(futures):
            yield future.result()


def search_all_sources(
    tag: str, location: str, limit: int = 20, include_remote: bool = True,
) -> tuple[list[dict], list[str]]:
    """Pesquisa todas as fontes em paralelo; uma fonte a falhar não afeta as outras."""
    jobs: list[dict] = []
    failed_sources: list[str] = []
    for source_name, source_jobs in iter_source_results(tag, location, limit, include_remote):
        if source_jobs is None:
            failed_sources.append(source_name)
        else:
            jobs.extend(source_jobs)
    return jobs, failed_sources
