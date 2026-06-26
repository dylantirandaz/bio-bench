#!/usr/bin/env python3
"""Command-line entry point for BioFigure task validation."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from biofigure.validate import main


if __name__ == "__main__":
    raise SystemExit(main())
