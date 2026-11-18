#!/usr/bin/env python3
"""Local, redacted PII *detection* for files you are authorized to review.

This is a DLP triage helper, not an extractor:
  - reads local files only (never URLs)
  - reports COUNTS by type and a coarse risk level
  - never prints, stores, or exports the detected values
  - never copies or modifies the source files

Supported: .txt .csv .tsv .json .md .log .html .htm .xml .yaml .yml .ini .conf
Optional (if the library is installed): .pdf (pdfminer.six), .docx (python-docx),
.xlsx (openpyxl). Otherwise those files are reported as unsupported.

Usage:
  python pii_detect.py --authorization "PO-2026-014" --path ./hr-files \
      --json pii-summary.json --md pii-summary.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys

TEXT_EXTS = {".txt", ".csv", ".tsv", ".json", ".md", ".log", ".html", ".htm", ".xml", ".yaml", ".yml", ".ini", ".conf"}
OPTIONAL_EXTS = {".pdf", ".docx", ".xlsx"}

PATTERNS = {
    "vn_phone": re.compile(r"(?<!\d)(?:\+84|0)(?:2\d{9}|[35789]\d{8})(?!\d)"),
    "cccd_12_digit": re.compile(r"(?<!\d)\d{12}(?!\d)"),
    "cmnd_9_digit": re.compile(r"(?<!\d)\d{9}(?!\d)"),
    "passport": re.compile(r"(?<![A-Z0-9])[A-Z]\d{7,8}(?![A-Z0-9])"),
    "email": re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    "date_of_birth": re.compile(r"(?<!\d)(?:0?[1-9]|[12]\d|3[01])[/.\-](?:0?[1-9]|1[0-2])[/.\-](?:19|20)\d{2}(?!\d)"),
}
NAME_LABEL = re.compile(r"(?i)(họ\s*(và\s*)?tên|ho\s*ten|full\s*name|ngày\s*sinh|date\s*of\s*birth|số\s*cccd|so\s*cccd)")


def read_text(path: str) -> tuple[str, str]:
    """Return (text, note). Raises on unreadable input."""
    ext = os.path.splitext(path)[1].lower()
    if ext in TEXT_EXTS:
        with open(path, "rb") as f:
            raw = f.read()
        return raw.decode("utf-8", "replace"), ""
    if ext == ".pdf":
        try:
            from pdfminer.high_level import extract_text  # type: ignore
        except ImportError:
            return "", "unsupported: install pdfminer.six for PDF text"
        return extract_text(path) or "", ""
    if ext == ".docx":
        try:
            import docx  # type: ignore
        except ImportError:
            return "", "unsupported: install python-docx for DOCX text"
        d = docx.Document(path)
        parts = [p.text for p in d.paragraphs]
        for t in d.tables:
            for row in t.rows:
                parts.extend(c.text for c in row.cells)
        return "\n".join(parts), ""
    if ext == ".xlsx":
        try:
            import openpyxl  # type: ignore
        except ImportError:
            return "", "unsupported: install openpyxl for XLSX text"
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        parts = []
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                parts.extend(str(v) for v in row if v is not None)
        return "\n".join(parts), ""
    return "", "unsupported extension"


def risk_level(counts: dict[str, int]) -> str:
    if counts.get("cccd_12_digit") or counts.get("cmnd_9_digit") or counts.get("passport"):
        return "high"
    if counts.get("vn_phone") or counts.get("email", 0) >= 3:
        return "medium"
    if any(counts.values()):
        return "low"
    return "none"


def scan_file(path: str) -> dict:
    text, note = read_text(path)
    counts = {k: len(p.findall(text)) for k, p in PATTERNS.items()} if text else {}
    labels = len(NAME_LABEL.findall(text)) if text else 0
    counts = {k: v for k, v in counts.items() if v}
    if labels:
        counts["name_or_dob_label"] = labels
    return {"path": os.path.abspath(path), "bytes": os.path.getsize(path), "types": counts,
            "risk": risk_level(counts), "note": note}


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Redacted PII detection for authorized local files.")
    ap.add_argument("--authorization", required=True, help="written authorization / ticket reference")
    ap.add_argument("--path", required=True, help="local file or directory (URLs are rejected)")
    ap.add_argument("--json", metavar="FILE")
    ap.add_argument("--md", metavar="FILE")
    args = ap.parse_args()

    if "://" in args.path:
        print("[!] URLs are rejected. This helper only reads local files.", file=sys.stderr)
        return 2
    if not os.path.exists(args.path):
        print(f"[!] path not found: {args.path}", file=sys.stderr)
        return 2

    files: list[str] = []
    if os.path.isfile(args.path):
        files = [args.path]
    else:
        for root, _dirs, names in os.walk(args.path):
            for n in names:
                ext = os.path.splitext(n)[1].lower()
                if ext in TEXT_EXTS or ext in OPTIONAL_EXTS:
                    files.append(os.path.join(root, n))

    rows = []
    for p in sorted(files):
        try:
            rows.append(scan_file(p))
        except Exception as e:  # noqa: BLE001
            rows.append({"path": os.path.abspath(p), "bytes": 0, "types": {}, "risk": "none",
                         "note": f"error: {e}"})

    totals: dict[str, int] = {}
    for r in rows:
        for k, v in r["types"].items():
            totals[k] = totals.get(k, 0) + v
    order = {"high": 0, "medium": 1, "low": 2, "none": 3}
    rows.sort(key=lambda r: (order.get(r["risk"], 9), -sum(r["types"].values())))

    doc = {
        "generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "authorization": args.authorization,
        "root": os.path.abspath(args.path),
        "files_scanned": len(rows),
        "totals_by_type": totals,
        "files": rows,
        "note": "Counts only. Detected values are never printed, stored, or exported.",
    }

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)
        print(f"Wrote {args.json}")
    if args.md:
        lines = [f"# PII detection summary\n",
                 f"Generated: {doc['generated']}",
                 f"Authorization: {args.authorization}",
                 f"Files scanned: {len(rows)}\n",
                 "## Totals by type\n",
                 "| Type | Count |", "|---|---|"]
        for k, v in sorted(totals.items()):
            lines.append(f"| {k} | {v} |")
        lines += ["\n## Files\n", "| Risk | File | Types (counts only) |", "|---|---|---|"]
        for r in rows:
            types = ", ".join(f"{k}={v}" for k, v in sorted(r["types"].items())) or "-"
            lines.append(f"| {r['risk']} | {r['path']} | {types} |")
        lines.append("\n> Counts only. No personal data value is included in this report.")
        with open(args.md, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"Wrote {args.md}")

    print(f"files={len(rows)} types={totals}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
