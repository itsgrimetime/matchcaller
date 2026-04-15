"""Helpers for fetching paginated start.gg event set data."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

import aiohttp

from .queries import EVENT_SETS_QUERY
from .transport import HTTPTransport
from ..utils.logging import log


EVENT_SETS_PAGE_SIZE = 80
MAX_EVENT_SET_PAGES = 10


def _event_set_nodes(raw_data: Mapping[str, Any]) -> list[Any]:
    sets = (((raw_data.get("data") or {}).get("event") or {}).get("sets") or {})
    nodes = sets.get("nodes") or []
    return nodes if isinstance(nodes, list) else []


def _event_set_total_pages(raw_data: Mapping[str, Any]) -> int | None:
    sets = (((raw_data.get("data") or {}).get("event") or {}).get("sets") or {})
    page_info = sets.get("pageInfo") or {}
    total_pages = page_info.get("totalPages")
    return total_pages if isinstance(total_pages, int) else None


def _merge_event_set_pages(pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge multiple event-set pages into one start.gg-like payload."""
    if not pages:
        return {}

    merged = deepcopy(pages[0])
    merged_nodes: list[Any] = []
    for page in pages:
        merged_nodes.extend(_event_set_nodes(page))

    sets = (((merged.get("data") or {}).get("event") or {}).get("sets") or {})
    sets["nodes"] = merged_nodes
    return merged


async def fetch_event_sets_payload(
    *,
    transport: HTTPTransport,
    base_url: str,
    headers: dict[str, str],
    event_id: str,
    timeout_seconds: float = 10,
    per_page: int = EVENT_SETS_PAGE_SIZE,
    max_pages: int = MAX_EVENT_SET_PAGES,
) -> dict[str, Any]:
    """Fetch active event sets in pages that stay under start.gg complexity caps."""
    pages: list[dict[str, Any]] = []
    page = 1
    total_pages: int | None = None

    while True:
        variables = {"eventId": event_id, "page": page, "perPage": per_page}
        response = await transport.post_json(
            base_url,
            payload={"query": EVENT_SETS_QUERY, "variables": variables},
            headers=headers,
            timeout_seconds=timeout_seconds,
        )
        log(f"📡 Event sets page {page} API Response Status: {response.status}")

        if response.status != 200:
            error_text = response.text or str(response.json_data)
            raise aiohttp.ClientError(f"HTTP {response.status}: {error_text}")

        if not isinstance(response.json_data, dict):
            raise ValueError("Expected JSON object from start.gg API")

        raw_data = response.json_data
        pages.append(raw_data)
        if raw_data.get("errors"):
            return _merge_event_set_pages(pages)

        nodes = _event_set_nodes(raw_data)
        total_pages = _event_set_total_pages(raw_data) or total_pages
        if total_pages is not None:
            if page >= total_pages:
                break
        elif len(nodes) < per_page:
            break

        if page >= max_pages:
            log(
                "⚠️  Reached max event-set pages while fetching active matches: "
                f"{max_pages}"
            )
            break
        page += 1

    if len(pages) > 1:
        set_count = sum(len(_event_set_nodes(page)) for page in pages)
        log(f"✅ Fetched {set_count} sets across {len(pages)} pages")
    return _merge_event_set_pages(pages)
