#!/usr/bin/env python3
"""Resolve start.gg short URLs to tournament slugs."""

import sys
import requests


def resolve_tournament_slug_from_unique_string(unique_string: str) -> str:
    """
    Resolve a start.gg short URL to a full tournament slug.

    Args:
        unique_string: Short URL path (e.g., "abbey")

    Returns:
        Tournament slug (e.g., "tournament/melee-abbey-tavern-114")
    """
    response = requests.get(f"https://start.gg/{unique_string}", allow_redirects=True)
    return response.url.split("/")[-2]


def main():
    """CLI entry point for resolving tournament slugs."""
    if len(sys.argv) != 2:
        print("Usage: resolve_slug <short_url>", file=sys.stderr)
        print("Example: resolve_slug abbey", file=sys.stderr)
        sys.exit(1)

    short_url = sys.argv[1].strip()

    # Remove https://start.gg/ prefix if provided
    print(f'short_url: {short_url}')
    if short_url.startswith("https://start.gg/"):
        short_url = short_url.replace("https://start.gg/", "")
    elif short_url.startswith("http://start.gg/"):
        short_url = short_url.replace("http://start.gg/", "")
    elif short_url.startswith("start.gg/"):
        short_url = short_url.replace("start.gg/", "")
    elif short_url.startswith("www.start.gg"):
        short_url = short_url.replace("www.start.gg", "")

    try:
        slug = resolve_tournament_slug_from_unique_string(short_url)
        print(slug)
        sys.exit(0)
    except Exception as e:
        print(f"Error resolving slug: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
