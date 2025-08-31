#!/usr/bin/env python3
"""Standalone script to clean up terminal state after Textual apps."""

import sys


def cleanup_terminal():
    """Send escape sequences to disable mouse tracking and restore terminal state."""
    # Disable various mouse tracking modes
    escape_sequences = [
        "\033[?1000l",  # Disable X11 mouse reporting
        "\033[?1003l",  # Disable all mouse motion reporting
        "\033[?1015l",  # Disable urxvt mouse mode
        "\033[?1006l",  # Disable SGR mouse mode
        "\033[?25h",  # Show cursor
        "\033[?1004l",  # Disable focus reporting
    ]

    for seq in escape_sequences:
        sys.stdout.write(seq)

    sys.stdout.flush()
    print("Terminal state reset - mouse tracking disabled")


if __name__ == "__main__":
    cleanup_terminal()
