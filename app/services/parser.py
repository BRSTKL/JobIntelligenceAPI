from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from app.models.schemas import RawJobListing
from app.services.multi_source_fetcher import SourcePayload


logger = logging.getLogger(__name__)

JOB_NODE_SELECTORS = ("tr.job", "article.job", "div.job", "section.job")
JOB_LINK_SELECTORS = ("a[itemprop='url']", "a.preventLink", "a[href]")
TITLE_SELECTORS = ("h2[itemprop='title']", "h2", "[data-position]", ".position h2")
COMPANY_SELECTORS = ("h3[itemprop='name']", "h3", "[data-company]", ".company h3")
LOCATION_SELECTORS = (
    ".location",
    "[data-location]",
    ".company_and_position .location",
    ".company .location",
)
SALARY_SELECTORS = (".salary", "[data-salary]")
DESCRIPTION_SELECTORS = (".description", ".description p", ".description-text", "[data-description]")
EMPLOYMENT_SELECTORS = (".employment", "[data-employment]")
REMOTE_SELECTORS = (".remote", "[data-remote]")
TAG_SELECTORS = (".tags h3", ".tags .tag", ".tag", ".skill", "[data-tag]")


class RemoteOkParser:
    """Parse a Remote OK style HTML page into raw listing records."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def parse_jobs(self, html: str | None) -> list[RawJobListing]:
        """Parse the source HTML into raw job listings without raising on bad rows."""
        payload = (html or "").strip()
        if self._looks_like_json(payload):
            return self._parse_json_jobs(payload)

        soup = BeautifulSoup(payload, "html.parser")
        job_nodes = self._find_job_nodes(soup)

        jobs: list[RawJobListing] = []
        seen_keys: set[str] = set()

        for node in job_nodes:
            job = self._safe_parse_node(node)
            if job is None or not self._has_usable_content(job):
                continue

            dedupe_key = self._build_dedupe_key(job)
            if dedupe_key in seen_keys:
                continue

            seen_keys.add(dedupe_key)
            jobs.append(job)

        return jobs

    def _looks_like_json(self, payload: str) -> bool:
        """Detect the public JSON feed so the parser can support both source formats."""
        return payload.startswith("[") or payload.startswith("{")

    def _parse_json_jobs(self, payload: str) -> list[RawJobListing]:
        """Parse the public Remote OK JSON feed into raw listing records."""
        try:
            records = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("Received JSON-like source payload that could not be decoded.")
            return []

        if isinstance(records, dict):
            records = [records]
        if not isinstance(records, list):
            return []

        jobs: list[RawJobListing] = []
        seen_keys: set[str] = set()

        for record in records:
            if not isinstance(record, dict):
                continue

            job = self._safe_parse_json_record(record)
            if job is None or not self._has_usable_content(job):
                continue

            dedupe_key = self._build_dedupe_key(job)
            if dedupe_key in seen_keys:
                continue

            seen_keys.add(dedupe_key)
            jobs.append(job)

        return jobs

    def _find_job_nodes(self, soup: BeautifulSoup) -> list[Tag]:
        """Return the first non-empty set of supported job-node selectors."""
        for selector in JOB_NODE_SELECTORS:
            nodes = soup.select(selector)
            if nodes:
                return [node for node in nodes if isinstance(node, Tag)]
        return []

    def _safe_parse_node(self, node: Tag) -> RawJobListing | None:
        """Parse one node and skip it if something unexpected goes wrong."""
        try:
            return self._build_raw_listing(node)
        except Exception:
            logger.warning("Skipping malformed job node during parse.", exc_info=True)
            return None

    def _safe_parse_json_record(self, record: dict[str, object]) -> RawJobListing | None:
        """Parse one JSON feed record and skip it if something unexpected goes wrong."""
        try:
            return self._build_raw_listing_from_json(record)
        except Exception:
            logger.warning("Skipping malformed JSON job record during parse.", exc_info=True)
            return None

    def _build_raw_listing(self, node: Tag) -> RawJobListing:
        """Build one raw listing using best-effort selector lookups."""
        source_job_id = self._read_first_attribute(node, ("data-id", "data-job-id", "id"))
        source_job_url = self._find_job_url(node)
        title = self._coalesce(
            self._read_first_text(node, TITLE_SELECTORS),
            self._read_first_attribute(node, ("data-position",)),
        )
        company = self._coalesce(
            self._read_first_text(node, COMPANY_SELECTORS),
            self._read_first_attribute(node, ("data-company",)),
        )
        location_raw = self._coalesce(
            self._read_first_text(node, LOCATION_SELECTORS),
            self._read_first_attribute(node, ("data-location",)),
        )
        salary_text = self._coalesce(
            self._read_first_text(node, SALARY_SELECTORS),
            self._read_first_attribute(node, ("data-salary",)),
        )
        description_text = self._coalesce(
            self._read_first_text(node, DESCRIPTION_SELECTORS),
            self._read_first_attribute(node, ("data-description",)),
        )
        posted_at_raw = self._find_posted_at(node)
        employment_type_raw = self._coalesce(
            self._read_first_text(node, EMPLOYMENT_SELECTORS),
            self._read_first_attribute(node, ("data-employment",)),
        )
        remote_type_raw = self._coalesce(
            self._read_first_text(node, REMOTE_SELECTORS),
            self._read_first_attribute(node, ("data-remote",)),
        )
        tags = self._collect_tags(node)

        return RawJobListing(
            source_job_id=source_job_id,
            source_job_url=source_job_url,
            title=self._clean_text(title),
            company=self._clean_text(company),
            location_raw=self._clean_text(location_raw),
            salary_text=self._clean_text(salary_text),
            description_text=self._clean_text(description_text),
            tags=tags,
            posted_at_raw=posted_at_raw,
            employment_type_raw=self._clean_text(employment_type_raw),
            remote_type_raw=self._clean_text(remote_type_raw),
        )

    def _build_raw_listing_from_json(self, record: dict[str, object]) -> RawJobListing:
        """Build one raw listing from the public Remote OK JSON feed."""
        return RawJobListing(
            source_job_id=self._clean_text(record.get("id")),
            source_job_url=self._coalesce(
                self._clean_text(record.get("url")),
                self._clean_text(record.get("apply_url")),
            ),
            title=self._clean_text(record.get("position")),
            company=self._clean_text(record.get("company")),
            location_raw=self._clean_text(record.get("location")),
            salary_text=self._build_salary_text_from_json(record),
            description_text=self._html_to_text(record.get("description")),
            tags=self._collect_json_tags(record.get("tags")),
            posted_at_raw=self._coalesce(
                self._clean_text(record.get("date")),
                self._clean_text(record.get("epoch")),
            ),
            employment_type_raw=None,
            remote_type_raw="remote",
        )

    def _find_job_url(self, node: Tag) -> str | None:
        """Resolve the first usable job link found in the node."""
        for selector in JOB_LINK_SELECTORS:
            link = node.select_one(selector)
            if link is None:
                continue

            href = self._clean_text(link.get("href"))
            if href is None:
                continue

            if href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            return urljoin(self.base_url, href)

        return None

    def _find_posted_at(self, node: Tag) -> str | None:
        """Return the raw posted-at value without attempting to parse it yet."""
        time_tag = node.select_one("time[datetime]")
        if time_tag and time_tag.get("datetime"):
            return self._clean_text(time_tag.get("datetime"))

        epoch_value = self._read_first_attribute(node, ("data-epoch",))
        if epoch_value:
            return epoch_value

        date_value = self._read_first_attribute(node, ("data-date",))
        if date_value:
            return date_value

        return None

    def _collect_tags(self, node: Tag) -> list[str]:
        """Collect tag-like values from common skill/tag selectors and data attributes."""
        tags: list[str] = []
        for element in self._select_many(node, TAG_SELECTORS):
            text = self._clean_text(element.get_text(" ", strip=True))
            if text and text not in tags:
                tags.append(text)

        raw_tags = self._read_first_attribute(node, ("data-tags",))
        if raw_tags:
            for value in raw_tags.split(","):
                cleaned = self._clean_text(value)
                if cleaned and cleaned not in tags:
                    tags.append(cleaned)

        return tags

    def _collect_json_tags(self, value: object | None) -> list[str]:
        """Collect tag values from the JSON feed while preserving order."""
        if value is None:
            return []

        tags: list[str] = []
        if isinstance(value, list):
            raw_values = value
        else:
            raw_values = str(value).split(",")

        for raw_value in raw_values:
            cleaned = self._clean_text(raw_value)
            if cleaned and cleaned not in tags:
                tags.append(cleaned)
        return tags

    def _build_salary_text_from_json(self, record: dict[str, object]) -> str | None:
        """Build a human-readable salary string from JSON feed min/max values."""
        salary_min = self._to_int(record.get("salary_min"))
        salary_max = self._to_int(record.get("salary_max"))

        if salary_min and salary_max:
            return f"${salary_min:,.0f} - ${salary_max:,.0f}"
        if salary_min:
            return f"${salary_min:,.0f}+"
        if salary_max:
            return f"Up to ${salary_max:,.0f}"
        return None

    def _html_to_text(self, value: object | None) -> str | None:
        """Convert small HTML description fragments into plain text."""
        cleaned_html = self._clean_text(value)
        if not cleaned_html:
            return None

        soup = BeautifulSoup(cleaned_html, "html.parser")
        return self._clean_text(soup.get_text(" ", strip=True))

    def _read_first_text(self, node: Tag, selectors: Iterable[str]) -> str | None:
        """Read the first non-empty text or content value for the given selectors."""
        for selector in selectors:
            element = node.select_one(selector)
            if element is None:
                continue

            if element.has_attr("content"):
                return self._clean_text(element.get("content"))

            return self._clean_text(element.get_text(" ", strip=True))

        return None

    def _read_first_attribute(self, node: Tag, attribute_names: Iterable[str]) -> str | None:
        """Read the first non-empty attribute value from the current node."""
        for attribute_name in attribute_names:
            cleaned = self._clean_text(node.get(attribute_name))
            if cleaned:
                return cleaned
        return None

    def _select_many(self, node: Tag, selectors: Iterable[str]) -> list[Tag]:
        """Return all matching tags for the provided selectors."""
        matches: list[Tag] = []
        for selector in selectors:
            for element in node.select(selector):
                if isinstance(element, Tag):
                    matches.append(element)
        return matches

    def _has_usable_content(self, job: RawJobListing) -> bool:
        """Keep rows that still have at least one useful identifier or display field."""
        return any(
            [
                job.source_job_id,
                job.source_job_url,
                job.title,
                job.company,
            ]
        )

    def _build_dedupe_key(self, job: RawJobListing) -> str:
        """Build a stable deduplication key from the best available fields."""
        return (
            job.source_job_id
            or job.source_job_url
            or f"{job.company or 'unknown-company'}::{job.title or 'unknown-title'}"
        )

    @staticmethod
    def _coalesce(*values: str | None) -> str | None:
        """Return the first non-empty string value."""
        for value in values:
            if value:
                return value
        return None

    @staticmethod
    def _clean_text(value: object | None) -> str | None:
        """Collapse whitespace and normalize empty values to None."""
        if value is None:
            return None

        cleaned = " ".join(str(value).split())
        return cleaned or None

    @staticmethod
    def _to_int(value: object | None) -> int | None:
        """Convert a numeric-looking value into an integer when possible."""
        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None


class PublicJobParser(RemoteOkParser):
    """Parse supported public source payloads into raw listing records."""

    def __init__(self, base_url: str | None = None) -> None:
        super().__init__(base_url or "")

    def parse_source_payloads(self, source_payloads: list[SourcePayload]) -> list[RawJobListing]:
        """Parse many fetched source payloads into one raw-job list."""
        raw_jobs: list[RawJobListing] = []
        for source_payload in source_payloads:
            raw_jobs.extend(self.parse_source_payload(source_payload))
        return raw_jobs

    def parse_source_payload(self, source_payload: SourcePayload) -> list[RawJobListing]:
        """Parse one fetched source payload using its source-specific mapping rules."""
        return self.parse_jobs(
            source_payload.body,
            source=source_payload.source,
            source_url=source_payload.url,
        )

    def parse_jobs(
        self,
        html: str | None,
        source: str | None = None,
        source_url: str | None = None,
    ) -> list[RawJobListing]:
        """Parse either supported JSON payloads or the legacy HTML fixture format."""
        payload = (html or "").strip()
        if not payload:
            return []

        if self._looks_like_json(payload):
            return self._parse_json_payload(payload, source)

        original_base_url = self.base_url
        if source_url:
            self.base_url = source_url
        try:
            jobs = super().parse_jobs(payload)
        finally:
            self.base_url = original_base_url

        if source:
            for job in jobs:
                job.source = source
        return jobs

    def _parse_json_payload(self, payload: str, source: str | None) -> list[RawJobListing]:
        """Parse a known JSON source payload without crashing on bad records."""
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("Received JSON-like source payload that could not be decoded.")
            return []

        if source == "arbeitnow":
            records = self._extract_sequence(data, primary_key="jobs", fallback_key="data")
            return self._parse_source_records(records, builder=self._build_arbeitnow_listing)
        if source == "remotive":
            records = self._extract_sequence(data, primary_key="jobs")
            return self._parse_source_records(records, builder=self._build_remotive_listing)
        if source == "themuse":
            records = self._extract_sequence(data, primary_key="results")
            return self._parse_source_records(records, builder=self._build_themuse_listing)

        return super()._parse_json_jobs(payload)

    def _extract_sequence(
        self,
        payload: object,
        primary_key: str,
        fallback_key: str | None = None,
    ) -> list[dict[str, object]]:
        """Read a list of record dictionaries from a source payload."""
        if isinstance(payload, list):
            return [record for record in payload if isinstance(record, dict)]
        if not isinstance(payload, dict):
            return []

        candidate = payload.get(primary_key)
        if not isinstance(candidate, list) and fallback_key:
            candidate = payload.get(fallback_key)
        if not isinstance(candidate, list):
            return []
        return [record for record in candidate if isinstance(record, dict)]

    def _parse_source_records(self, records: list[dict[str, object]], builder) -> list[RawJobListing]:
        """Build raw listings from many source records while skipping malformed entries."""
        jobs: list[RawJobListing] = []
        seen_keys: set[str] = set()

        for record in records:
            job = self._safe_parse_source_record(record, builder)
            if job is None or not self._has_usable_content(job):
                continue

            dedupe_key = self._build_dedupe_key(job)
            if dedupe_key in seen_keys:
                continue

            seen_keys.add(dedupe_key)
            jobs.append(job)

        return jobs

    def _safe_parse_source_record(self, record: dict[str, object], builder) -> RawJobListing | None:
        """Build one raw record and skip it if something unexpected goes wrong."""
        try:
            return builder(record)
        except Exception:
            logger.warning("Skipping malformed JSON job record during parse.", exc_info=True)
            return None

    def _build_arbeitnow_listing(self, record: dict[str, object]) -> RawJobListing:
        """Build one raw listing from the Arbeitnow job board API."""
        return RawJobListing(
            source="arbeitnow",
            source_job_id=self._coalesce(
                self._clean_text(record.get("slug")),
                self._clean_text(record.get("id")),
                self._clean_text(record.get("url")),
            ),
            source_job_url=self._clean_text(record.get("url")),
            title=self._clean_text(record.get("title")),
            company=self._clean_text(record.get("company_name")),
            location_raw=self._clean_text(record.get("location")),
            salary_text=None,
            description_text=self._html_to_text(record.get("description")),
            tags=self._collect_json_tags(record.get("tags")),
            posted_at_raw=self._clean_text(record.get("created_at")),
            employment_type_raw=self._coalesce(
                self._clean_text(record.get("employment_type")),
                self._clean_text(record.get("job_type")),
            ),
            remote_type_raw=self._build_remote_type_from_boolean(record.get("remote")),
        )

    def _build_remotive_listing(self, record: dict[str, object]) -> RawJobListing:
        """Build one raw listing from the Remotive remote jobs API."""
        return RawJobListing(
            source="remotive",
            source_job_id=self._coalesce(
                self._clean_text(record.get("id")),
                self._clean_text(record.get("url")),
            ),
            source_job_url=self._clean_text(record.get("url")),
            title=self._clean_text(record.get("title")),
            company=self._clean_text(record.get("company_name")),
            location_raw=self._clean_text(record.get("candidate_required_location")),
            salary_text=self._clean_text(record.get("salary")),
            description_text=self._html_to_text(record.get("description")),
            tags=self._collect_json_tags(record.get("tags")),
            posted_at_raw=self._clean_text(record.get("publication_date")),
            employment_type_raw=self._clean_text(record.get("job_type")),
            remote_type_raw="remote",
        )

    def _build_themuse_listing(self, record: dict[str, object]) -> RawJobListing:
        """Build one raw listing from The Muse public jobs API."""
        location_raw = self._flatten_themuse_locations(record.get("locations"))
        return RawJobListing(
            source="themuse",
            source_job_id=self._coalesce(
                self._clean_text(record.get("id")),
                self._read_nested_text(record, ("refs", "landing_page")),
            ),
            source_job_url=self._read_nested_text(record, ("refs", "landing_page")),
            title=self._clean_text(record.get("name")),
            company=self._read_nested_text(record, ("company", "name")),
            location_raw=location_raw,
            salary_text=None,
            description_text=self._html_to_text(record.get("contents")),
            tags=[],
            posted_at_raw=self._clean_text(record.get("publication_date")),
            employment_type_raw=self._clean_text(record.get("type")),
            remote_type_raw="remote" if location_raw and "remote" in location_raw.lower() else None,
        )

    def _flatten_themuse_locations(self, value: object | None) -> str | None:
        """Turn The Muse location arrays into one readable location string."""
        if not isinstance(value, list):
            return None

        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                cleaned = self._coalesce(
                    self._clean_text(item.get("name")),
                    self._clean_text(item.get("short_name")),
                )
            else:
                cleaned = self._clean_text(item)

            if cleaned and cleaned not in parts:
                parts.append(cleaned)

        if not parts:
            return None
        return ", ".join(parts)

    def _read_nested_text(self, payload: dict[str, object], path: tuple[str, ...]) -> str | None:
        """Read a nested dictionary string value."""
        current: object = payload
        for key in path:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        return self._clean_text(current)

    def _build_remote_type_from_boolean(self, value: object | None) -> str | None:
        """Map a boolean-like source value to a normalized remote hint."""
        truthy_value = self._to_bool(value)
        if truthy_value is True:
            return "remote"
        if truthy_value is False:
            return "onsite"
        return None

    @staticmethod
    def _to_bool(value: object | None) -> bool | None:
        """Convert a boolean-like value into True, False, or None."""
        if isinstance(value, bool):
            return value
        if value is None:
            return None

        cleaned = str(value).strip().lower()
        if cleaned in {"1", "true", "yes"}:
            return True
        if cleaned in {"0", "false", "no"}:
            return False
        return None
