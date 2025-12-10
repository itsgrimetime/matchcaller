#!/usr/bin/env python3
"""Resolve start.gg short URLs to tournament slugs.

This module provides robust resolution of start.gg short URLs (like "abbey")
to full tournament slugs (like "melee-abbey-tavern-123"). It handles start.gg's
dynamic rate limiting and bot detection with multiple fallback strategies.
"""

import json
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests


# Cache file location - stores resolved slugs to reduce API calls
CACHE_FILE = Path("/tmp/matchcaller_slug_cache.json")
CACHE_TTL_SECONDS = 3600  # 1 hour cache TTL


def _load_cache() -> dict:
    """Load the slug cache from disk."""
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return {}


def _save_cache(cache: dict) -> None:
    """Save the slug cache to disk."""
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except IOError:
        pass  # Cache save failure is non-fatal


def _get_cached_slug(unique_string: str) -> Optional[str]:
    """Get a cached slug if it exists and hasn't expired."""
    cache = _load_cache()
    entry = cache.get(unique_string)
    if entry:
        cached_time = entry.get("timestamp", 0)
        if time.time() - cached_time < CACHE_TTL_SECONDS:
            return entry.get("slug")
    return None


def _cache_slug(unique_string: str, slug: str) -> None:
    """Cache a resolved slug."""
    cache = _load_cache()
    cache[unique_string] = {
        "slug": slug,
        "timestamp": time.time(),
    }
    _save_cache(cache)


def _extract_slug_from_url(url: str) -> Optional[str]:
    """Extract tournament slug from a start.gg URL.

    Handles URLs like:
    - https://www.start.gg/tournament/melee-abbey-tavern-123/details
    - https://start.gg/tournament/melee-abbey-tavern-123/event/singles
    """
    if "/tournament/" not in url:
        return None

    # Split on /tournament/ and get the next path segment
    parts = url.split("/tournament/")
    if len(parts) < 2:
        return None

    # The slug is the first path segment after /tournament/
    slug_part = parts[1].split("/")[0]
    return slug_part if slug_part else None


def _resolve_via_head_request(unique_string: str) -> Optional[str]:
    """Try to resolve using HTTP HEAD request (lower bandwidth)."""
    try:
        response = requests.head(
            f"https://start.gg/{unique_string}",
            allow_redirects=True,
            timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; MatchCaller/1.0)",
            },
        )
        if response.status_code == 200:
            return _extract_slug_from_url(response.url)
    except requests.RequestException:
        pass
    return None


def _resolve_via_get_request(unique_string: str, use_browser_headers: bool = False) -> Optional[str]:
    """Try to resolve using HTTP GET request with optional browser-like headers."""
    headers = {}
    if use_browser_headers:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
    else:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; MatchCaller/1.0)",
        }

    try:
        response = requests.get(
            f"https://start.gg/{unique_string}",
            allow_redirects=True,
            timeout=15,
            headers=headers,
        )
        if response.status_code == 200:
            return _extract_slug_from_url(response.url)
    except requests.RequestException:
        pass
    return None


def _resolve_via_manual_redirects(unique_string: str) -> Optional[str]:
    """Manually follow redirects to handle edge cases better."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    })

    current_url = f"https://start.gg/{unique_string}"

    try:
        for _ in range(10):  # Max 10 redirects
            response = session.get(
                current_url,
                allow_redirects=False,
                timeout=10,
            )

            # If we got a successful response, check the URL
            if response.status_code == 200:
                slug = _extract_slug_from_url(current_url)
                if slug:
                    return slug
                break

            # If it's a redirect, follow it
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("Location")
                if not location:
                    break
                current_url = urljoin(current_url, location)

                # Check if we've arrived at a tournament URL
                slug = _extract_slug_from_url(current_url)
                if slug:
                    # Do one more request to confirm it's valid
                    final_response = session.get(current_url, allow_redirects=True, timeout=10)
                    if final_response.status_code == 200:
                        return _extract_slug_from_url(final_response.url)
            else:
                # Got an unexpected status code
                break
    except requests.RequestException:
        pass

    return None


def resolve_tournament_slug_from_unique_string(
    unique_string: str,
    use_cache: bool = True,
    max_retries: int = 3,
) -> str:
    """
    Resolve a start.gg short URL to a full tournament slug.

    Uses multiple strategies with fallbacks to handle start.gg's bot detection:
    1. Check cache for previously resolved slugs
    2. HTTP HEAD request (lower bandwidth)
    3. HTTP GET with simple headers
    4. HTTP GET with browser-like headers
    5. Manual redirect following

    Args:
        unique_string: Short URL path (e.g., "abbey")
        use_cache: Whether to use cached results (default: True)
        max_retries: Maximum retry attempts per strategy (default: 3)

    Returns:
        Tournament slug (e.g., "melee-abbey-tavern-114")

    Raises:
        RuntimeError: If all resolution strategies fail
    """
    # Check cache first
    if use_cache:
        cached = _get_cached_slug(unique_string)
        if cached:
            return cached

    # List of resolution strategies to try
    strategies = [
        ("HEAD request", lambda: _resolve_via_head_request(unique_string)),
        ("GET request", lambda: _resolve_via_get_request(unique_string, use_browser_headers=False)),
        ("GET with browser headers", lambda: _resolve_via_get_request(unique_string, use_browser_headers=True)),
        ("Manual redirects", lambda: _resolve_via_manual_redirects(unique_string)),
    ]

    last_error = None

    for _strategy_name, strategy_func in strategies:
        for attempt in range(max_retries):
            try:
                slug = strategy_func()
                if slug:
                    # Cache the successful result
                    if use_cache:
                        _cache_slug(unique_string, slug)
                    return slug
            except Exception as e:
                last_error = e

            # Exponential backoff between retries (0.5s, 1s, 2s)
            if attempt < max_retries - 1:
                time.sleep(0.5 * (2 ** attempt))

    raise RuntimeError(
        f"Failed to resolve slug for '{unique_string}' after trying all strategies. "
        f"Last error: {last_error}"
    )


def _normalize_short_url(short_url: str) -> str:
    """Normalize a short URL by removing common prefixes."""
    prefixes = [
        "https://www.start.gg/",
        "https://start.gg/",
        "http://www.start.gg/",
        "http://start.gg/",
        "www.start.gg/",
        "start.gg/",
    ]
    for prefix in prefixes:
        if short_url.startswith(prefix):
            return short_url[len(prefix):]
    return short_url


def clear_cache() -> None:
    """Clear the slug resolution cache."""
    try:
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
    except IOError:
        pass


def main():
    """CLI entry point for resolving tournament slugs."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Resolve start.gg short URLs to tournament slugs"
    )
    parser.add_argument("short_url", help="Short URL or unique string (e.g., 'abbey')")
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip cache lookup and force fresh resolution",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear the cache before resolving",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    if args.clear_cache:
        clear_cache()
        if args.verbose:
            print("Cache cleared", file=sys.stderr)

    short_url = _normalize_short_url(args.short_url.strip())

    if args.verbose:
        print(f"Resolving: {short_url}", file=sys.stderr)

    try:
        slug = resolve_tournament_slug_from_unique_string(
            short_url,
            use_cache=not args.no_cache,
        )
        print(slug)
        sys.exit(0)
    except Exception as e:
        print(f"Error resolving slug: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
