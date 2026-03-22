from __future__ import annotations

import logging
from collections.abc import Mapping

import httpx

from app.core.config import Settings


logger = logging.getLogger(__name__)


class PublicJobFetcher:
    """Fetch public job listing pages without any authentication workflow."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch_jobs_page(self, query: str | None = None) -> str:
        """
        Fetch the public source page.

        The first MVP keeps the source interaction intentionally simple. The
        provider URL is public, and additional filtering happens locally after
        parsing and normalization.
        """
        source_url = self._get_source_url()
        logger.info("Fetching public job listings from %s", source_url)
        if query:
            logger.debug("Search query '%s' will be applied after parsing", query)

        async with httpx.AsyncClient(
            timeout=self.settings.http_timeout_seconds,
            follow_redirects=True,
            headers=self._build_headers(),
        ) as client:
            response = await client.get(source_url)
            response.raise_for_status()
            return response.text

    def _get_source_url(self) -> str:
        """Return the public job source URL used by the fetcher."""
        return self.settings.source_base_url

    def _build_headers(self) -> Mapping[str, str]:
        """Return the small set of headers used for a normal public source request."""
        return {
            "User-Agent": "JobIntelligenceAPI/0.1 (+public listing ingestion MVP)",
            "Accept": "application/json,text/html,application/xhtml+xml",
        }
