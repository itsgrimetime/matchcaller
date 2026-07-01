"""Main entry point for the tournament display application."""

import argparse
import os
import sys
import time

from .ui import TournamentDisplay
from .utils.logging import log


def _normalize_short_url(short_url: str) -> str:
    """Normalize a start.gg short URL into the slug sent to GraphQL."""
    normalized = short_url.strip().rstrip("/").lower()
    for prefix in (
        "https://www.start.gg/",
        "https://start.gg/",
        "http://www.start.gg/",
        "http://start.gg/",
        "www.start.gg/",
        "start.gg/",
    ):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break
    return normalized


def _is_event_slug(slug: str) -> bool:
    """Return whether a normalized start.gg slug points at a specific event."""
    return "/event/" in slug


def _is_auto_event_filter(event_filter: str | None) -> bool:
    """Return whether event selection should combine active tournament events."""
    return (event_filter or "").lower() == "auto"


def _normalize_event_filter(event_filter: str | None) -> str | None:
    """Normalize a CLI/env event filter value."""
    if event_filter is None:
        return None
    normalized = event_filter.strip()
    return normalized or None


def _bare_tournament_slug(slug: str) -> str:
    """Return the tournament-name part from a start.gg tournament path."""
    normalized = _normalize_short_url(slug)
    if normalized.startswith("tournament/"):
        parts = normalized.split("/")
        if len(parts) >= 2:
            return parts[1]
    return normalized.split("/")[0]


def _tournament_lookup_candidates(tournament_slug: str) -> list[str]:
    """Build start.gg tournament slug variants to try for event discovery."""
    normalized = _normalize_short_url(tournament_slug)
    if normalized.startswith("tournament/"):
        parts = normalized.split("/")
        if len(parts) >= 2:
            normalized = f"tournament/{parts[1]}"

    candidates = [normalized]
    bare_slug = _bare_tournament_slug(normalized)
    full_slug = f"tournament/{bare_slug}"
    for candidate in (bare_slug, full_slug):
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _resolve_event_from_tournament(
    api,
    tournament_slug: str,
    event_filter: str | None,
) -> tuple[str, str]:
    """Resolve a tournament slug/page to a selected event slug."""
    import asyncio
    from .api.dashboard_api import derive_tournament_slug_from_event_slug

    normalized = _normalize_short_url(tournament_slug)
    if _is_event_slug(normalized):
        resolved_tournament_slug = (
            derive_tournament_slug_from_event_slug(normalized)
            or _bare_tournament_slug(normalized)
        )
        return normalized, resolved_tournament_slug

    for lookup_slug in _tournament_lookup_candidates(normalized):
        events = asyncio.run(api.get_events_for_tournament(lookup_slug))
        if not events:
            continue

        chosen = _choose_event(events, event_filter)
        resolved_tournament_slug = (
            derive_tournament_slug_from_event_slug(chosen["slug"])
            or _bare_tournament_slug(lookup_slug)
        )
        log(f"✅ Resolved tournament slug: {resolved_tournament_slug}")
        log(f"✅ Selected event: {chosen['name']} (slug: {chosen['slug']})")
        return chosen["slug"], resolved_tournament_slug

    raise RuntimeError(f"No events found for tournament: {normalized}")


def _is_abbey_short_url(short_url: str) -> bool:
    """Return whether a short URL is the Abbey weekly shortcut."""
    return _normalize_short_url(short_url) == "abbey"


def _choose_event(
    events: list[dict[str, str]],
    event_filter: str | None,
) -> dict[str, str]:
    """Pick the event matching the user's filter, avoiding waitlists when possible."""
    viable_events = [
        ev for ev in events
        if "waitlist" not in ev["name"].lower()
    ] or events

    def event_matches(event: dict[str, str], keyword: str) -> bool:
        return keyword in event["name"].lower() or keyword in event["slug"].lower()

    def first_matching(keywords: tuple[str, ...]) -> dict[str, str] | None:
        for keyword in keywords:
            for event in viable_events:
                if event_matches(event, keyword):
                    return event
        return None

    if event_filter:
        keyword = event_filter.lower()
        if keyword == "auto":
            return (
                first_matching(("doubles", "teams", "2v2"))
                or first_matching(("singles",))
                or viable_events[0]
            )

        matches = [
            ev for ev in events
            if event_matches(ev, keyword)
        ]
        non_waitlist = [
            ev for ev in matches
            if "waitlist" not in ev["name"].lower()
        ]
        if non_waitlist:
            return non_waitlist[0]
        if matches:
            return matches[0]

    return events[0]


class MatchCallerArgs(argparse.Namespace):
    token: str | None = None
    event: str | None = None
    slug: str | None = None
    tournament: str | None = None
    short_url: str | None = None
    event_filter: str | None = None
    demo: bool = False
    simulate: str | None = None
    jsonbin_id: str | None = None
    jsonbin_key: str | None = None
    view: str = "auto"


def cleanup_terminal():
    """Cleanup terminal state to prevent mouse tracking issues"""
    try:
        import sys

        sys.stdout.write(
            "\033[?1000l\033[?1003l\033[?1015l\033[?1006l\033[?25h\033[?1004l"
        )
        sys.stdout.flush()
    except Exception:
        pass


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Tournament Display TUI")
    parser.add_argument("--token", help="start.gg API token")
    parser.add_argument("--event", help="start.gg event ID")
    parser.add_argument(
        "--slug",
        help=(
            "start.gg event slug/URL, or a tournament slug/page when paired with "
            "--event-filter"
        ),
    )
    parser.add_argument(
        "--tournament",
        "--tournament-slug",
        dest="tournament",
        help="start.gg tournament slug/page; use --event-filter to pick auto/singles/doubles",
    )
    parser.add_argument(
        "--short-url",
        help="start.gg short URL (e.g., 'abbey') - resolves to tournament slug automatically",
    )
    parser.add_argument(
        "--event-filter",
        help=(
            "Keyword to match the right event when selecting from a tournament "
            "(auto, singles, doubles). Defaults to EVENT_FILTER when set."
        ),
    )
    parser.add_argument("--demo", action="store_true", help="Run with demo data")
    parser.add_argument(
        "--simulate",
        help="Run with simulated data from cloned tournament file",
    )
    parser.add_argument(
        "--jsonbin-id",
        help="jsonbin.io bin ID for late arrival / DQ alerts from Discord bot",
    )
    parser.add_argument(
        "--jsonbin-key",
        help="jsonbin.io API key (X-Master-Key) for private bins",
    )
    parser.add_argument(
        "--view",
        choices=["auto", "main", "split", "ladder"],
        default="auto",
        help="Display mode: auto, main, split, or ladder",
    )

    args: MatchCallerArgs = parser.parse_args(namespace=MatchCallerArgs())
    if args.event_filter is None:
        args.event_filter = os.environ.get("EVENT_FILTER")
    args.event_filter = _normalize_event_filter(args.event_filter)
    resolved_tournament_slug = None
    multi_event_tournament_slug = None

    log("🔍 Command line args:")
    log(f"   Token: {'***' if args.token else 'None'}")
    log(f"   Event: {args.event}")
    log(f"   Slug: {args.slug}")
    log(f"   Tournament: {args.tournament}")
    log(f"   Short URL: {args.short_url}")
    log(f"   Event Filter: {args.event_filter}")
    log(f"   Demo: {args.demo}")
    log(f"   Simulate: {args.simulate}")
    log(f"   JsonBin ID: {args.jsonbin_id or 'None'}")
    log(f"   JsonBin Key: {'***' if args.jsonbin_key else 'None'}")
    log(f"   View: {args.view}")

    if args.slug:
        args.slug = _normalize_short_url(args.slug)

    # Resolve a tournament slug/page to one event, unless auto mode should
    # combine active singles/doubles events from that tournament on each refresh.
    if args.token and not args.event and (args.tournament or args.slug):
        tournament_arg = args.tournament
        if not tournament_arg and args.slug and not _is_event_slug(args.slug):
            tournament_arg = args.slug

        if tournament_arg and _is_auto_event_filter(args.event_filter):
            multi_event_tournament_slug = _bare_tournament_slug(tournament_arg)
            resolved_tournament_slug = multi_event_tournament_slug
            args.slug = None
            log(
                "🔍 Auto event mode enabled for tournament: "
                f"{multi_event_tournament_slug}"
            )
        elif tournament_arg:
            log(
                "🔍 Resolving tournament event: "
                f"{tournament_arg} filter={args.event_filter or 'first event'}"
            )
            try:
                from .api import TournamentAPI

                tmp_api = TournamentAPI(api_token=args.token)
                args.slug, resolved_tournament_slug = _resolve_event_from_tournament(
                    tmp_api,
                    tournament_arg,
                    args.event_filter,
                )
            except Exception as e:
                log(f"❌ Failed to resolve tournament event: {e}")
                sys.exit(1)

    # Resolve --short-url to a full event slug
    if args.short_url and args.token and not args.slug:
        log(f"🔍 Resolving short URL: {args.short_url}")
        try:
            import asyncio
            from .api import TournamentAPI
            from .api.dashboard_api import derive_tournament_slug_from_event_slug
            from .utils.resolve import resolve_tournament_slug_from_unique_string

            tmp_api = TournamentAPI(api_token=args.token)
            short_url_slug = _normalize_short_url(args.short_url)
            tournament_slug = None

            events = asyncio.run(tmp_api.get_events_for_tournament(short_url_slug))
            if events:
                log(f"✅ Resolved short URL via start.gg API alias: {short_url_slug}")
            else:
                is_abbey_short_url = _is_abbey_short_url(short_url_slug)
                if is_abbey_short_url:
                    log("🔍 Falling back to start.gg API search for Abbey weekly")
                    tournament_slug = asyncio.run(
                        tmp_api.find_nearest_abbey_tournament_slug()
                    )

                if not tournament_slug:
                    try:
                        tournament_slug = resolve_tournament_slug_from_unique_string(
                            short_url_slug
                        )
                    except Exception as resolve_error:
                        if not is_abbey_short_url:
                            raise
                        log(f"⚠️  Short URL redirect resolution failed: {resolve_error}")
                        raise RuntimeError(
                            "Could not find a nearby Melee @ Abbey Tavern tournament "
                            "via start.gg API search or web redirect"
                        ) from resolve_error
                events = asyncio.run(tmp_api.get_events_for_tournament(tournament_slug))

            if not events:
                log(
                    "❌ No events found for tournament: "
                    f"{tournament_slug or short_url_slug}"
                )
                sys.exit(1)

            if _is_auto_event_filter(args.event_filter):
                first_event_slug = events[0].get("slug") if events else None
                resolved_tournament_slug = (
                    tournament_slug
                    or derive_tournament_slug_from_event_slug(first_event_slug)
                    or short_url_slug
                )
                multi_event_tournament_slug = resolved_tournament_slug
                log(
                    "✅ Auto event mode enabled for tournament: "
                    f"{resolved_tournament_slug}"
                )
            else:
                # Pick the matching event, deprioritizing waitlist/staging events.
                chosen = _choose_event(events, args.event_filter)
                args.slug = chosen["slug"]
                resolved_tournament_slug = (
                    tournament_slug
                    or derive_tournament_slug_from_event_slug(args.slug)
                    or short_url_slug
                )
                log(f"✅ Resolved tournament slug: {resolved_tournament_slug}")
                log(f"✅ Selected event: {chosen['name']} (slug: {args.slug})")
        except Exception as e:
            log(f"❌ Failed to resolve short URL: {e}")
            sys.exit(1)

    if args.simulate:
        log("🎮 Running in SIMULATION mode")
        log(f"📁 Loading tournament data from: {args.simulate}")

        # Import simulator components
        from .simulator.bracket_simulator import (
            BracketSimulator,
            SimulatedTournamentAPI,
        )

        # Create simulator
        simulator = BracketSimulator(args.simulate, speed_multiplier=60.0)
        if not simulator.load_tournament():
            log("❌ Failed to load tournament data")
            sys.exit(1)

        log("✅ Tournament data loaded successfully")
        log("🎬 Simulation will start when TUI launches")
        log("   Press Ctrl+C to exit\n")
        time.sleep(1)

        # Create and run app with simulation directly
        app_kwargs = {
            "api_token": None,
            "event_id": None,
            "event_slug": None,
            "tournament_slug": None,
            "view_mode": "main",
        }
        if args.jsonbin_id is not None:
            app_kwargs["jsonbin_id"] = args.jsonbin_id
        if args.jsonbin_key is not None:
            app_kwargs["jsonbin_key"] = args.jsonbin_key
        app = TournamentDisplay(
            **app_kwargs,
            api=SimulatedTournamentAPI(simulator),
        )

        try:
            log("🏁 Starting simulation...")
            # TODO: Integrate simulation with TUI properly
            app.run()
            log("🏁 Simulation finished")
        except KeyboardInterrupt:
            log("\n👋 Simulation stopped")
        except Exception as e:
            log(f"❌ Simulation crashed: {type(e).__name__}: {e}")
        finally:
            cleanup_terminal()

        return  # Exit early for simulation mode

    elif args.demo:
        log("🏆 Running in DEMO mode with mock data")
        log("   Use --token and (--event or --slug) for real data")
        log("   Press Ctrl+C to exit\n")
        time.sleep(2)
        # Force None values in demo mode
        token_to_use = None
        event_to_use = None
        slug_to_use = None
        tournament_slug_to_use = None
        view_mode_to_use = "main"
    elif not args.token or (
        not args.event
        and not args.slug
        and not multi_event_tournament_slug
    ):
        log("🏆 Running in DEMO mode with mock data")
        log("   Use --token and (--event or --slug) for real data")
        log("   Press Ctrl+C to exit\n")
        time.sleep(2)
        # Force None values in demo mode
        token_to_use = None
        event_to_use = None
        slug_to_use = None
        tournament_slug_to_use = None
        view_mode_to_use = "main"
    else:
        log("🌐 Running with REAL start.gg data")
        log("   Press Ctrl+C to exit\n")
        time.sleep(1)
        token_to_use = args.token
        event_to_use = args.event
        slug_to_use = args.slug
        from .api.dashboard_api import derive_tournament_slug_from_event_slug

        tournament_slug_to_use = (
            resolved_tournament_slug
            or derive_tournament_slug_from_event_slug(args.slug)
        )
        view_mode_to_use = args.view

    api_source = None
    if token_to_use and multi_event_tournament_slug:
        from .api import MultiEventTournamentAPI

        api_source = MultiEventTournamentAPI(
            api_token=token_to_use,
            tournament_slug=multi_event_tournament_slug,
        )
        event_to_use = None
        slug_to_use = None
        tournament_slug_to_use = multi_event_tournament_slug

    log(
        "🔍 Creating app with token: "
        f"{'***' if token_to_use else 'None'}, "
        f"event: {repr(event_to_use)}, slug: {repr(slug_to_use)}"
    )

    app_kwargs = {
        "api_token": token_to_use,
        "event_id": event_to_use,
        "event_slug": slug_to_use,
        "tournament_slug": tournament_slug_to_use,
        "view_mode": view_mode_to_use,
    }
    if args.jsonbin_id is not None:
        app_kwargs["jsonbin_id"] = args.jsonbin_id
    if args.jsonbin_key is not None:
        app_kwargs["jsonbin_key"] = args.jsonbin_key
    if api_source is not None:
        app_kwargs["api"] = api_source

    app = TournamentDisplay(**app_kwargs)

    try:
        log("🏁 Starting Textual app...")
        app.run()
        log("🏁 Textual app finished")
    except KeyboardInterrupt:
        log("\n👋 Tournament display stopped")
    except Exception as e:
        log(f"❌ App crashed: {type(e).__name__}: {e}")
    finally:
        # Always clean up terminal state regardless of how app exits
        cleanup_terminal()


if __name__ == "__main__":
    main()
