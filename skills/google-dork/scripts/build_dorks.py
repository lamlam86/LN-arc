#!/usr/bin/env python3
"""Build site-scoped Google dork queries for an authorized domain.

This script only prints queries/URLs; it never sends requests to Google or the
target. Review the results manually in a browser, then verify exposure with
read-only HEAD/GET requests.

Usage:
  python build_dorks.py example.com
  python build_dorks.py example.com --category docs,config
  python build_dorks.py example.com --format urls
"""

from __future__ import annotations

import argparse
import csv
import sys
import urllib.parse

QUERIES: dict[str, list[str]] = {
    "docs": [
        'site:{d} filetype:pdf',
        'site:{d} (filetype:docx OR filetype:xlsx OR filetype:pptx)',
        'site:{d} (filetype:csv OR filetype:txt OR filetype:json)',
        'site:{d} (filetype:zip OR filetype:rar OR filetype:7z)',
    ],
    "config": [
        'site:{d} (inurl:.env OR inurl:config OR inurl:settings)',
        'site:{d} (ext:bak OR ext:old OR ext:orig OR ext:log)',
        'site:{d} (ext:sql OR ext:dump OR ext:tar OR ext:gz)',
        'site:{d} intext:"password" filetype:txt',
    ],
    "vcs": [
        'site:{d} (inurl:.git OR inurl:.svn OR inurl:.hg)',
        'site:{d} intitle:"index of"',
    ],
    "admin": [
        'site:{d} (inurl:admin OR inurl:login OR inurl:dashboard)',
        'site:{d} (inurl:upload OR inurl:backup OR inurl:manage)',
        'site:{d} (intitle:"admin" OR intitle:"login")',
    ],
    "api": [
        'site:{d} (inurl:swagger OR inurl:api-docs OR inurl:openapi)',
        'site:{d} inurl:graphql',
    ],
    "debug": [
        'site:{d} (inurl:debug OR inurl:phpinfo OR inurl:server-status)',
        'site:{d} intext:"stack trace"',
        'site:{d} (inurl:actuator OR inurl:metrics)',
    ],
    "subdomains": [
        'site:*.{d} -www',
        'site:*.{d} (inurl:admin OR inurl:dev OR inurl:staging)',
    ],
}

CATEGORIES = list(QUERIES)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description="Build scoped Google dorks (no network).")
    ap.add_argument("domain", help="authorized root domain, e.g. example.com")
    ap.add_argument("--category", default="all", help="comma-separated: " + ", ".join(CATEGORIES))
    ap.add_argument("--format", choices=("text", "urls", "csv"), default="text")
    args = ap.parse_args()

    domain = args.domain.strip().lower().lstrip(".")
    if not domain or "/" in domain or " " in domain:
        print("[!] pass a bare root domain, not a URL", file=sys.stderr)
        return 2

    cats = CATEGORIES if args.category == "all" else [c.strip() for c in args.category.split(",")]
    bad = [c for c in cats if c not in QUERIES]
    if bad:
        print(f"[!] unknown category: {', '.join(bad)}", file=sys.stderr)
        return 2

    rows = []
    for cat in cats:
        for tmpl in QUERIES[cat]:
            q = tmpl.format(d=domain)
            rows.append({"category": cat, "query": q,
                         "url": "https://www.google.com/search?q=" + urllib.parse.quote_plus(q)})

    if args.format == "csv":
        w = csv.DictWriter(sys.stdout, fieldnames=["category", "query", "url"])
        w.writeheader()
        w.writerows(rows)
    elif args.format == "urls":
        for r in rows:
            print(r["url"])
    else:
        for r in rows:
            print(f"[{r['category']:<10}] {r['query']}")
    print(f"\n{len(rows)} queries for {domain}. Review manually; verify with HEAD/GET.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
