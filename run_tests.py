#!/usr/bin/env python3
"""
Test runner script for matchcaller TUI application

This script provides various testing options:
- Run all tests
- Run specific test categories (unit, integration, ui)
- Run with coverage reporting
- Update snapshots
- Run tests matching patterns

Usage:
    python run_tests.py              # Run all tests
    python run_tests.py --unit       # Run only unit tests
    python run_tests.py --ui         # Run only UI tests
    python run_tests.py --coverage   # Run with coverage report
    python run_tests.py --snapshots  # Update snapshot tests
    python run_tests.py --fast       # Skip slow tests
    python run_tests.py --pattern test_api  # Run tests matching pattern
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description=""):
    """Run a command and handle output"""
    print(f"\n{'='*60}")
    if description:
        print(f"🚀 {description}")
    print(f"📝 Running: {' '.join(cmd)}")
    print(f"{'='*60}")

    try:
        result = subprocess.run(cmd, check=False, capture_output=False)
        if result.returncode == 0:
            print(f"✅ {description or 'Command'} completed successfully")
        else:
            print(
                f"❌ {description or 'Command'} failed with exit code {result.returncode}"
            )
        return result.returncode
    except FileNotFoundError:
        print(f"❌ Command not found: {cmd[0]}")
        return 127
    except Exception as e:
        print(f"❌ Error running command: {e}")
        return 1


def install_dependencies():
    """Install test dependencies"""
    print("📦 Installing test dependencies...")
    return run_command(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
        "Installing dependencies",
    )


def run_tests(args):
    """Run tests based on provided arguments"""
    cmd = [sys.executable, "-m", "pytest"]

    # Add verbosity
    cmd.extend(["-v"])

    # Test selection
    if args.unit:
        cmd.extend(["-m", "unit"])
        description = "Unit tests"
    elif args.integration:
        cmd.extend(["-m", "integration"])
        description = "Integration tests"
    elif args.ui:
        cmd.extend(["-m", "ui"])
        description = "UI tests"
    else:
        description = "All tests"

    # Coverage reporting
    if args.coverage:
        cmd.extend(
            [
                "--cov=matchcaller",
                "--cov-report=html",
                "--cov-report=term",
                "--cov-report=xml",
            ]
        )
        description += " with coverage"

    # Snapshot updates
    if args.snapshots:
        cmd.extend(["--snapshot-update"])
        description += " (updating snapshots)"

    # Skip slow tests
    if args.fast:
        cmd.extend(["-m", "not slow"])
        description += " (fast only)"

    # Pattern matching
    if args.pattern:
        cmd.extend(["-k", args.pattern])
        description += f" (pattern: {args.pattern})"

    # Specific test file
    if args.file:
        cmd.append(f"tests/{args.file}")
        description += f" (file: {args.file})"

    # Add test directory if no specific file
    if not args.file:
        cmd.append("tests/")

    return run_command(cmd, description)


def check_environment():
    """Check if the environment is set up correctly"""
    print("🔍 Checking test environment...")

    # Check if we're in the right directory
    if not Path("matchcaller").exists():
        print("❌ Not in the correct directory. Please run from project root.")
        return False

    # Check if requirements.txt exists
    if not Path("requirements.txt").exists():
        print("❌ requirements.txt not found")
        return False

    # Check if tests directory exists
    if not Path("tests").exists():
        print("❌ tests directory not found")
        return False

    print("✅ Environment looks good")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Test runner for matchcaller TUI application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py                    # Run all tests
  python run_tests.py --unit            # Run unit tests only
  python run_tests.py --ui --coverage   # Run UI tests with coverage
  python run_tests.py --snapshots       # Update snapshot tests
  python run_tests.py --pattern api     # Run tests with 'api' in the name
  python run_tests.py --file test_api.py # Run specific test file
        """,
    )

    # Test type selection
    test_group = parser.add_mutually_exclusive_group()
    test_group.add_argument("--unit", action="store_true", help="Run unit tests only")
    test_group.add_argument(
        "--integration", action="store_true", help="Run integration tests only"
    )
    test_group.add_argument("--ui", action="store_true", help="Run UI tests only")

    # Test options
    parser.add_argument(
        "--coverage", action="store_true", help="Run tests with coverage reporting"
    )
    parser.add_argument(
        "--snapshots", action="store_true", help="Update snapshot tests"
    )
    parser.add_argument("--fast", action="store_true", help="Skip slow tests")
    parser.add_argument("--pattern", help="Run tests matching this pattern")
    parser.add_argument("--file", help="Run specific test file (e.g., test_api.py)")

    # Environment options
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Install dependencies before running tests",
    )
    parser.add_argument(
        "--no-env-check", action="store_true", help="Skip environment checks"
    )

    args = parser.parse_args()

    print("🧪 Matchcaller Test Runner")
    print("=" * 60)

    # Environment check
    if not args.no_env_check and not check_environment():
        return 1

    # Install dependencies if requested
    if args.install_deps:
        if install_dependencies() != 0:
            return 1

    # Run tests
    exit_code = run_tests(args)

    # Summary
    print(f"\n{'='*60}")
    if exit_code == 0:
        print("🎉 All tests passed!")
        if args.coverage:
            print("📊 Coverage report generated in htmlcov/")
    else:
        print("💥 Some tests failed")
        print("📋 Check the output above for details")
    print(f"{'='*60}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
