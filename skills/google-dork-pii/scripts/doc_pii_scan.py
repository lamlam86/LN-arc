#!/usr/bin/env python3
"""Redacted PII triage for publicly reachable documents (authorized targets only).

Consumes the CSV/JSON output of google_dork.py (or explicit URLs), downloads each
document with a bounded, read-only GET, extracts text **in memory**, and reports
only aggregate evidence:

  - counts and distinct counts of Vietnamese phone numbers, 12-digit CCCD and
    9-digit CMND-shaped numbers
  - label hits (Số điện thoại / CCCD / Họ và tên / ...)
  - list structure (lines carrying several PII values, label+value lines)
  - a coarse verdict hint: likely_list / possible_list / incidental_contact /
    mentions_only / no_pii / no_text / blocked

It never writes a document body to disk, never prints or stores a full PII value,
and masks the few number samples it does emit. Treat the output as evidence for a
human/LLM judgment, not as a data extract.

Usage:
  python3 doc_pii_scan.py --authorization "PO-2026-014" \
      --input recon/dork.csv --site camau.baohiemxahoi.gov.vn \
      --out-dir recon/gdork-pii

  python3 doc_pii_scan.py --authorization "PO-2026-014" \
      --url https://target.example/doc.pdf --url https://target.example/list.xlsx

Only use this against assets you are authorized to assess.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import html as htmlmod
import io
import ipaddress
import json
import os
import re
import ssl
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile

UA = "Mozilla/5.0 (compatible; LN-ARC-pii-scan/1.0; authorized read-only recon)"
# Candidate patterns are deliberately broad; validation below removes noise.
PHONE_CAND = re.compile(r"(?<![\d])(?:\+?84|0)(?:[ \t.\-\u00a0\u2013\u2014]?\d){9,10}(?![\d])")
CCCD_CAND = re.compile(r"(?<![\d])\d{12}(?![\d])")
CCCD_GROUPED = re.compile(r"(?<![\d])\d{3}[ .\-]\d{3}[ .\-]\d{3}[ .\-]\d{3}(?![\d])")
CMND_CAND = re.compile(r"(?<![\d])\d{9}(?![\d])")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

# Vietnamese province/city codes used as the first three CCCD digits (001-096).
PROVINCE_CODES = set(range(1, 97))
CURRENT_YY = dt.date.today().year % 100

LABEL_PATTERNS = {
    "phone": re.compile(r"\b(?:so\s*dien\s*thoai|sdt|dien\s*thoai|phone|di\s*dong|lien\s*he)\b"),
    "cccd": re.compile(r"\b(?:cccd|so\s*cccd|can\s*cuoc(?:\s*cong\s*dan)?|cmnd|chung\s*minh\s*nhan\s*dan)\b"),
    "name": re.compile(r"\b(?:ho\s*va\s*ten|ho\s*ten|full\s*name|ngay\s*sinh|date\s*of\s*birth)\b"),
    "address": re.compile(r"\b(?:dia\s*chi|noi\s*o|noi\s*thuong\s*tru|address)\b"),
    "table": re.compile(r"\b(?:stt|tt|so\s*thu\s*tu|danh\s*sach|list)\b"),
}


# --------------------------------------------------------------------------- #
# Fetch (read-only, bounded, same-site redirects)
# --------------------------------------------------------------------------- #
class _SameSiteRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts: set[str]):
        super().__init__()
        self.allowed = allowed_hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        host = (urllib.parse.urlparse(newurl).hostname or "").lower().rstrip(".")
        if self.allowed and not _host_allowed(host, self.allowed):
            raise urllib.error.HTTPError(
                newurl, code, f"cross-host redirect blocked ({host})", headers, fp
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _host_allowed(host: str, allowed: set[str]) -> bool:
    host = (host or "").lower().rstrip(".")
    return any(host == a or host.endswith("." + a) for a in allowed)


def is_private_host(host: str) -> bool:
    """True for loopback/private/link-local/reserved literal hosts."""
    h = (host or "").strip("[]").lower().rstrip(".")
    if h == "localhost" or h.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_reserved


def fetch(url: str, *, timeout: float, max_bytes: int, proxy: str | None,
          insecure: bool, allowed_hosts: set[str], allow_private: bool = False) -> dict:
    """Return {data, status, content_type, final_url, bytes, truncated, error}."""
    out = {"data": b"", "status": None, "content_type": "", "final_url": url,
           "bytes": 0, "truncated": False, "error": ""}
    if not re.match(r"^https?://", url, re.I):
        out["error"] = "unsupported scheme (http/https only)"
        return out
    host = (urllib.parse.urlparse(url).hostname or "")
    if not allow_private and is_private_host(host):
        out["error"] = "private/loopback host blocked (use --allow-private for an authorized internal target)"
        return out

    handlers: list[urllib.request.BaseHandler] = [_SameSiteRedirect(allowed_hosts)]
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    handlers.append(urllib.request.HTTPSHandler(context=ctx))
    opener = urllib.request.build_opener(*handlers)

    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/pdf,application/octet-stream,text/html,*/*;q=0.8",
        "Accept-Encoding": "identity",
    })
    try:
        with opener.open(req, timeout=timeout) as r:
            out["status"] = getattr(r, "status", None)
            out["content_type"] = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            out["final_url"] = r.geturl()
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    keep = max_bytes - (total - len(chunk))
                    if keep > 0:
                        chunks.append(chunk[:keep])
                    out["truncated"] = True
                    break
                chunks.append(chunk)
            data = b"".join(chunks)
            out["bytes"] = len(data)
            if (r.headers.get("Content-Encoding") or "").lower() == "gzip":
                try:
                    with gzip.GzipFile(fileobj=io.BytesIO(data)) as gz:
                        data = gz.read(max_bytes)
                    out["bytes"] = len(data)
                except OSError:
                    pass
            out["data"] = data
    except urllib.error.HTTPError as exc:
        out["status"] = exc.code
        out["error"] = f"HTTP {exc.code}"
        try:
            out["data"] = exc.read(min(max_bytes, 65536))
        except Exception:  # noqa: BLE001 - diagnostics only
            pass
    except Exception as exc:  # noqa: BLE001 - network/SSL/timeout
        out["error"] = f"{type(exc).__name__}: {exc}"[:300]
    return out


# --------------------------------------------------------------------------- #
# Extract text (no body is ever written to disk)
# --------------------------------------------------------------------------- #
def _decode_text(b: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1258", "cp1252", "latin-1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", "replace")


def _strip_markup(s: str) -> str:
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", s)
    s = re.sub(r"(?i)</t[dh]>", "\t", s)
    s = re.sub(r"<[^>]+>", "", s)
    return htmlmod.unescape(s)


def extract_docx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if "word/document.xml" not in z.namelist():
            return ""
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab[^>]*/>", "\t", xml)
    xml = re.sub(r"<w:br[^>]*/>", "\n", xml)
    return htmlmod.unescape(re.sub(r"<[^>]+>", "", xml))


def extract_xlsx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = set(z.namelist())

        def texts(xml: str) -> list[str]:
            out: list[str] = []
            for block in re.findall(r"(?is)<si\b.*?</si>", xml):
                out.append(htmlmod.unescape(re.sub(r"<[^>]+>", "", block)))
            return out

        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            shared = texts(z.read("xl/sharedStrings.xml").decode("utf-8", "replace"))
        rows_out: list[str] = []
        for name in sorted(n for n in names if re.match(r"xl/worksheets/sheet\d+\.xml$", n)):
            xml = z.read(name).decode("utf-8", "replace")
            for row in re.findall(r"(?is)<row\b.*?</row>", xml):
                cells: list[str] = []
                for cell in re.findall(r"(?is)<c\b[^>]*>.*?</c>", row):
                    t = re.search(r'\bt="([^"]+)"', cell)
                    typ = t.group(1) if t else ""
                    if typ == "s":
                        m = re.search(r"(?is)<v>(\d+)</v>", cell)
                        if m:
                            idx = int(m.group(1))
                            cells.append(shared[idx] if 0 <= idx < len(shared) else "")
                        else:
                            cells.append("")
                    elif typ == "inlineStr":
                        m = re.search(r"(?is)<t\b[^>]*>(.*?)</t>", cell)
                        cells.append(htmlmod.unescape(m.group(1)) if m else "")
                    else:
                        m = re.search(r"(?is)<v>(.*?)</v>", cell)
                        cells.append(htmlmod.unescape(m.group(1)) if m else "")
                rows_out.append("\t".join(cells))
        return "\n".join(rows_out)


def extract_pdf(data: bytes) -> tuple[str, int, int, str]:
    """Return (text, pages, pages_with_text, note)."""
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        return "", 0, 0, "unsupported: pypdf not installed"
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
    except Exception as exc:  # noqa: BLE001 - malformed/encrypted
        return "", 0, 0, f"pdf parse failed: {type(exc).__name__}"
    parts: list[str] = []
    text_pages = 0
    for page in reader.pages:
        try:
            t = page.extract_text() or ""
        except Exception:  # noqa: BLE001 - per-page decode issues
            t = ""
        if t.strip():
            text_pages += 1
        parts.append(t)
    text = "\n".join(parts)
    note = ""
    if not text.strip() and reader.pages:
        note = "scanned_or_image_pdf: no text layer; needs manual/authorized OCR review"
    return text, len(reader.pages), text_pages, note


def extract_text(data: bytes, content_type: str, url: str) -> tuple[str, str, dict]:
    """Return (text, kind, meta)."""
    meta: dict = {}
    path = urllib.parse.urlparse(url).path.lower()
    ext = os.path.splitext(path)[1]
    head = data[:1024]

    if head.startswith(b"%PDF") or ext == ".pdf" or content_type == "application/pdf":
        text, pages, text_pages, note = extract_pdf(data)
        meta.update(pages=pages, text_pages=text_pages, note=note)
        return text, "pdf", meta

    if head.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = z.namelist()
            if any(n.startswith("word/") for n in names):
                return extract_docx(data), "docx", meta
            if any(n.startswith("xl/") for n in names):
                return extract_xlsx(data), "xlsx", meta
        except zipfile.BadZipFile:
            pass

    ctype = content_type or ""
    if "html" in ctype or ext in {".html", ".htm"} or head.lstrip()[:1] == b"<":
        return _strip_markup(_decode_text(data)), "html", meta
    if ext in {".csv", ".tsv"} or "csv" in ctype:
        return _decode_text(data), "csv", meta
    if ext in {".doc", ".xls", ".ppt", ".rtf"}:
        meta["note"] = f"legacy binary {ext}: text extraction unsupported; needs manual review"
        return "", ext.lstrip("."), meta

    text = _decode_text(data)
    printable = sum(1 for ch in text[:4000] if ch.isprintable() or ch in "\n\r\t")
    if text and printable / max(len(text[:4000]), 1) > 0.85:
        return text, "text", meta
    meta["note"] = "unknown binary content: text extraction unsupported"
    return "", "binary", meta


# --------------------------------------------------------------------------- #
# Detect (counts only; values never leave this module)
# --------------------------------------------------------------------------- #
def strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("đ", "d").replace("Đ", "D")
    return s.lower()


def normalize_phone(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("84") and len(digits) in (11, 12):
        digits = "0" + digits[2:].lstrip("0") if digits[2:3] == "0" else "0" + digits[2:]
    if not digits.startswith("0"):
        digits = "0" + digits
    if re.fullmatch(r"0[35789]\d{8}", digits):      # mobile, 10 digits
        return digits
    if re.fullmatch(r"02\d{9}", digits):            # landline, 11 digits
        return digits
    return None


def valid_cccd(s: str) -> bool:
    if len(s) != 12 or len(set(s)) == 1:
        return False
    if int(s[:3]) not in PROVINCE_CODES:
        return False
    c = int(s[3])
    yy = int(s[4:6])
    if c in (0, 1):          # born 1900-1999
        return True
    if c in (2, 3):          # born 2000-2099
        return yy <= CURRENT_YY
    return False             # 2100+ is not a plausible living person's CCCD


def mask_phone(v: str) -> str:
    return v[:2] + "x" * max(0, len(v) - 4) + v[-2:]


def mask_cccd(v: str) -> str:
    return v[:3] + "x" * 6 + v[-3:]


def mask_cmnd(v: str) -> str:
    return v[:1] + "x" * (len(v) - 3) + v[-2:]


def detect(text: str, *, samples: bool) -> dict:
    norm = strip_accents(text)
    phones: list[str] = []
    cccds: list[str] = []
    cmnds: list[str] = []
    for m in PHONE_CAND.finditer(text):
        v = normalize_phone(m.group(0))
        if v:
            phones.append(v)
    for m in CCCD_CAND.finditer(text):
        if valid_cccd(m.group(0)):
            cccds.append(m.group(0))
    for m in CCCD_GROUPED.finditer(text):
        v = re.sub(r"\D", "", m.group(0))
        if valid_cccd(v):
            cccds.append(v)
    for m in CMND_CAND.finditer(text):
        cmnds.append(m.group(0))

    labels = {k: len(p.findall(norm)) for k, p in LABEL_PATTERNS.items()}

    phone_set, cccd_set, cmnd_set = set(phones), set(cccds), set(cmnds)
    lines_multi = 0
    lines_label_value = 0
    for line in text.splitlines():
        lnorm = strip_accents(line)
        p = sum(1 for m in PHONE_CAND.finditer(line) if normalize_phone(m.group(0)))
        c = sum(1 for m in CCCD_CAND.finditer(line) if valid_cccd(m.group(0)))
        c += sum(1 for m in CCCD_GROUPED.finditer(line) if valid_cccd(re.sub(r"\D", "", m.group(0))))
        k = sum(1 for m in CMND_CAND.finditer(line))
        hits = p + c + k
        if hits >= 2:
            lines_multi += 1
        if hits >= 1 and any(pat.search(lnorm) for pat in LABEL_PATTERNS.values()):
            lines_label_value += 1

    text_chars = len(text)
    total_distinct = len(phone_set) + len(cccd_set)
    density = total_distinct * 1000.0 / max(text_chars, 1)

    score = 0
    if len(cccd_set) >= 1:
        score += 2
    if len(cccd_set) >= 3:
        score += 2
    if len(cccd_set) >= 10:
        score += 2
    if len(phone_set) >= 1:
        score += 1
    if len(phone_set) >= 5:
        score += 2
    if len(phone_set) >= 15:
        score += 2
    if labels["cccd"] and labels["phone"]:
        score += 2
    elif labels["cccd"] or labels["phone"]:
        score += 1
    if lines_multi >= 2:
        score += 2
    if lines_multi >= 5:
        score += 1
    if lines_label_value >= 2:
        score += 2
    if lines_label_value >= 5:
        score += 1
    if density >= 2:
        score += 1

    if not text.strip():
        verdict = "no_text"
    elif total_distinct == 0:
        verdict = "no_pii"
    elif score >= 8 and (len(cccd_set) >= 2 or len(phone_set) >= 5):
        verdict = "likely_list"
    elif len(cccd_set) == 0 and len(phone_set) <= 2 and lines_multi == 0:
        verdict = "incidental_contact"
    elif len(cccd_set) <= 1 and len(phone_set) <= 2 and lines_multi == 0:
        verdict = "single_record"
    elif score >= 4 and total_distinct >= 2:
        verdict = "possible_list"
    else:
        verdict = "mentions_only"

    if score >= 10 and lines_label_value >= 2 and labels["cccd"]:
        confidence = "high"
    elif score >= 6:
        confidence = "medium"
    else:
        confidence = "low"

    out = {
        "text_chars": text_chars,
        "counts": {
            "vn_phone": len(phones),
            "cccd_12_valid": len(cccds),
            "cmnd_9_digit": len(cmnds),
            "email": len(EMAIL_RE.findall(text)),
        },
        "distinct": {
            "vn_phone": len(phone_set),
            "cccd_12_valid": len(cccd_set),
            "cmnd_9_digit": len(cmnd_set),
        },
        "labels": labels,
        "structure": {
            "lines_with_multiple_pii": lines_multi,
            "lines_with_label_and_pii": lines_label_value,
            "distinct_pii_per_1k_chars": round(density, 2),
        },
        "score": score,
        "verdict_hint": verdict,
        "confidence_hint": confidence,
    }
    if samples:
        out["masked_samples"] = {
            "vn_phone": sorted({mask_phone(v) for v in phones})[:3],
            "cccd_12_valid": sorted({mask_cccd(v) for v in cccds})[:3],
            "cmnd_9_digit": sorted({mask_cmnd(v) for v in cmnds})[:3],
        }
    return out


# --------------------------------------------------------------------------- #
# Input / output
# --------------------------------------------------------------------------- #
def load_urls(args) -> list[str]:
    urls: list[str] = list(args.url or [])
    if args.input:
        path = args.input
        try:
            if path.lower().endswith(".json"):
                raw = json.loads(open(path, encoding="utf-8-sig").read())
                rows = raw.get("results", []) if isinstance(raw, dict) else raw
                for r in rows:
                    if isinstance(r, dict) and r.get("url"):
                        urls.append(str(r["url"]))
                    elif isinstance(r, str):
                        urls.append(r)
            elif path.lower().endswith(".csv"):
                with open(path, newline="", encoding="utf-8-sig") as fh:
                    for row in csv.DictReader(fh):
                        if row.get("url"):
                            urls.append(row["url"].strip())
            else:
                for line in open(path, encoding="utf-8-sig"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        urls.append(line)
        except (OSError, json.JSONDecodeError, csv.Error) as exc:
            sys.exit(f"[!] cannot read --input {path}: {exc}")
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        u = u.strip()
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    if args.limit and args.limit > 0:
        out = out[: args.limit]
    return out


def write_markdown(path: str, report: dict) -> None:
    rows = sorted(report["docs"], key=lambda d: (-d.get("score", 0), d["url"]))
    lines = [
        "# Dork PII exposure triage",
        "",
        f"- Authorization: `{report['authorization']}`",
        f"- Target site: `{report.get('site') or '(derived from URLs)'}`",
        f"- Generated: {report['generated_at']}",
        f"- Documents checked: {len(rows)}",
        "- Values are never stored; samples are masked. Verify manually before any notification.",
        "",
        "| # | Verdict | Score | Conf | URL | Status | Type | Pages | Phones (distinct) | CCCD (valid distinct) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, d in enumerate(rows, 1):
        dis = d.get("distinct", {})
        lines.append(
            f"| {i} | {d.get('verdict_hint')} | {d.get('score')} | {d.get('confidence_hint')} | "
            f"{d['url'].replace('|', '%7C')} | {d.get('status') or '-'} | {d.get('kind') or '-'} | "
            f"{d.get('pages') or '-'} | {dis.get('vn_phone', 0)} | {dis.get('cccd_12_valid', 0)} |"
        )
    lines += ["", "## Notes", ""]
    for d in rows:
        note = d.get("note") or ""
        if note:
            lines.append(f"- `{d['url']}` — {note}")
    lines += [
        "",
        "## How to read the hints",
        "",
        "- `likely_list` / `possible_list`: aggregate evidence of a list of people; confirm manually.",
        "- `single_record`: one person's ID/contact detail, not a list.",
        "- `incidental_contact`: one or two contact numbers, not a person list.",
        "- `no_text`: scanned/image PDF or unsupported format; needs authorized manual review.",
        "- `blocked` / HTTP 401/403: not publicly readable; do not attempt bypass.",
        "",
        "No full phone number, CCCD/CMND, name, or address is included in this file.",
        "",
    ]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description="Redacted PII triage for authorized public documents.")
    ap.add_argument("--authorization", required=True, help="written authorization / ticket reference")
    ap.add_argument("--input", help="google_dork.py output (.csv/.json) or a URL list")
    ap.add_argument("--url", action="append", help="explicit document URL (repeatable)")
    ap.add_argument("--site", help="authorized root domain; redirects outside it are blocked")
    ap.add_argument("--out-dir", default=".", help="directory for pii-scan.json / pii-scan.md")
    ap.add_argument("--json", help="override JSON output path")
    ap.add_argument("--md", help="override Markdown output path")
    ap.add_argument("--max-bytes", type=int, default=20 * 1024 * 1024, help="per-document download cap (default 20 MiB)")
    ap.add_argument("--timeout", type=float, default=20.0, help="per-request timeout seconds")
    ap.add_argument("--delay", type=float, default=1.0, help="delay between requests seconds")
    ap.add_argument("--limit", type=int, default=0, help="maximum documents to check (0 = all)")
    ap.add_argument("--proxy", help="optional http(s) proxy, e.g. http://127.0.0.1:8788")
    ap.add_argument("--insecure", action="store_true", help="disable TLS verification (avoid unless required)")
    ap.add_argument("--allow-private", action="store_true", help="allow literal private/loopback hosts (authorized internal targets only)")
    ap.add_argument("--no-samples", action="store_true", help="omit even masked number samples")
    args = ap.parse_args()

    urls = load_urls(args)
    if not urls:
        sys.exit("[!] no URLs: pass --input or --url")

    allowed: set[str] = set()
    site = (args.site or "").strip()
    if "://" in site:
        site = urllib.parse.urlparse(site).hostname or ""
    site = site.lower().rstrip(".")
    if site:
        allowed.add(site)
    else:
        for u in urls:
            h = (urllib.parse.urlparse(u).hostname or "").lower().rstrip(".")
            if h:
                allowed.add(h)
    # If --site is given, keep only in-scope URLs.
    if site:
        urls = [u for u in urls if _host_allowed(
            (urllib.parse.urlparse(u).hostname or "").lower().rstrip("."), allowed)]
        if not urls:
            sys.exit(f"[!] no in-scope URLs for site {site}")

    os.makedirs(args.out_dir, exist_ok=True)
    json_path = args.json or os.path.join(args.out_dir, "pii-scan.json")
    md_path = args.md or os.path.join(args.out_dir, "pii-scan.md")

    docs: list[dict] = []
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url}", flush=True)
        meta = {"url": url, "status": None, "kind": None, "pages": None,
                "bytes": 0, "truncated": False, "note": "", "text_chars": 0}
        got = fetch(url, timeout=args.timeout, max_bytes=args.max_bytes,
                    proxy=args.proxy, insecure=args.insecure, allowed_hosts=allowed,
                    allow_private=args.allow_private)
        meta["status"] = got["status"]
        meta["bytes"] = got["bytes"]
        meta["truncated"] = got["truncated"]
        if got["error"]:
            meta["note"] = got["error"]
        if got["data"] and (got["status"] or 0) < 400:
            text, kind, extra = extract_text(got["data"], got["content_type"], got["final_url"])
            meta["kind"] = kind
            meta.update({k: v for k, v in extra.items() if v not in (None, "")})
            if not text and not meta["note"]:
                meta["note"] = "no text extracted"
            det = detect(text, samples=not args.no_samples) if text else detect("", samples=False)
            meta.update(det)
            if meta.get("verdict_hint") == "no_text" and not meta["note"]:
                meta["note"] = "no text extracted"
        else:
            meta["counts"] = {"vn_phone": 0, "cccd_12_valid": 0, "cmnd_9_digit": 0, "email": 0}
            meta["distinct"] = {"vn_phone": 0, "cccd_12_valid": 0, "cmnd_9_digit": 0}
            meta["labels"] = {k: 0 for k in LABEL_PATTERNS}
            meta["structure"] = {"lines_with_multiple_pii": 0, "lines_with_label_and_pii": 0,
                                 "distinct_pii_per_1k_chars": 0}
            meta["score"] = 0
            meta["verdict_hint"] = "blocked" if (got["status"] or 0) >= 400 else "fetch_failed"
            meta["confidence_hint"] = "low"
        dis = meta.get("distinct", {})
        print(f"    -> {meta.get('verdict_hint')} score={meta.get('score')} "
              f"phone={dis.get('vn_phone', 0)} cccd={dis.get('cccd_12_valid', 0)} "
              f"{('- ' + meta['note']) if meta.get('note') else ''}", flush=True)
        docs.append(meta)
        if args.delay > 0 and i < len(urls):
            time.sleep(args.delay)

    report = {
        "authorization": args.authorization,
        "site": site,
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "tool": "doc_pii_scan.py",
        "policy": "counts and masked samples only; no document body or full PII value is stored",
        "documents": len(docs),
        "summary": {
            "likely_list": sum(d.get("verdict_hint") == "likely_list" for d in docs),
            "possible_list": sum(d.get("verdict_hint") == "possible_list" for d in docs),
            "no_text": sum(d.get("verdict_hint") == "no_text" for d in docs),
            "blocked": sum(d.get("verdict_hint") == "blocked" for d in docs),
        },
        "docs": docs,
    }
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    write_markdown(md_path, report)
    print(f"\n[i] JSON -> {json_path}")
    print(f"[i] Markdown -> {md_path}")
    print(f"[i] Summary: {report['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
