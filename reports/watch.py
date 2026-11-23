#!/usr/bin/env python3
"""Watch report sources and republish them to the web UI automatically.

The backend writes `recon-report.md` into each task directory when an agent
finishes a task. This watcher notices new or changed reports and runs
`reports/sync_web.py`, so the Reports page picks them up without manual steps.

Watched sources (same set as sync_web.py):
  reports/*.md
  dist/artex-windows-amd64/data/tasks/<id>/recon-report.md
  data/tasks/<id>/recon-report.md

Usage:
  python reports/watch.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from glob import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYNC = os.path.join(ROOT, "reports", "sync_web.py")

SOURCES = [
    os.path.join(ROOT, "reports", "*.md"),
    os.path.join(ROOT, "dist", "artex-windows-amd64", "data", "tasks", "*", "recon-report.md"),
    os.path.join(ROOT, "data", "tasks", "*", "recon-report.md"),
]

INTERVAL_SECONDS = 5
DEBOUNCE_SECONDS = 2


def snapshot() -> dict[str, tuple[int, int]]:
    """Return a path -> (mtime_ns, size) map of every report source."""
    snap: dict[str, tuple[int, int]] = {}
    for pattern in SOURCES:
        for path in glob(pattern):
            try:
                st = os.stat(path)
            except OSError:
                continue
            snap[path] = (st.st_mtime_ns, st.st_size)
    return snap


def sync() -> None:
    result = subprocess.run(
        [sys.executable, SYNC],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    lines = (result.stdout or "").strip().splitlines()
    head = lines[0] if lines else "(no output)"
    print(f"[{time.strftime('%H:%M:%S')}] {head}", flush=True)
    if result.returncode != 0:
        tail = (result.stderr or "").strip()[-600:]
        print(f"  sync failed (rc={result.returncode}): {tail}", flush=True)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    print(f"Watching reports every {INTERVAL_SECONDS}s. Press Ctrl+C to stop.", flush=True)
    sync()
    previous = snapshot()

    while True:
        time.sleep(INTERVAL_SECONDS)
        current = snapshot()
        if current == previous:
            continue
        # Let the agent finish writing before publishing a partial file.
        time.sleep(DEBOUNCE_SECONDS)
        current = snapshot()
        sync()
        previous = current


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("stopped", flush=True)
