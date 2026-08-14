#!/usr/bin/env python3
"""Run the Rivet web UI + API locally.

Usage: python scripts/run_dev_server.py [--port 5000]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Run from a source checkout without installing: the engine lives in
# packages/engine, the service in apps/api.
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root / "packages" / "engine"))
sys.path.insert(0, str(_root / "apps" / "api"))

from rivet.api.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    app = create_app()
    app.run(host=args.host, port=args.port, debug=True)


if __name__ == "__main__":
    main()
