"""Main entry point for the tournament display application."""

import argparse
import sys
import time

from .ui import TournamentDisplay
from .utils.logging import log


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

    args: MatchCallerArgs = parser.parse_args(namespace=MatchCallerArgs())

    log("🔍 Command line args:")
    log(f"   Token: {'***' + args.token[-4:] if args.token else 'None'}")
    log(f"   Event: {args.event}")
    log(f"   Slug: {args.slug}")
    log(f"   Short URL: {args.short_url}")
    log(f"   Event Filter: {args.event_filter}")
    log(f"   Demo: {args.demo}")
    log(f"   Simulate: {args.simulate}")
    log(f"   JsonBin ID: {args.jsonbin_id or 'None'}")
    log(f"   JsonBin Key: {'***' if args.jsonbin_key else 'None'}")

    # Resolve --short-url to a full event slug
    if args.short_url and args.token and not args.slug:
        log(f"🔍 Resolving short URL: {args.short_url}")
        try:
            from .utils.resolve import resolve_tournament_slug_from_unique_string

            tournament_slug = resolve_tournament_slug_from_unique_string(args.short_url)
            log(f"✅ Resolved tournament slug: {tournament_slug}")

            # Query API for events under this tournament
            import asyncio

            from .api import TournamentAPI

            tmp_api = TournamentAPI(api_token=args.token)
            events = asyncio.run(tmp_api.get_events_for_tournament(tournament_slug))

            if not events:
                log(f"❌ No events found for tournament: {tournament_slug}")
                sys.exit(1)

            # Pick the matching event, deprioritizing waitlist/staging events
            chosen = None
            if args.event_filter:
                keyword = args.event_filter.lower()
                matches = [
                    ev for ev in events
                    if keyword in ev["name"].lower() or keyword in ev["slug"].lower()
                ]
                # Prefer non-waitlist events
                non_waitlist = [
                    ev for ev in matches
                    if "waitlist" not in ev["name"].lower()
                ]
                if non_waitlist:
                    chosen = non_waitlist[0]
                elif matches:
                    chosen = matches[0]
            if not chosen:
                chosen = events[0]

            args.slug = chosen["slug"]
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
        app = TournamentDisplay(
            api_token=None, event_id=None, event_slug=None,
            jsonbin_id=args.jsonbin_id, jsonbin_key=args.jsonbin_key,
        )
        app.api = SimulatedTournamentAPI(simulator)

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
    elif not args.token or (not args.event and not args.slug):
        log("🏆 Running in DEMO mode with mock data")
        log("   Use --token and (--event or --slug) for real data")
        log("   Press Ctrl+C to exit\n")
        time.sleep(2)
        # Force None values in demo mode
        token_to_use = None
        event_to_use = None
        slug_to_use = None
    else:
        log("🌐 Running with REAL start.gg data")
        log("   Press Ctrl+C to exit\n")
        time.sleep(1)
        token_to_use = args.token
        event_to_use = args.event
        slug_to_use = args.slug

    log(
        f"🔍 Creating app with token: {repr(token_to_use)}, event: {repr(event_to_use)}, slug: {repr(slug_to_use)}"
    )

    app = TournamentDisplay(
        api_token=token_to_use, event_id=event_to_use, event_slug=slug_to_use,
        jsonbin_id=args.jsonbin_id, jsonbin_key=args.jsonbin_key,
    )

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
