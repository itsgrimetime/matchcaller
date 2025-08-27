"""Main entry point for the tournament display application."""

import argparse
import asyncio
import random
import sys
import time

import aiohttp

from .ui import TournamentDisplay
from .utils.logging import log


async def find_active_tournament(api_token: str):
    """Find a random active tournament with multiple pools using your manual search approach"""
    log("🔍 Searching for recent tournaments with active brackets...")

    # Calculate timestamps for recent tournaments (tournaments are typically 1-6 hours long)
    import time as time_module

    now = int(time_module.time())
    start_of_search = now - (12 * 3600)  # 12 hours ago (to catch ongoing tournaments)
    end_of_search = now + (6 * 3600)  # 6 hours from now

    # GraphQL query to find recent tournaments
    query = """
    query TournamentsToday($perPage: Int!, $afterDate: Timestamp!, $beforeDate: Timestamp!) {
        tournaments(query: {
            perPage: $perPage
            page: 1
            filter: {
                afterDate: $afterDate
                beforeDate: $beforeDate
                published: true
            }
        }) {
            nodes {
                id
                name
                slug
                startAt
                endAt
                state
                events {
                    id
                    name
                    slug
                    state
                    sets(page: 1, perPage: 5, filters: {state: [1, 2, 6]}) {
                        nodes {
                            id
                            state
                            phaseGroup {
                                displayIdentifier
                            }
                        }
                    }
                }
            }
        }
    }
    """

    variables = {
        "perPage": 75,  # Reasonable number for 18-hour window
        "afterDate": start_of_search,
        "beforeDate": end_of_search,
    }
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.start.gg/gql/alpha",
                json={"query": query, "variables": variables},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    log(f"❌ Error fetching tournaments: HTTP {response.status}")
                    return None

                data = await response.json()

                if "errors" in data:
                    log(f"❌ GraphQL errors: {data['errors']}")
                    return None

                tournaments = (
                    data.get("data", {}).get("tournaments", {}).get("nodes", [])
                )
                log(
                    f"🔍 Found {len(tournaments)} tournaments in 18-hour window (12h ago to 6h from now)"
                )

                # Filter for tournaments with active brackets
                suitable_tournaments = []
                # Accept tournaments that started up to 8 hours ago or start up to 4 hours from now
                past_cutoff = now - (8 * 3600)  # Started within last 8 hours
                future_cutoff = now + (4 * 3600)  # Or starting within next 4 hours

                log(f"🔍 Debug: Current time: {now}")
                log(
                    f"🔍 Debug: Filtering for tournaments between {past_cutoff} and {future_cutoff}"
                )
                log(
                    "🔍 Debug: This covers tournaments from 8 hours ago to 4 hours from now"
                )

                for i, tournament in enumerate(tournaments):
                    if i < 5:  # Debug first 5 tournaments
                        log(
                            f"🔍 Debug Tournament {i+1}: {tournament.get('name', 'Unknown')}"
                        )
                        log(f"   Slug: {tournament.get('slug')}")
                        log(
                            f"   URL: https://www.start.gg/{tournament.get('slug', '')}"
                        )
                        log(
                            f"   Start time: {tournament.get('startAt')} (vs cutoff: {past_cutoff})"
                        )
                        log(f"   State: {tournament.get('state')}")
                        log(f"   Events: {len(tournament.get('events', []))}")

                    start_time = tournament.get("startAt")
                    if not start_time:
                        if i < 5:
                            log("   ❌ Skipped: No start time")
                        continue
                    if start_time < past_cutoff or start_time > future_cutoff:
                        if i < 5:
                            if start_time < now:
                                hours_ago = (now - start_time) / 3600
                                log(
                                    f"   ❌ Skipped: Started {hours_ago:.1f} hours ago (too long)"
                                )
                            else:
                                hours_future = (start_time - now) / 3600
                                log(
                                    f"   ❌ Skipped: Starts {hours_future:.1f} hours from now (too far)"
                                )
                        continue

                    events = tournament.get("events", [])
                    if i < 5:
                        log(f"   ✅ Recent enough, checking {len(events)} events")

                    for j, event in enumerate(events):
                        sets = event.get("sets", {}).get("nodes", [])
                        if i < 5:
                            log(
                                f"     Event {j+1} '{event.get('name', 'Unknown')}': {len(sets)} sets, state: {event.get('state')}"
                            )
                            log(f"       Event slug: {event.get('slug')}")
                            log(
                                f"       Event URL: https://www.start.gg/{event.get('slug', '')}"
                            )

                        if not sets:
                            if i < 5:
                                log("       ❌ No active matches")
                            continue

                        # Check for multiple pools by counting unique pool identifiers
                        pools = set()
                        active_matches = 0
                        for match_set in sets:
                            if match_set.get("state") in [
                                1,
                                2,
                                6,
                            ]:  # Active match states
                                active_matches += 1
                                phase_group = match_set.get("phaseGroup", {})
                                if phase_group and phase_group.get("displayIdentifier"):
                                    pools.add(phase_group["displayIdentifier"])

                        if i < 5:
                            log(
                                f"       Active matches: {active_matches}, Pools: {list(pools)}"
                            )

                        # Check if the event/bracket has actually started
                        event_state = event.get("state")
                        if i < 5:
                            log(
                                f"       Event state: {event_state} (1=Created, 2=Active, 3=Completed)"
                            )

                        # Prioritize events that are ACTIVE (state 2) with active matches
                        # State 1 = Created (not started), State 2 = Active (started), State 3 = Completed
                        # Also accept events with many active matches even if not in "ACTIVE" state (some TOs don't update state)
                        is_suitable = (
                            (
                                event_state == 2 and active_matches > 0
                            )  # Properly started events
                            or (
                                active_matches >= 5
                            )  # Or events with many active matches regardless of state
                        ) and (len(pools) > 1 or active_matches >= 3)

                        if is_suitable:
                            hours_since = (now - start_time) / 3600
                            suitable_tournaments.append(
                                {
                                    "tournament": tournament,
                                    "event": event,
                                    "pool_count": len(pools),
                                    "active_matches": active_matches,
                                    "hours_since_start": hours_since,
                                    "event_state": event_state,
                                }
                            )
                            if i < 5:
                                if event_state == 2:
                                    log(
                                        f"       ✅ SUITABLE! Event ACTIVE (state {event_state}), {len(pools)} pools, {active_matches} matches"
                                    )
                                else:
                                    log(
                                        f"       ✅ SUITABLE! Many active matches ({active_matches}), {len(pools)} pools, state {event_state}"
                                    )
                        elif i < 5:
                            if active_matches == 0:
                                log("       ❌ No active matches found")
                            elif event_state != 2 and active_matches < 5:
                                log(
                                    f"       ❌ Event not active: state {event_state}, only {active_matches} matches (need 5+ or state 2)"
                                )
                            else:
                                log(
                                    f"       ❌ Not enough pools: {len(pools)} pools (need multiple pools or 3+ matches)"
                                )

                log(f"🎯 Found {len(suitable_tournaments)} suitable tournaments")

                if not suitable_tournaments:
                    log("❌ No suitable tournaments found")
                    log(
                        "💡 Looking for: tournaments with ACTIVE brackets (state 2) that have multiple pools and ongoing matches"
                    )
                    log(
                        "💡 Note: We skip tournaments with 'Created' brackets (state 1) that haven't started yet"
                    )
                    return None

                # Pick a random tournament, prefer ones with more pools/matches
                selected = random.choice(suitable_tournaments)
                tournament = selected["tournament"]
                event = selected["event"]

                log(f"✅ Selected: {tournament['name']} - {event['name']}")
                log(
                    f"📊 {selected['pool_count']} pools, {selected['active_matches']} active matches"
                )
                log(f"⏱️  Started {selected['hours_since_start']:.1f} hours ago")
                log(
                    f"🎯 Event state: {selected['event_state']} (Active bracket with ongoing matches)"
                )

                # Create the event slug (just use the event slug directly)
                event_slug = event["slug"]
                log(f"🔍 Debug: Tournament slug: {tournament['slug']}")
                log(f"🔍 Debug: Event slug: {event['slug']}")
                log(f"🔍 Debug: Final event slug: {event_slug}")
                return event_slug

    except Exception as e:
        log(f"❌ Error finding active tournaments: {e}")
        return None


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
    parser.add_argument(
        "--find-active",
        action="store_true",
        help="Automatically find a random active tournament with multiple pools",
    )

    args = parser.parse_args()

    log("🔍 Command line args:")
    log(f"   Token: {'***' + args.token[-4:] if args.token else 'None'}")
    log(f"   Event: {args.event}")
    log(f"   Slug: {args.slug}")
    log(f"   Demo: {args.demo}")
    log(f"   Find Active: {args.find_active}")

    # Debug the actual values being passed
    log(f"🔍 Raw args.token: {repr(args.token)}")
    log(f"🔍 Raw args.event: {repr(args.event)}")
    log(f"🔍 Raw args.slug: {repr(args.slug)}")

    if args.demo:
        log("🏆 Running in DEMO mode with mock data")
        log("   Use --token and (--event or --slug) for real data")
        log("   Press Ctrl+C to exit\n")
        time.sleep(2)
        # Force None values in demo mode
        token_to_use = None
        event_to_use = None
        slug_to_use = None
    elif args.find_active:
        if not args.token:
            log("❌ --find-active requires --token to search for tournaments")
            sys.exit(1)
        log("🎯 Finding active tournament with multiple pools...")
        log("   This may take a few seconds...")
        time.sleep(1)

        # Run the async function to find active tournament
        try:
            found_slug = asyncio.run(find_active_tournament(args.token))
            if not found_slug:
                log("❌ No suitable active tournaments found")
                log("   Try running with --demo or specify a tournament manually")
                sys.exit(1)

            log(f"🌐 Using auto-found tournament: {found_slug}")
            log("   Press Ctrl+C to exit\n")
            token_to_use = args.token
            event_to_use = None
            slug_to_use = found_slug
        except Exception as e:
            log(f"❌ Error finding tournament: {e}")
            sys.exit(1)
    elif not args.token or (not args.event and not args.slug):
        log("🏆 Running in DEMO mode with mock data")
        log("   Use --token and (--event or --slug) for real data")
        log("   Or use --token --find-active to auto-find tournaments")
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
