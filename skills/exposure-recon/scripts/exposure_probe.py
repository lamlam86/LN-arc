#!/usr/bin/env python3
"""Read-only probe for publicly exposed files on an AUTHORIZED target.

Checks a small curated list of high-signal paths (VCS metadata, env/config,
backups, debug endpoints, API docs, storage) with anonymous GET requests.
It never authenticates, never sends discovered secrets, and reads at most a few
KB per path. Findings are fingerprinted only; bodies are not saved.

Usage:
    python exposure_probe.py https://example.com
    python exposure_probe.py https://example.com --delay 0.5 --timeout 8
    python exposure_probe.py https://example.com --json findings.json
    python exposure_probe.py https://example.com --only vcs,config

Only use this against assets you are authorized to test.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "exposure-recon/1.0 (authorized read-only)"


def looks_html(b: bytes) -> bool:
    head = b[:512].lower()
    return b"<!doctype html" in head or b"<html" in head or b"<head" in head


def sig_env(b: bytes, _ct: str) -> bool:
    if looks_html(b):
        return False
    lines = [l.strip() for l in b.splitlines() if l.strip() and not l.strip().startswith(b"#")]
    kv = [l for l in lines[:6] if re.match(rb"^[A-Za-z_][A-Za-z0-9_]*=", l)]
    return len(kv) >= 2


def sig_yamlish(b: bytes, _ct: str) -> bool:
    if looks_html(b):
        return False
    return re.search(rb"(?m)^[A-Za-z_][\w.-]*\s*:", b[:2048]) is not None


def sig_json_keys(*keys: bytes):
    def check(b: bytes, ct: str) -> bool:
        if "json" not in ct and not b.strip().startswith(b"{"):
            return False
        return any(k in b[:4096] for k in keys)
    return check


def sig_magic(*magics: bytes):
    def check(b: bytes, _ct: str) -> bool:
        return any(b.startswith(m) for m in magics)
    return check


def sig_sql(b: bytes, _ct: str) -> bool:
    low = b[:2048].lower()
    return any(k in low for k in (b"insert into", b"create table", b"-- mysql", b"pg_dump"))


def sig_plain(b: bytes, _ct: str) -> bool:
    return bool(b.strip()) and not looks_html(b)


CHECKS: list[tuple[str, str, object]] = [
    ("vcs", "/.git/HEAD", lambda b, _c: b.startswith(b"ref: refs/")),
    ("vcs", "/.git/config", lambda b, _c: b"[core]" in b[:2048]),
    ("vcs", "/.git/index", sig_magic(b"DIRC")),
    ("vcs", "/.svn/entries", sig_plain),
    ("vcs", "/.hg/requires", sig_plain),
    ("config", "/.env", sig_env),
    ("config", "/.env.local", sig_env),
    ("config", "/.env.production", sig_env),
    ("config", "/config.json", sig_json_keys(b"{", b'"')),
    ("config", "/config.yml", sig_yamlish),
    ("config", "/docker-compose.yml", sig_yamlish),
    ("config", "/.npmrc", sig_env),
    ("config", "/.aws/credentials", lambda b, _c: b"[default]" in b[:1024]),
    ("config", "/wp-config.php", lambda b, _c: b"DB_PASSWORD" in b[:4096]),
    ("config", "/web.config", lambda b, _c: b"<configuration" in b[:1024]),
    ("config", "/id_rsa", lambda b, _c: b"PRIVATE KEY" in b[:256]),
    ("backup", "/backup.zip", sig_magic(b"PK\x03\x04")),
    ("backup", "/backup.tar.gz", sig_magic(b"\x1f\x8b")),
    ("backup", "/db.sql", sig_sql),
    ("backup", "/dump.sql", sig_sql),
    ("backup", "/.DS_Store", sig_magic(b"\x00\x00\x00\x01Bud1")),
    ("backup", "/debug.log", sig_plain),
    ("debug", "/actuator", sig_json_keys(b"_links", b"health")),
    ("debug", "/actuator/env", sig_json_keys(b"propertySources", b"activeProfiles")),
    ("debug", "/actuator/heapdump", sig_magic(b"JAVA PROFILE", b"\x1f\x8b")),
    ("debug", "/debug/pprof/", lambda b, _c: b"profiles" in b[:2048] or b"goroutine" in b[:2048]),
    ("debug", "/phpinfo.php", lambda b, _c: b"PHP Version" in b[:4096]),
    ("debug", "/server-status", lambda b, _c: b"Apache Server Status" in b[:2048]),
    ("debug", "/metrics", lambda b, _c: b"# HELP" in b[:2048] or b"# TYPE" in b[:2048]),
    ("api", "/swagger-ui.html", lambda b, _c: b"swagger" in b[:4096].lower()),
    ("api", "/swagger-ui/", lambda b, _c: b"swagger" in b[:4096].lower()),
    ("api", "/v3/api-docs", sig_json_keys(b"openapi", b"swagger", b"paths")),
    ("api", "/openapi.json", sig_json_keys(b"openapi", b"swagger", b"paths")),
    ("api", "/api-docs", sig_json_keys(b"openapi", b"swagger", b"paths")),
    ("api", "/graphql", lambda b, _c: b"__schema" in b[:4096]),
    ("meta", "/robots.txt", lambda b, _c: b"user-agent" in b[:1024].lower() or b"disallow" in b[:2048].lower()),
    ("meta", "/sitemap.xml", lambda b, _c: b"<urlset" in b[:1024] or b"<sitemapindex" in b[:1024]),
    ("meta", "/.well-known/security.txt", lambda b, _c: b"contact:" in b[:2048].lower()),
    ("meta", "/crossdomain.xml", lambda b, _c: b"cross-domain-policy" in b[:1024]),
]


def fetch(url: str, timeout: float, max_bytes: int):
    req = urllib.request.Request(url, method="GET", headers={
        "User-Agent": UA,
        "Accept": "*/*",
        "Range": f"bytes=0-{max_bytes}",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read(max_bytes + 1)
        status = resp.status
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "gzip" in (resp.headers.get("Content-Encoding") or "") and body[:2] == b"\x1f\x8b":
            try:
                body = gzip.decompress(body)[:max_bytes]
            except OSError:
                pass
        return status, ctype, body


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only exposure probe (authorized targets only).")
    ap.add_argument("base_url", help="e.g. https://example.com")
    ap.add_argument("--delay", type=float, default=0.6, help="seconds between requests (default 0.6)")
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--max-bytes", type=int, default=8192)
    ap.add_argument("--json", metavar="FILE", help="write findings as JSON")
    ap.add_argument("--only", help="comma-separated categories: vcs,config,backup,debug,api,meta")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    cats = {c.strip() for c in args.only.split(",")} if args.only else None

    # Baseline: an unlikely path tells us the SPA/404 fallback body.
    marker = f"__exposure_probe_{random.randrange(10**9)}__"
    try:
        _, _, base_body = fetch(f"{base}/{marker}", args.timeout, args.max_bytes)
        base_hash = hashlib.sha256(base_body).hexdigest()
    except urllib.error.HTTPError as e:
        base_hash = hashlib.sha256(e.read(args.max_bytes) or b"").hexdigest()
        base_body = b""
    except Exception as e:  # noqa: BLE001
        print(f"[!] baseline request failed: {e}", file=sys.stderr)
        return 2

    findings = []
    for cat, path, check in CHECKS:
        if cats and cat not in cats:
            continue
        url = base + path
        try:
            status, ctype, body = fetch(url, args.timeout, args.max_bytes)
        except urllib.error.HTTPError as e:
            verdict = "PROTECTED" if e.code in (401, 403) else None
            if verdict:
                print(f"  {verdict:<9} {e.code}  {path}")
            time.sleep(args.delay)
            continue
        except Exception as e:  # noqa: BLE001
            print(f"  {'ERR':<9} ---   {path}  ({e})", file=sys.stderr)
            time.sleep(args.delay)
            continue

        h = hashlib.sha256(body).hexdigest()
        if status == 200 and body and h == base_hash:
            verdict = "FALLBACK"
        elif status == 200 and check(body, ctype):
            verdict = "HIT"
        else:
            verdict = "."

        if verdict != ".":
            note = f"{ctype or 'unknown'}, {len(body)}B"
            print(f"  {verdict:<9} {status}  {path}  ({note})")
        if verdict == "HIT":
            findings.append({"category": cat, "url": url, "status": status,
                             "content_type": ctype, "bytes": len(body),
                             "sha256": h})
        time.sleep(args.delay)

    print(f"\n{len(findings)} potential exposure(s). Bodies are not saved.")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(findings, f, indent=2)
        print(f"Wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
