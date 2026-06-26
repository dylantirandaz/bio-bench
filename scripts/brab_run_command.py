#!/usr/bin/env python3
"""Command-line entry point for running BRAB prompts through an external adapter."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brab.run_command import main


if __name__ == "__main__":
    raise SystemExit(main())
