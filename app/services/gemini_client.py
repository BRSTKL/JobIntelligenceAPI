from __future__ import annotations

import json
import re
from collections.abc import Sequence

from google import genai

from app.core.exceptions import AIConfigurationError, AIProviderError, AIResponseError
from app.models.schemas import JobRecord

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class GeminiClientService:
    """A small wrapper around Google Gemini for structured JSON tasks."""

    def __init__(self, api_key: str | None, model_name: str = DEFAULT_GEMINI_MODEL) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self._client: genai.Client | None = None

    def match_jobs(
        self,
        *,
        skills: Sequence[str],
        experience_years: int,
        preferred_location: str | None,
        remote_preferred: bool | None,
        jobs: Sequence[JobRecord],
    ) -> list[str]:
        """Return ranked job IDs from Gemini as a validated list."""
        compact_jobs = [self._job_to_prompt_payload(job) for job in jobs]
        prompt = (
            f"Given these candidate skills: {list(skills)}\n"
            f"Experience: {experience_years} years\n"
            f"Location preference: {preferred_location}\n"
            f"Remote preference: {remote_preferred}\n\n"
            f"From these job listings: {json.dumps(compact_jobs, ensure_ascii=False)}\n\n"
            'Return top 5 best matching job IDs as JSON array:\n["id1", "id2", "id3", "id4", "id5"]\n\n'
            "Only return the JSON array, nothing else."
        )
        payload = self._generate_json(prompt, expected_type=list)

        job_ids: list[str] = []
        for value in payload:
            if isinstance(value, str) and value.strip():
                job_ids.append(value.strip())
        return job_ids

    def analyze_skills_gap(
        self,
        *,
        current_skills: Sequence[str],
        target_job_title: str,
    ) -> dict[str, object]:
        """Return a structured skill-gap analysis object from Gemini."""
        prompt = (
            f"A person knows: {list(current_skills)}\n"
            f"They want to become: {target_job_title}\n\n"
            "Return a JSON object:\n"
            "{\n"
            "  \"missing_skills\": [\"kubernetes\", \"terraform\"],\n"
            "  \"learning_priority\": \"high/medium/low\",\n"
            "  \"estimated_learning_time\": \"3-6 months\",\n"
            "  \"recommended_resources\": [\"resource1\", \"resource2\"]\n"
            "}\n"
            "Only return JSON, nothing else."
        )
        payload = self._generate_json(prompt, expected_type=dict)
        return payload

    def _generate_json(self, prompt: str, expected_type: type[list] | type[dict]) -> list[object] | dict[str, object]:
        """Run Gemini and parse the returned JSON payload."""
        client = self._get_client()

        try:
            response = client.models.generate_content(model=self.model_name, contents=prompt)
        except Exception as exc:
            raise AIProviderError("Gemini request failed.", details=[str(exc)]) from exc

        response_text = self._extract_text(response)
        json_text = self._clean_json_text(response_text)
        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError as exc:
            raise AIResponseError("Gemini returned invalid JSON.", details=[str(exc)]) from exc

        if not isinstance(parsed, expected_type):
            raise AIResponseError(
                "Gemini returned JSON in an unexpected shape.",
                details=[f"Expected JSON {expected_type.__name__}."],
            )

        return parsed

    def _get_client(self) -> genai.Client:
        """Build a Gemini client only when one of the AI endpoints is used."""
        if not self.api_key:
            raise AIConfigurationError(
                "GEMINI_API_KEY is not configured.",
                details=["Set GEMINI_API_KEY to enable AI endpoints."],
            )

        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    @staticmethod
    def _extract_text(response: object) -> str:
        """Read the text value from a Gemini response object."""
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text

        raise AIResponseError("Gemini returned an empty response.", details=["No text content was available."])

    @staticmethod
    def _clean_json_text(value: str) -> str:
        """Remove markdown code fences and trim whitespace around JSON."""
        cleaned = value.strip()
        cleaned = CODE_FENCE_PATTERN.sub("", cleaned).strip()
        return cleaned

    @staticmethod
    def _job_to_prompt_payload(job: JobRecord) -> dict[str, object]:
        """Keep the Gemini job context compact and matching-focused."""
        payload = job.model_dump(mode="json")
        return {
            "id": payload["id"],
            "title": payload["title"],
            "normalized_title": payload["normalized_title"],
            "company": payload["company"],
            "location_raw": payload["location_raw"],
            "remote_type": payload["remote_type"],
            "employment_type": payload["employment_type"],
            "seniority_level": payload["seniority_level"],
            "skills": payload["skills"],
            "language": payload["language"],
        }
