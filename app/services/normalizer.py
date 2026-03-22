from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from pydantic import HttpUrl, TypeAdapter, ValidationError

from app.models.schemas import (
    EmploymentTypeEnum,
    JobRecord,
    LanguageCodeEnum,
    RawJobListing,
    RemoteTypeEnum,
    SeniorityLevelEnum,
)


logger = logging.getLogger(__name__)
HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)

SKILL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "aws": ("aws",),
    "azure": ("azure",),
    "beautifulsoup": ("beautifulsoup", "beautiful soup"),
    "celery": ("celery",),
    "css": ("css",),
    "data engineering": ("data engineering",),
    "django": ("django",),
    "docker": ("docker",),
    "fastapi": ("fastapi",),
    "flask": ("flask",),
    "gcp": ("gcp", "google cloud"),
    "git": ("git",),
    "go": ("go", "golang"),
    "graphql": ("graphql",),
    "html": ("html",),
    "httpx": ("httpx",),
    "java": ("java",),
    "javascript": ("javascript",),
    "kubernetes": ("kubernetes",),
    "linux": ("linux",),
    "machine learning": ("machine learning",),
    "mysql": ("mysql",),
    "node": ("node", "node.js", "nodejs"),
    "pandas": ("pandas",),
    "postgresql": ("postgresql",),
    "python": ("python",),
    "pytest": ("pytest",),
    "react": ("react",),
    "redis": ("redis",),
    "rest": ("rest", "restful"),
    "ruby": ("ruby",),
    "rust": ("rust",),
    "scala": ("scala",),
    "sql": ("sql",),
    "sqlite": ("sqlite",),
    "terraform": ("terraform",),
    "typescript": ("typescript",),
    "vue": ("vue", "vue.js"),
}

SKILL_ALIASES = {
    "bs4": "beautifulsoup",
    "k8s": "kubernetes",
    "node.js": "node",
    "nodejs": "node",
    "postgres": "postgresql",
    "py": "python",
    "ts": "typescript",
}

REMOTE_PATTERNS: dict[RemoteTypeEnum, tuple[re.Pattern[str], ...]] = {
    RemoteTypeEnum.hybrid: (
        re.compile(r"\bhybrid\b", re.IGNORECASE),
        re.compile(r"\bremote[-\s]?first\b", re.IGNORECASE),
    ),
    RemoteTypeEnum.onsite: (
        re.compile(r"\bonsite\b", re.IGNORECASE),
        re.compile(r"\bon[-\s]?site\b", re.IGNORECASE),
        re.compile(r"\bin[-\s]?office\b", re.IGNORECASE),
    ),
    RemoteTypeEnum.remote: (
        re.compile(r"\bremote\b", re.IGNORECASE),
        re.compile(r"\bwork from home\b", re.IGNORECASE),
        re.compile(r"\bworldwide\b", re.IGNORECASE),
        re.compile(r"\banywhere\b", re.IGNORECASE),
        re.compile(r"\bdistributed\b", re.IGNORECASE),
    ),
}

EMPLOYMENT_PATTERNS: dict[EmploymentTypeEnum, tuple[re.Pattern[str], ...]] = {
    EmploymentTypeEnum.full_time: (
        re.compile(r"\bfull[\s_-]?time\b", re.IGNORECASE),
        re.compile(r"\bpermanent\b", re.IGNORECASE),
    ),
    EmploymentTypeEnum.part_time: (re.compile(r"\bpart[\s_-]?time\b", re.IGNORECASE),),
    EmploymentTypeEnum.contract: (
        re.compile(r"\bcontract\b", re.IGNORECASE),
        re.compile(r"\bfreelance\b", re.IGNORECASE),
        re.compile(r"\bconsultant\b", re.IGNORECASE),
    ),
    EmploymentTypeEnum.internship: (
        re.compile(r"\bintern(ship)?\b", re.IGNORECASE),
        re.compile(r"\bapprentice(ship)?\b", re.IGNORECASE),
    ),
    EmploymentTypeEnum.temporary: (
        re.compile(r"\btemporary\b", re.IGNORECASE),
        re.compile(r"\btemp\b", re.IGNORECASE),
        re.compile(r"\bfixed[-\s]?term\b", re.IGNORECASE),
    ),
}

SENIORITY_PATTERNS: dict[SeniorityLevelEnum, tuple[re.Pattern[str], ...]] = {
    SeniorityLevelEnum.executive: (
        re.compile(r"\bchief\b", re.IGNORECASE),
        re.compile(r"\bexecutive\b", re.IGNORECASE),
        re.compile(r"\bcxo\b", re.IGNORECASE),
    ),
    SeniorityLevelEnum.director: (
        re.compile(r"\bdirector\b", re.IGNORECASE),
        re.compile(r"\bvp\b", re.IGNORECASE),
        re.compile(r"\bvice president\b", re.IGNORECASE),
    ),
    SeniorityLevelEnum.manager: (
        re.compile(r"\bmanager\b", re.IGNORECASE),
        re.compile(r"\bhead of\b", re.IGNORECASE),
    ),
    SeniorityLevelEnum.lead: (
        re.compile(r"\blead\b", re.IGNORECASE),
        re.compile(r"\bprincipal\b", re.IGNORECASE),
        re.compile(r"\bstaff\b", re.IGNORECASE),
    ),
    SeniorityLevelEnum.senior: (
        re.compile(r"\bsenior\b", re.IGNORECASE),
        re.compile(r"\bsr\.?\b", re.IGNORECASE),
    ),
    SeniorityLevelEnum.mid: (
        re.compile(r"\bmid[-\s]?level\b", re.IGNORECASE),
        re.compile(r"\bintermediate\b", re.IGNORECASE),
        re.compile(r"\bmid\b", re.IGNORECASE),
    ),
    SeniorityLevelEnum.junior: (
        re.compile(r"\bjunior\b", re.IGNORECASE),
        re.compile(r"\bjr\.?\b", re.IGNORECASE),
        re.compile(r"\bentry[-\s]?level\b", re.IGNORECASE),
    ),
    SeniorityLevelEnum.intern: (re.compile(r"\bintern(ship)?\b", re.IGNORECASE),),
}

TITLE_METADATA_PATTERN = re.compile(
    r"[\(\[\{][^)\]\}]*\b("
    r"remote|hybrid|on[-\s]?site|onsite|worldwide|anywhere|"
    r"full[\s-]?time|part[\s-]?time|contract|freelance|intern(ship)?|temporary|temp"
    r")\b[^)\]\}]*[\)\]\}]",
    re.IGNORECASE,
)
TITLE_NOISE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bremote\b", re.IGNORECASE),
    re.compile(r"\bhybrid\b", re.IGNORECASE),
    re.compile(r"\bonsite\b", re.IGNORECASE),
    re.compile(r"\bon[-\s]?site\b", re.IGNORECASE),
    re.compile(r"\bworldwide\b", re.IGNORECASE),
    re.compile(r"\banywhere\b", re.IGNORECASE),
    re.compile(r"\bfull[\s-]?time\b", re.IGNORECASE),
    re.compile(r"\bpart[\s-]?time\b", re.IGNORECASE),
    re.compile(r"\bcontract\b", re.IGNORECASE),
    re.compile(r"\bfreelance\b", re.IGNORECASE),
    re.compile(r"\btemporary\b", re.IGNORECASE),
    re.compile(r"\btemp\b", re.IGNORECASE),
    re.compile(r"\bsenior\b", re.IGNORECASE),
    re.compile(r"\bsr\.?\b", re.IGNORECASE),
    re.compile(r"\bjunior\b", re.IGNORECASE),
    re.compile(r"\bjr\.?\b", re.IGNORECASE),
    re.compile(r"\blead\b", re.IGNORECASE),
    re.compile(r"\bprincipal\b", re.IGNORECASE),
    re.compile(r"\bstaff\b", re.IGNORECASE),
    re.compile(r"\bmid[-\s]?level\b", re.IGNORECASE),
    re.compile(r"\bmid\b", re.IGNORECASE),
    re.compile(r"\bintern(ship)?\b", re.IGNORECASE),
)
TITLE_SEPARATOR_PATTERN = re.compile(r"\s*\|\s*")
TITLE_SPACED_BREAK_PATTERN = re.compile(r"\s(?:-|/)\s")
TITLE_ACRONYMS = {
    "ai": "AI",
    "api": "API",
    "aws": "AWS",
    "css": "CSS",
    "gcp": "GCP",
    "html": "HTML",
    "ios": "iOS",
    "ml": "ML",
    "qa": "QA",
    "sql": "SQL",
    "sre": "SRE",
    "ui": "UI",
    "ux": "UX",
}
LOWERCASE_TITLE_WORDS = {"and", "for", "in", "of", "on", "to", "with"}
IGNORED_SKILL_TAGS = {
    "anywhere",
    "contract",
    "full-time",
    "full time",
    "hybrid",
    "internship",
    "on-site",
    "onsite",
    "part-time",
    "part time",
    "remote",
    "temporary",
    "worldwide",
}
TURKISH_TITLE_CHARACTERS = set("\u00e7\u011f\u0131\u00f6\u015f\u00fc\u00c7\u011e\u0130\u00d6\u015e\u00dc\u0131")


class JobNormalizer:
    """Turn raw listings into normalized API records."""

    def __init__(
        self,
        source_name: str = "public-source",
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.default_source_name = source_name
        self.now_provider = now_provider or (lambda: datetime.now(tz=UTC))

    def normalize_jobs(self, jobs: list[RawJobListing]) -> list[JobRecord]:
        """Normalize many raw jobs while skipping any unexpected bad records."""
        normalized_jobs: list[JobRecord] = []
        for raw_job in jobs:
            try:
                normalized_jobs.append(self.normalize_job(raw_job))
            except Exception:
                logger.warning("Skipping raw job that could not be normalized.", exc_info=True)
        return normalized_jobs

    def normalize_job(self, raw_job: RawJobListing) -> JobRecord:
        """Normalize one raw job into the stable API response shape."""
        source_name = raw_job.source or self.default_source_name
        safe_source_job_url = self._normalize_source_job_url(raw_job.source_job_url)
        source_job_id = raw_job.source_job_id or self._fallback_source_job_id(raw_job, safe_source_job_url)
        identity = self._build_identity(source_name, source_job_id, safe_source_job_url)
        description_snippet = self._build_description_snippet(raw_job.description_text)
        posted_at = self._parse_posted_at(raw_job.posted_at_raw)
        evidence_text = self._build_evidence_text(raw_job, description_snippet)
        location_city, location_country = self._parse_location(raw_job.location_raw)

        return JobRecord(
            id=self._stable_hash(identity),
            source=source_name,
            source_job_id=source_job_id,
            source_job_url=safe_source_job_url,
            language=self._detect_language(raw_job.title),
            title=raw_job.title,
            normalized_title=self._normalize_title(raw_job.title),
            company=raw_job.company,
            location_raw=raw_job.location_raw,
            location_city=location_city,
            location_country=location_country,
            remote_type=self._extract_remote_type(evidence_text),
            employment_type=self._extract_employment_type(evidence_text),
            seniority_level=self._extract_seniority_level(evidence_text),
            salary_text=raw_job.salary_text,
            description_snippet=description_snippet,
            skills=self._extract_skills(raw_job.tags, raw_job.title, description_snippet),
            posted_at=posted_at,
            freshness_days=self._calculate_freshness_days(posted_at),
        )

    def _detect_language(self, title: str | None) -> LanguageCodeEnum:
        """Detect a simple tr/en language hint from Turkish title characters."""
        cleaned_title = self._clean_text(title) or ""
        if any(character in TURKISH_TITLE_CHARACTERS for character in cleaned_title):
            return LanguageCodeEnum.tr
        return LanguageCodeEnum.en

    def _build_identity(self, source_name: str, source_job_id: str, source_job_url: str | None) -> str:
        """Build a stable identity string for hashing into the internal job ID."""
        return f"{source_name}:{source_job_id}:{source_job_url or ''}"

    def _fallback_source_job_id(self, raw_job: RawJobListing, source_job_url: str | None) -> str:
        """Create a stable fallback source ID when the provider does not expose one."""
        seed = " | ".join(
            filter(
                None,
                [
                    source_job_url,
                    raw_job.source_job_url,
                    raw_job.company,
                    raw_job.title,
                    raw_job.location_raw,
                    raw_job.posted_at_raw,
                ],
            )
        ) or "missing-source-id"
        return self._stable_hash(seed)[:16]

    @staticmethod
    def _stable_hash(value: str) -> str:
        """Return a short stable hash for deterministic internal IDs."""
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]

    def _normalize_source_job_url(self, source_job_url: str | None) -> str | None:
        """Validate the source URL and return None when it is malformed."""
        cleaned_url = self._clean_text(source_job_url)
        if not cleaned_url:
            return None

        try:
            return str(HTTP_URL_ADAPTER.validate_python(cleaned_url))
        except ValidationError:
            return None

    def _normalize_title(self, title: str | None) -> str | None:
        """Remove common metadata from the title while keeping the role readable."""
        cleaned = self._clean_text(title)
        if not cleaned:
            return None

        normalized = TITLE_METADATA_PATTERN.sub(" ", cleaned)
        normalized = TITLE_SEPARATOR_PATTERN.sub(" ", normalized)
        normalized = TITLE_SPACED_BREAK_PATTERN.sub(" ", normalized)

        for pattern in TITLE_NOISE_PATTERNS:
            normalized = pattern.sub(" ", normalized)

        normalized = re.sub(r"[\(\)\[\]\{\},;:]+", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip(" -_/")
        if not normalized:
            return cleaned

        return self._smart_title_case(normalized)

    def _smart_title_case(self, title: str) -> str:
        """Apply a small amount of title-casing without breaking common acronyms."""
        words = title.split()
        normalized_words: list[str] = []

        for index, word in enumerate(words):
            lower_word = word.lower()
            if lower_word in TITLE_ACRONYMS:
                normalized_words.append(TITLE_ACRONYMS[lower_word])
            elif index > 0 and lower_word in LOWERCASE_TITLE_WORDS:
                normalized_words.append(lower_word)
            elif word.isupper() or word.islower():
                normalized_words.append(word.capitalize())
            else:
                normalized_words.append(word)

        return " ".join(normalized_words)

    def _parse_location(self, location_raw: str | None) -> tuple[str | None, str | None]:
        """Split a best-effort location into city and country parts."""
        cleaned_location = self._clean_text(location_raw)
        if not cleaned_location:
            return None, None

        lowered = cleaned_location.lower()
        if any(keyword in lowered for keyword in ("remote", "worldwide", "anywhere")):
            return None, None

        parts = [part.strip() for part in cleaned_location.split(",") if part.strip()]
        if len(parts) >= 2:
            return parts[0], parts[-1]
        if len(parts) == 1:
            return parts[0], None
        return None, None

    def _build_description_snippet(self, description_text: str | None, max_length: int = 280) -> str | None:
        """Create a short description snippet or return None when no description exists."""
        cleaned_description = self._clean_text(description_text)
        if not cleaned_description:
            return None

        if len(cleaned_description) <= max_length:
            return cleaned_description

        return f"{cleaned_description[: max_length - 3].rstrip()}..."

    def _build_evidence_text(self, raw_job: RawJobListing, description_snippet: str | None) -> str:
        """Join the fields used for heuristic inference into one searchable string."""
        return " ".join(
            filter(
                None,
                [
                    self._clean_text(raw_job.title),
                    description_snippet,
                    self._clean_text(raw_job.location_raw),
                    self._clean_text(raw_job.employment_type_raw),
                    self._clean_text(raw_job.remote_type_raw),
                    " ".join(raw_job.tags),
                ],
            )
        ).lower()

    def _extract_remote_type(self, evidence_text: str) -> RemoteTypeEnum | None:
        """Return a remote type only when the text contains clear evidence."""
        return self._match_first_enum(evidence_text, REMOTE_PATTERNS)

    def _extract_employment_type(self, evidence_text: str) -> EmploymentTypeEnum | None:
        """Return an employment type only when the text contains clear evidence."""
        return self._match_first_enum(evidence_text, EMPLOYMENT_PATTERNS)

    def _extract_seniority_level(self, evidence_text: str) -> SeniorityLevelEnum | None:
        """Return a seniority level only when the text contains clear evidence."""
        return self._match_first_enum(evidence_text, SENIORITY_PATTERNS)

    def _match_first_enum(self, text: str, patterns: dict) -> object | None:
        """Return the first enum value whose patterns match the provided text."""
        for enum_value, enum_patterns in patterns.items():
            if self._matches_any_pattern(text, enum_patterns):
                return enum_value
        return None

    @staticmethod
    def _matches_any_pattern(text: str, patterns: Iterable[re.Pattern[str]]) -> bool:
        """Check whether any compiled regex matches the provided text."""
        return any(pattern.search(text) for pattern in patterns)

    def _extract_skills(
        self,
        tags: list[str],
        title: str | None,
        description_snippet: str | None,
    ) -> list[str]:
        """Extract skills from source tags first, then enrich them from text."""
        skills: set[str] = set()

        for tag in tags:
            normalized_tag = self._normalize_skill_tag(tag)
            if normalized_tag:
                skills.add(normalized_tag)

        searchable_text = " ".join(filter(None, [self._clean_text(title), description_snippet])).lower()
        if searchable_text:
            for alias, canonical_name in SKILL_ALIASES.items():
                if self._contains_keyword(searchable_text, alias):
                    skills.add(canonical_name)

            for canonical_name, keywords in SKILL_KEYWORDS.items():
                if any(self._contains_keyword(searchable_text, keyword) for keyword in keywords):
                    skills.add(canonical_name)

        return sorted(skills)

    def _normalize_skill_tag(self, tag: str | None) -> str | None:
        """Turn a source tag into a stable skill value when it looks useful."""
        cleaned_tag = self._clean_text(tag)
        if not cleaned_tag:
            return None

        lowered = cleaned_tag.lower()
        if lowered in IGNORED_SKILL_TAGS:
            return None
        if lowered in SKILL_ALIASES:
            return SKILL_ALIASES[lowered]
        if lowered in SKILL_KEYWORDS:
            return lowered

        for canonical_name, keywords in SKILL_KEYWORDS.items():
            if lowered in keywords:
                return canonical_name

        return lowered

    @staticmethod
    def _contains_keyword(text: str, keyword: str) -> bool:
        """Match a keyword using boundaries when the term starts or ends with word characters."""
        pattern = re.escape(keyword)
        if keyword[:1].isalnum():
            pattern = rf"\b{pattern}"
        if keyword[-1:].isalnum():
            pattern = rf"{pattern}\b"
        return re.search(pattern, text, re.IGNORECASE) is not None

    @staticmethod
    def _parse_posted_at(posted_at_raw: str | None) -> datetime | None:
        """Parse an ISO or epoch timestamp into a UTC datetime."""
        cleaned_value = JobNormalizer._clean_text(posted_at_raw)
        if not cleaned_value:
            return None

        if cleaned_value.isdigit():
            epoch_value = int(cleaned_value)
            if len(cleaned_value) > 10:
                epoch_value = epoch_value // 1000
            return datetime.fromtimestamp(epoch_value, tz=UTC)

        candidate = cleaned_value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            return None

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    def _calculate_freshness_days(self, posted_at: datetime | None) -> int | None:
        """Return job age in days or None when the posted date is unknown."""
        if posted_at is None:
            return None

        now = self.now_provider()
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        else:
            now = now.astimezone(UTC)

        delta = now.date() - posted_at.date()
        return max(delta.days, 0)

    @staticmethod
    def _clean_text(value: object | None) -> str | None:
        """Collapse whitespace and normalize empty values to None."""
        if value is None:
            return None

        cleaned = " ".join(str(value).split())
        return cleaned or None
