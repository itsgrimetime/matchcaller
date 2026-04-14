"""Tests for start.gg short URL resolution."""

import pytest

from matchcaller.utils import resolve


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int,
        url: str,
        headers: dict[str, str] | None = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self.url = url
        self.headers = headers or {}
        self.text = text


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.headers = {}

    def get(self, *args, **kwargs):
        return self.response


def test_short_url_resolution_reports_cloudflare_challenge(monkeypatch):
    challenge = FakeResponse(
        status_code=403,
        url="https://www.start.gg/abbey",
        headers={"cf-mitigated": "challenge"},
        text="<html><head><title>Just a moment...</title></head></html>",
    )

    monkeypatch.setattr(resolve.requests, "head", lambda *args, **kwargs: challenge)
    monkeypatch.setattr(resolve.requests, "get", lambda *args, **kwargs: challenge)
    monkeypatch.setattr(resolve.requests, "Session", lambda: FakeSession(challenge))

    with pytest.raises(RuntimeError) as exc_info:
        resolve.resolve_tournament_slug_from_unique_string(
            "abbey",
            use_cache=False,
            max_retries=1,
        )

    message = str(exc_info.value)
    assert "Cloudflare challenge" in message
    assert "HTTP 403" in message
    assert "https://www.start.gg/abbey" in message
    assert "--slug tournament/" in message


def test_short_url_resolution_reports_no_tournament_redirect(monkeypatch):
    normal_page = FakeResponse(
        status_code=200,
        url="https://www.start.gg/abbey",
        text="<html><head><title>start.gg</title></head></html>",
    )

    monkeypatch.setattr(resolve.requests, "head", lambda *args, **kwargs: normal_page)
    monkeypatch.setattr(resolve.requests, "get", lambda *args, **kwargs: normal_page)
    monkeypatch.setattr(resolve.requests, "Session", lambda: FakeSession(normal_page))

    with pytest.raises(RuntimeError) as exc_info:
        resolve.resolve_tournament_slug_from_unique_string(
            "abbey",
            use_cache=False,
            max_retries=1,
        )

    message = str(exc_info.value)
    assert "No strategy returned a tournament URL" in message
    assert "Last error: None" not in message
