#!/usr/bin/env python3
"""Metadata-only audit of YOUR OWN web property for publicly reachable documents.

What it does:
  - fetches robots.txt, sitemap.xml, and same-origin HTML pages (small budget)
  - collects links to document extensions
  - sends HEAD to each document URL (falls back to a 1-byte range GET if HEAD is rejected)
  - classifies by filename/path only and prints a removal-oriented summary

What it never does:
  - download, open, OCR, or preview a document
  - extract names, phone numbers, ID numbers, or any personal data
  - crawl or dork third-party domains

Usage:
  python doc_exposure_scan.py https://your-domain.example \
      --authorization "PO-2026-014" --max-pages 150 --max-depth 2 --delay 0.5 \
      --json doc-findings.json --md doc-findings.md --dorks
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "self-exposure-audit/1.0 (authorized owner audit, metadata only)"
DOC_EXTS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".txt",
    ".rtf", ".odt", ".ods", ".zip", ".rar", ".7z", ".tar", ".gz",
}
# Ordered by sensitivity: the first matching group wins when a path matches several.
KEYWORDS = [
    ("identity", ["cccd", "cmnd", "passport", "ho-chieu", "hộ chiếu", "can-cuoc", "căn cước"]),
    ("payroll", ["payroll", "luong", "lương", "salary", "bang-luong", "bảng lương"]),
    ("hr", ["hr", "nhan-su", "nhân sự", "tuyen-dung", "tuyển dụng", "resume", "cv"]),
    ("contract", ["contract", "hop-dong", "hợp đồng", "agreement"]),
    ("customer", ["customer", "khach-hang", "khách hàng", "crm", "export"]),
    ("finance", ["invoice", "hoa-don", "hoá đơn", "hóa đơn", "budget", "quyet-toan"]),
    ("contact", ["phone", "sdt", "sđt", "danh-ba", "danh bạ", "contact-list"]),
    ("backup", ["backup", "dump", "archive", "sao-luu"]),
]
HREF_RE = re.compile(r"""href\s*=\s*["']([^"'#]+)["']""", re.I)
INDEX_OF_RE = re.compile(r"index\s+of\s+/", re.I)


def same_origin(url: str, base: str) -> bool:
    a, b = urllib.parse.urlsplit(url), urllib.parse.urlsplit(base)
    return (a.scheme, a.netloc.lower()) == (b.scheme, b.netloc.lower())


def clean(url: str, base: str) -> str | None:
    try:
        full = urllib.parse.urljoin(base, url)
    except ValueError:
        return None
    p = urllib.parse.urlsplit(full)
    if p.scheme not in ("http", "https") or not p.netloc:
        return None
    if not same_origin(full, base):
        return None
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, p.query, ""))


def is_doc(url: str) -> bool:
    return urllib.parse.urlsplit(url).path.lower().endswith(tuple(DOC_EXTS))


def classify(url: str) -> str:
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path).lower()
    for label, words in KEYWORDS:
        if any(w in path for w in words):
            return label
    return "unclassified"


def request(url: str, method: str, timeout: float, max_bytes: int = 0):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": "*/*"})
    if max_bytes:
        req.add_header("Range", f"bytes=0-{max_bytes - 1}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read(max_bytes) if max_bytes else b""
        return resp.status, (resp.headers.get("Content-Type") or "").lower(), resp.headers.get("Content-Length"), body


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Metadata-only self-exposure audit (owned domains only).")
    ap.add_argument("base_url")
    ap.add_argument("--authorization", default="", help="written authorization / ticket reference")
    ap.add_argument("--max-pages", type=int, default=150)
    ap.add_argument("--max-depth", type=int, default=2)
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--timeout", type=float, default=10)
    ap.add_argument("--json", metavar="FILE")
    ap.add_argument("--md", metavar="FILE")
    ap.add_argument("--dorks", action="store_true", help="print site:-scoped queries for manual review")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    host = urllib.parse.urlsplit(base).netloc
    docs: set[str] = set()
    listings: list[str] = []
    seeds: list[str] = []
    notes: list[str] = []

    # robots.txt + sitemap seeds
    for path in ("/robots.txt", "/sitemap.xml"):
        try:
            _, ctype, _, body = request(base + path, "GET", args.timeout, max_bytes=256 * 1024)
        except Exception:
            continue
        text = body.decode("utf-8", "replace")
        if path.endswith("robots.txt"):
            for line in text.splitlines():
                m = re.match(r"(?i)\s*sitemap\s*:\s*(\S+)", line)
                if m:
                    seeds.append(m.group(1))
        else:
            for m in re.finditer(r"<loc>\s*([^<\s]+)\s*</loc>", text, re.I):
                u = clean(m.group(1), base)
                if not u:
                    continue
                if is_doc(u):
                    docs.add(u)
                else:
                    seeds.append(u)

    # BFS over same-origin HTML pages
    queue: list[tuple[str, int]] = [(base + "/", 0)] + [(u, 0) for u in seeds[:50]]
    seen: set[str] = set()
    pages = 0
    while queue and pages < args.max_pages:
        url, depth = queue.pop(0)
        if url in seen or depth > args.max_depth:
            continue
        seen.add(url)
        if is_doc(url):
            docs.add(url)
            continue
        try:
            _, ctype, _, body = request(url, "GET", args.timeout, max_bytes=512 * 1024)
        except Exception as e:  # noqa: BLE001
            notes.append(f"skip {url}: {e}")
            continue
        if "html" not in ctype:
            continue
        pages += 1
        text = body.decode("utf-8", "replace")
        if INDEX_OF_RE.search(text) and re.search(r"<title>[^<]*index\s+of", text, re.I):
            listings.append(url)
        for m in HREF_RE.finditer(text):
            u = clean(m.group(1), base)
            if not u:
                continue
            if is_doc(u):
                docs.add(u)
            elif depth < args.max_depth and u not in seen:
                queue.append((u, depth + 1))
        time.sleep(args.delay)

    # HEAD each document (metadata only)
    results = []
    for u in sorted(docs):
        status, ctype, length, _ = None, "", None, None
        try:
            status, ctype, length, _ = request(u, "HEAD", args.timeout)
        except urllib.error.HTTPError as e:
            status = e.code
        except Exception:
            try:  # HEAD may be blocked; read one byte only
                status, ctype, length, _ = request(u, "GET", args.timeout, max_bytes=1)
            except urllib.error.HTTPError as e:
                status = e.code
            except Exception as e:  # noqa: BLE001
                notes.append(f"error {u}: {e}")
        results.append({
            "url": u,
            "status": status,
            "content_type": ctype,
            "bytes": int(length) if length and length.isdigit() else None,
            "likely_category": classify(u),
            "public": status == 200,
        })
        time.sleep(args.delay)

    public = [r for r in results if r["public"]]
    doc = {
        "base": base,
        "host": host,
        "authorization": args.authorization,
        "generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "pages_crawled": pages,
        "documents_found": len(results),
        "public_documents": len(public),
        "directory_listings": listings,
        "documents": results,
        "notes": notes,
    }

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)
        print(f"Wrote {args.json}")

    if args.md:
        lines = [f"# Self-exposure audit — {host}\n",
                 f"Generated: {doc['generated']}",
                 f"Authorization: {args.authorization or '_not provided_'}\n",
                 f"Pages crawled: {pages} · documents found: {len(results)} · public: {len(public)}\n",
                 "| Status | Likely category | URL | Type | Bytes |", "|---|---|---|---|---|"]
        for r in sorted(results, key=lambda x: (not x["public"], x["likely_category"])):
            lines.append(f"| {r['status']} | {r['likely_category']} | {r['url']} | {r['content_type']} | {r['bytes'] or ''} |")
        if listings:
            lines.append("\n## Directory listings\n")
            lines.extend(f"- {u}" for u in listings)
        if notes:
            lines.append("\n## Notes\n")
            lines.extend(f"- {n}" for n in notes[:30])
        lines.append("\n> Metadata only. Documents were not downloaded or opened. "
                     "Remove/block public documents and de-index them; see the skill playbook.\n")
        with open(args.md, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"Wrote {args.md}")

    print(f"crawled={pages} docs={len(results)} public={len(public)} listings={len(listings)}")
    if args.dorks:
        print("\nManual search queries (owned host only):")
        for q in [
            f"site:{host} filetype:pdf",
            f"site:{host} filetype:docx OR filetype:xlsx",
            f"site:{host} (hợp đồng OR contract)",
            f"site:{host} (nhân sự OR \"hồ sơ\" OR HR OR tuyển dụng)",
            f"site:{host} (CCCD OR CMND OR passport)",
            f"site:{host} (bảng lương OR salary OR payroll)",
            f"site:{host} (khách hàng OR customer OR export)",
            f"site:{host} (backup OR dump OR sao lưu)",
        ]:
            print(f"  {q}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
