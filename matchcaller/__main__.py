"""Main entry point for the tournament display application."""

import argparse
import sys
import time

from .ui import TournamentDisplay
from .utils.logging import log


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Tournament Display TUI")
    parser.add_argument("--token", help="start.gg API token")
    parser.add_argument("--event", help="start.gg event ID")
    parser.add_argument(
        "--slug",
        help="start.gg event slug (e.g., tournament/the-c-stick-55/event/melee-singles)",
    )
    parser.add_argument("--demo", action="store_true", help="Run with demo data")

    args = parser.parse_args()

    log(f"🔍 Command line args:")
    log(f"   Token: {'***' + args.token[-4:] if args.token else 'None'}")
    log(f"   Event: {args.event}")
    log(f"   Slug: {args.slug}")
    log(f"   Demo: {args.demo}")

    # Debug the actual values being passed
    log(f"🔍 Raw args.token: {repr(args.token)}")
    log(f"🔍 Raw args.event: {repr(args.event)}")
    log(f"🔍 Raw args.slug: {repr(args.slug)}")

    if args.demo or (not args.token or (not args.event and not args.slug)):
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
        api_token=token_to_use, event_id=event_to_use, event_slug=slug_to_use
    )

    try:
        log("🏁 Starting Textual app...")
        app.run()
        log("🏁 Textual app finished")
    except KeyboardInterrupt:
        log("\n👋 Tournament display stopped")
    except Exception as e:
        log(f"❌ App crashed: {type(e).__name__}: {e}")
        import traceback

        log(f"❌ Full traceback: {traceback.format_exc()}")


if __name__ == "__main__":
    main()