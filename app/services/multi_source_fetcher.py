from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass

import httpx

from app.core.config import Settings


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SourceDefinition:
    """Describe one public job source used by the multi-source fetcher."""

    name: str
    url: str


@dataclass(frozen=True, slots=True)
class SourcePayload:
    """Store the raw HTTP response body for one successfully fetched source."""

    source: str
    url: str
    body: str


class MultiSourceJobFetcher:
    """Fetch multiple public job sources without any authentication workflow."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch_source_payloads(self, query: str | None = None) -> list[SourcePayload]:
        """
        Fetch each configured public source in order.

        Search text is still applied locally after parsing and normalization, so
        the query is logged for clarity but not sent upstream.
        """
        if query:
            logger.debug("Search query '%s' will be applied after parsing", query)

        payloads: list[SourcePayload] = []
        last_error: httpx.HTTPError | None = None

        async with httpx.AsyncClient(
            timeout=self.settings.http_timeout_seconds,
            follow_redirects=True,
            headers=self._build_headers(),
        ) as client:
            for source in self._get_sources():
                logger.info("Fetching public job listings from %s (%s)", source.name, source.url)
                try:
                    response = await client.get(source.url)
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    last_error = exc
                    logger.warning("Failed to fetch public source '%s': %s", source.name, exc)
                    continue

                body = response.text.strip()
                if not body:
                    logger.warning("Skipping public source '%s' because the response body was empty.", source.name)
                    continue

                payloads.append(SourcePayload(source=source.name, url=source.url, body=body))

        if payloads:
            return payloads

        if last_error is not None:
            raise last_error

        raise httpx.HTTPError("No public job sources returned data.")

    def _get_sources(self) -> list[SourceDefinition]:
        """Return the built-in public sources in their fallback order."""
        return [
            SourceDefinition(name="arbeitnow", url=self.settings.arbeitnow_source_url),
            SourceDefinition(name="remotive", url=self.settings.remotive_source_url),
            SourceDefinition(name="themuse", url=self.settings.themuse_source_url),
        ]

    @staticmethod
    def _build_headers() -> Mapping[str, str]:
        """Return the small set of headers used for normal public source requests."""
        return {
            "User-Agent": "JobIntelligenceAPI/0.1 (+public listing ingestion MVP)",
            "Accept": "application/json,text/html,application/xhtml+xml",
        }
