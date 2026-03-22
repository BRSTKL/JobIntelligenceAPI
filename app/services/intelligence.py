from __future__ import annotations

from collections import Counter

from app.models.schemas import InsightItem, JobRecord


class IntelligenceService:
    """Build simple insight summaries from normalized jobs."""

    def top_skills(self, jobs: list[JobRecord], limit: int = 10) -> list[InsightItem]:
        counter: Counter[str] = Counter()
        for job in jobs:
            for skill in job.skills:
                counter[skill] += 1
        return self._to_items(counter, limit)

    def top_companies(self, jobs: list[JobRecord], limit: int = 10) -> list[InsightItem]:
        counter: Counter[str] = Counter()
        for job in jobs:
            if job.company:
                counter[job.company] += 1
        return self._to_items(counter, limit)

    def top_locations(self, jobs: list[JobRecord], limit: int = 10) -> list[InsightItem]:
        counter: Counter[str] = Counter()
        for job in jobs:
            location_name = job.location_raw or self._combine_location(job.location_city, job.location_country)
            if location_name:
                counter[location_name] += 1
        return self._to_items(counter, limit)

    @staticmethod
    def _combine_location(city: str | None, country: str | None) -> str | None:
        parts = [part for part in (city, country) if part]
        return ", ".join(parts) or None

    @staticmethod
    def _to_items(counter: Counter[str], limit: int) -> list[InsightItem]:
        return [InsightItem(name=name, count=count) for name, count in counter.most_common(limit)]
