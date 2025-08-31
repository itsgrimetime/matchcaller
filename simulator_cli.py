#!/usr/bin/env python3
"""
Tournament Simulator CLI
A tool for cloning tournaments and running bracket simulations
"""

import argparse
import asyncio
import sys
import time

from matchcaller.ui import TournamentDisplay
from matchcaller.utils.bracket_simulator import BracketSimulator, SimulatedTournamentAPI
from matchcaller.utils.logging import log
from matchcaller.utils.tournament_cloner import TournamentCloner


async def clone_tournament(args):
    """Clone a tournament from start.gg"""
    if not args.token:
        log("❌ API token required for cloning. Use --token YOUR_TOKEN")
        return 1

    cloner = TournamentCloner(args.token)

    log(f"🔄 Cloning tournament: {args.slug}")
    log("   This may take a while for large tournaments...")

    try:
        filepath = await cloner.clone_tournament(args.slug)
    except Exception as e:
        log(f"❌ Error during cloning: {e}")
        return 1

    if filepath:
        print("✅ Tournament cloned successfully!")
        print(f"📁 File: {filepath}")
        print(f"💡 Use: python simulator_cli.py simulate {filepath}")
        return 0
    else:
        print("❌ Failed to clone tournament")
        return 1


def list_tournaments(args):
    """List all cloned tournaments"""
    cloner = TournamentCloner("")  # No token needed for listing
    tournaments = cloner.list_cloned_tournaments()

    if not tournaments:
        print("📭 No cloned tournaments found")
        print(
            "💡 Clone a tournament first: python simulator_cli.py clone --token TOKEN --slug SLUG"
        )
        return 0

    print(f"📚 Found {len(tournaments)} cloned tournaments:")
    print("")

    for i, tournament in enumerate(tournaments, 1):
        metadata = tournament["metadata"]
        cloned_at = time.ctime(metadata.get("cloned_at", 0))

        print(f"{i}. {metadata['event_name']}")
        print(f"   Tournament: {metadata['tournament_name']}")
        print(f"   Slug: {metadata['event_slug']}")
        print(f"   Matches: {metadata['total_matches']}")
        print(f"   Duration: {tournament['duration_minutes']} minutes")
        print(f"   Cloned: {cloned_at}")
        print(f"   File: {tournament['filename']}")
        print("")

    return 0


def simulate_tournament(args):
    """Run a tournament simulation"""
    simulator = BracketSimulator(args.file, args.speed)

    if not simulator.load_tournament():
        return 1

    log(f"🎮 Simulation Controls:")
    log("   Ctrl+C: Stop simulation")
    log("   The TUI will show live data from the simulation")
    log("")

    if args.gui:
        # Run with TUI
        print("🖥️  Starting TUI with simulated data...")
        print("   The simulation will advance automatically as the TUI refreshes")
        print("   Press Ctrl+C to exit")

        # Create a simulated API
        sim_api = SimulatedTournamentAPI(simulator)

        # Create TUI that uses simulated data
        app = TournamentDisplay(api_token=None, event_id=None, event_slug=None)
        app.api = sim_api

        # Run the TUI
        try:
            app.run()
        except KeyboardInterrupt:
            print("\n👋 Simulation stopped")

    else:
        # Run simulation only (console output)
        print("📊 Console simulation mode")

        async def console_callback(state):
            """Print simulation state to console"""
            print(f"📊 {state['event_name']}: {len(state['sets'])} active matches")
            for match in state["sets"][:5]:  # Show first 5 matches
                status = {1: "Waiting", 2: "Ready", 6: "In Progress"}[match["state"]]
                print(
                    f"   {match['player1']['tag']} vs {match['player2']['tag']} - {status}"
                )
            if len(state["sets"]) > 5:
                print(f"   ... and {len(state['sets']) - 5} more matches")
            print("")

        # Run async simulation in sync function
        import asyncio

        asyncio.run(simulator.start_simulation(callback=console_callback))

    return 0


def analyze_tournament(args):
    """Analyze a cloned tournament file"""
    simulator = BracketSimulator(args.file)

    if not simulator.load_tournament():
        return 1

    data = simulator.tournament_data
    metadata = data["metadata"]

    print(f"📊 Tournament Analysis")
    print("=" * 50)
    print(f"Event: {metadata['event_name']}")
    print(f"Tournament: {metadata['tournament_name']}")
    print(f"Slug: {metadata['event_slug']}")
    print(f"Total Matches: {metadata['total_matches']}")
    print(
        f"Duration: {data['duration_minutes']} minutes ({data['duration_minutes']/60:.1f} hours)"
    )
    print("")

    # Analyze match states
    state_counts = {}
    phase_counts = {}

    for match in data["matches"]:
        state = match["state"]
        state_counts[state] = state_counts.get(state, 0) + 1

        phase = match["phase_name"]
        phase_counts[phase] = phase_counts.get(phase, 0) + 1

    print("Match States:")
    state_names = {
        1: "Created/Waiting",
        2: "Ready/In Progress",
        3: "Completed",
        6: "In Progress",
        7: "Invalid",
    }
    for state, count in sorted(state_counts.items()):
        name = state_names.get(state, f"Unknown ({state})")
        print(f"  {name}: {count}")

    print("")
    print("Phases/Brackets:")
    for phase, count in sorted(phase_counts.items()):
        print(f"  {phase}: {count}")

    print("")
    print("Timeline Events:")
    print(f"  Total Events: {len(simulator.timeline_events)}")
    if simulator.timeline_events:
        first_event = time.ctime(simulator.timeline_events[0]["timestamp"])
        last_event = time.ctime(simulator.timeline_events[-1]["timestamp"])
        print(f"  First Event: {first_event}")
        print(f"  Last Event: {last_event}")

    return 0


def main():

    parser = argparse.ArgumentParser(
        description="Tournament Simulator CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Clone a completed tournament
  python simulator_cli.py clone --token YOUR_TOKEN --slug "tournament/the-c-stick-55/event/melee-singles"

  # List cloned tournaments
  python simulator_cli.py list

  # Run simulation with TUI
  python simulator_cli.py simulate tournament_data.json --gui

  # Run console simulation at 120x speed
  python simulator_cli.py simulate tournament_data.json --speed 120

  # Analyze tournament data
  python simulator_cli.py analyze tournament_data.json
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Clone command
    clone_parser = subparsers.add_parser(
        "clone", help="Clone a tournament from start.gg"
    )
    clone_parser.add_argument("--token", required=True, help="start.gg API token")
    clone_parser.add_argument(
        "--slug", required=True, help="Event slug (e.g., tournament/name/event/singles)"
    )

    # List command
    list_parser = subparsers.add_parser("list", help="List cloned tournaments")

    # Simulate command
    simulate_parser = subparsers.add_parser(
        "simulate", help="Run tournament simulation"
    )
    simulate_parser.add_argument("file", help="Cloned tournament JSON file")
    simulate_parser.add_argument(
        "--speed",
        type=float,
        default=60.0,
        help="Simulation speed multiplier (default: 60x)",
    )
    simulate_parser.add_argument(
        "--gui", action="store_true", help="Run with TUI interface"
    )

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze tournament data")
    analyze_parser.add_argument("file", help="Cloned tournament JSON file")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    try:
        if args.command == "clone":
            return asyncio.run(clone_tournament(args))
        elif args.command == "list":
            return list_tournaments(args)
        elif args.command == "simulate":
            return simulate_tournament(args)
        elif args.command == "analyze":
            return analyze_tournament(args)
    except KeyboardInterrupt:
        log("\n👋 Interrupted by user")
        return 1
    except Exception as e:
        log(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
