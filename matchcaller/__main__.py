"""Main entry point for the tournament display application."""

import argparse
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


def _is_abbey_short_url(short_url: str) -> bool:
    """Return whether a short URL is the Abbey weekly shortcut."""
    return _normalize_short_url(short_url) == "abbey"


def _choose_event(
    events: list[dict[str, str]],
    event_filter: str | None,
) -> dict[str, str]:
    """Pick the event matching the user's filter, avoiding waitlists when possible."""
    chosen = None
    if event_filter:
        keyword = event_filter.lower()
        matches = [
            ev for ev in events
            if keyword in ev["name"].lower() or keyword in ev["slug"].lower()
        ]
        non_waitlist = [
            ev for ev in matches
            if "waitlist" not in ev["name"].lower()
        ]
        if non_waitlist:
            chosen = non_waitlist[0]
        elif matches:
            chosen = matches[0]
    return chosen or events[0]


class MatchCallerArgs(argparse.Namespace):
    token: str | None = None
    event: str | None = None
    slug: str | None = None
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
        help="start.gg event slug (e.g., tournament/the-c-stick-55/event/melee-singles)",
    )
    parser.add_argument(
        "--short-url",
        help="start.gg short URL (e.g., 'abbey') - resolves to tournament slug automatically",
    )
    parser.add_argument(
        "--event-filter",
        help="Keyword to match the right event when using --short-url (e.g., 'melee', 'singles')",
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
    resolved_tournament_slug = None

    log("🔍 Command line args:")
    log(f"   Token: {'***' if args.token else 'None'}")
    log(f"   Event: {args.event}")
    log(f"   Slug: {args.slug}")
    log(f"   Short URL: {args.short_url}")
    log(f"   Event Filter: {args.event_filter}")
    log(f"   Demo: {args.demo}")
    log(f"   Simulate: {args.simulate}")
    log(f"   JsonBin ID: {args.jsonbin_id or 'None'}")
    log(f"   JsonBin Key: {'***' if args.jsonbin_key else 'None'}")
    log(f"   View: {args.view}")

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
    elif not args.token or (not args.event and not args.slug):
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
