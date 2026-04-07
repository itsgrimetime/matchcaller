"""HTTP transport abstractions for API clients."""

import json
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

import aiohttp


@dataclass(frozen=True)
class HTTPResult:
    """Structured HTTP result with parsed JSON when available."""

    status: int
    text: str
    json_data: Any | None = None


class HTTPTransport(Protocol):
    """Minimal transport interface for JSON-oriented HTTP requests."""

    async def post_json(
        self,
        url: str,
        *,
        payload: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> HTTPResult:
        """Send a POST request with a JSON body."""

    async def get_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> HTTPResult:
        """Send a GET request expecting a JSON response."""


class AiohttpTransport:
    """Default transport backed by aiohttp."""

    async def post_json(
        self,
        url: str,
        *,
        payload: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> HTTPResult:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=dict(payload),
                headers=dict(headers),
                timeout=aiohttp.ClientTimeout(total=timeout_seconds),
            ) as response:
                return await self._build_result(response)

    async def get_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> HTTPResult:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=dict(headers),
                timeout=aiohttp.ClientTimeout(total=timeout_seconds),
            ) as response:
                return await self._build_result(response)

    @staticmethod
    async def _build_result(response: aiohttp.ClientResponse) -> HTTPResult:
        """Read the response body once and parse JSON when possible."""
        text = await response.text()
        json_data: Any | None = None
        if text:
            try:
                json_data = json.loads(text)
            except json.JSONDecodeError:
                json_data = None
        return HTTPResult(status=response.status, text=text, json_data=json_data)
