"""
Tournament Display TUI - A terminal-based tournament viewer
Designed for Raspberry Pi Zero 2W - no X11/browser required!

This is the refactored version with modular architecture.
"""

import os
import sys

# Add the parent directory to the path so we can import the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matchcaller.__main__ import main

if __name__ == "__main__":
    main()
