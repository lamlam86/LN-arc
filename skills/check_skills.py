#!/usr/bin/env python3
"""Validate shipped skills: frontmatter, name/dir match, deployment, visibility hints.

Usage:
  python skills/check_skills.py
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")
DEPLOYED = os.path.join(ROOT, "dist", "artex-windows-amd64", "skills")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    out: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    errors: list[str] = []
    warnings: list[str] = []
    rows = []
    for name in sorted(os.listdir(SKILLS)):
        d = os.path.join(SKILLS, name)
        path = os.path.join(d, "SKILL.md")
        if not os.path.isdir(d) or not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        fm = frontmatter(text)
        skill_name = fm.get("name", "")
        desc = fm.get("description", "")
        if not NAME_RE.match(name):
            errors.append(f"{name}: directory must be lowercase letters/digits/hyphens")
        # The loader matches visibility by DIRECTORY name, so a display-name
        # mismatch is allowed (warn only).
        if skill_name != name:
            warnings.append(f"{name}: frontmatter display name is {skill_name!r}")
        if len(desc) < 20:
            errors.append(f"{name}: description is missing or too short")
        deployed = os.path.isfile(os.path.join(DEPLOYED, name, "SKILL.md"))
        if not deployed:
            errors.append(f"{name}: not deployed to {DEPLOYED}")
        rows.append((name, len(text), "yes" if deployed else "no", desc[:70]))

    print(f"{len(rows)} skill(s)")
    for name, size, deployed, desc in rows:
        print(f"  {name:<22} {size:>6}B deployed={deployed:<3} {desc}")
    if warnings:
        print("\nWARNINGS:")
        for w in warnings:
            print(f"  - {w}")
    if errors:
        print("\nERRORS:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("\nOK: all skills have valid names, descriptions and deployment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
