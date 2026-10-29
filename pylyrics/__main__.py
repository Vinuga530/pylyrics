"""Module entry point for running `python -m pylyrics`."""

from __future__ import annotations

import sys

from pylyrics.cli import main

if __name__ == "__main__":
    sys.exit(main())
