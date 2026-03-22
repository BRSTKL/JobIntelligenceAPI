import httpx
import pytest

from app.core.config import Settings
from app.services.multi_source_fetcher import MultiSourceJobFetcher


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeResponse:
    def __init__(self, url: str, body: str, status_code: int = 200) -> None:
        self.url = url
        self.text = body
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", self.url)
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("boom", request=request, response=response)


class FakeAsyncClient:
    def __init__(self, responses: dict[str, object], **kwargs) -> None:
        self.responses = responses

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str):
        outcome = self.responses[url]
        if isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, tuple):
            status_code, body = outcome
            return FakeResponse(url=url, body=body, status_code=status_code)
        return FakeResponse(url=url, body=str(outcome))


@pytest.mark.anyio
async def test_multi_source_fetcher_continues_when_one_source_fails(monkeypatch):
    settings = Settings(
        api_keys=("test-key",),
        arbeitnow_source_url="https://arbeitnow.test/jobs",
        remotive_source_url="https://remotive.test/jobs",
        themuse_source_url="https://themuse.test/jobs",
        kariyer_source_url="https://kariyer.test/jobs",
    )
    responses = {
        "https://arbeitnow.test/jobs": '{"jobs":[{"id":"1"}]}',
        "https://remotive.test/jobs": httpx.ConnectError("blocked"),
        "https://themuse.test/jobs": '{"results":[{"id":"3"}]}',
        "https://kariyer.test/jobs": "<html><body><div>kariyer</div></body></html>",
    }

    monkeypatch.setattr(
        "app.services.multi_source_fetcher.httpx.AsyncClient",
        lambda **kwargs: FakeAsyncClient(responses, **kwargs),
    )

    fetcher = MultiSourceJobFetcher(settings)
    payloads = await fetcher.fetch_source_payloads()

    assert [payload.source for payload in payloads] == ["arbeitnow", "themuse", "kariyer"]
    assert payloads[-1].payload_type == "html"


@pytest.mark.anyio
async def test_multi_source_fetcher_raises_when_all_sources_fail(monkeypatch):
    settings = Settings(
        api_keys=("test-key",),
        arbeitnow_source_url="https://arbeitnow.test/jobs",
        remotive_source_url="https://remotive.test/jobs",
        themuse_source_url="https://themuse.test/jobs",
        kariyer_source_url="https://kariyer.test/jobs",
    )
    responses = {
        "https://arbeitnow.test/jobs": httpx.ConnectError("blocked"),
        "https://remotive.test/jobs": httpx.ConnectError("blocked"),
        "https://themuse.test/jobs": httpx.ConnectError("blocked"),
        "https://kariyer.test/jobs": httpx.ConnectError("blocked"),
    }

    monkeypatch.setattr(
        "app.services.multi_source_fetcher.httpx.AsyncClient",
        lambda **kwargs: FakeAsyncClient(responses, **kwargs),
    )

    fetcher = MultiSourceJobFetcher(settings)

    with pytest.raises(httpx.HTTPError):
        await fetcher.fetch_source_payloads()
