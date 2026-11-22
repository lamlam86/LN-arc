#!/usr/bin/env python3
"""Assess the sensitivity of documents scanned by google-dork-pii.

Reads pii-scan.json (counts/structure only) and assigns a sensitivity level and
remediation priority. It never reads document bodies and never prints values.

Usage:
  python pii_assess.py --input pii-scan.json --out pii-assessment.md
  python pii_assess.py --input pii-scan.json --json pii-assessment.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Review": 3, "Low": 4, "Info": 5}
PRIORITY = {"Critical": 1, "High": 1, "Medium": 2, "Review": 2, "Low": 3, "Info": 5}


def g(d: dict, *path, default=0):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def assess(doc: dict) -> dict:
    status = doc.get("status")
    verdict = doc.get("verdict_hint", "unknown")
    cccd = g(doc, "distinct", "cccd_12_valid")
    cmnd = g(doc, "distinct", "cmnd_9_digit")
    phone = g(doc, "distinct", "vn_phone")
    email = g(doc, "counts", "email")
    name = g(doc, "labels", "name")
    addr = g(doc, "labels", "address")
    multi = g(doc, "structure", "lines_with_multiple_pii")
    label_pii = g(doc, "structure", "lines_with_label_and_pii")
    table = g(doc, "labels", "table")
    id_count = cccd + cmnd
    id_label = g(doc, "labels", "cccd") + g(doc, "labels", "phone")
    has_id = id_count > 0
    has_contact = (phone + email) > 0
    has_identity = (name + addr) > 0
    list_shape = multi >= 2 or table >= 1 or label_pii >= 2
    public = status == 200

    if not public:
        sev = "Info"
        why = f"not publicly readable (status {status}); do not bypass"
    elif doc.get("note", "").startswith("scanned_or_image_pdf") or verdict == "no_text":
        sev = "Review"
        why = "scanned/image PDF: no text layer, sensitivity not assessed; needs authorized manual review"
    elif has_id and id_count >= 10 and list_shape:
        sev = "Critical"
        why = f"{id_count} distinct ID values ({cccd} CCCD, {cmnd} CMND) in a list; public"
    elif has_id and id_count >= 3 and (list_shape or has_identity or id_label):
        sev = "High"
        why = f"{id_count} distinct ID values ({cccd} CCCD, {cmnd} CMND) with {'list structure' if list_shape else 'identity context'}; public"
    elif has_id and (list_shape or has_identity):
        sev = "High"
        why = f"{id_count} ID value(s) ({cccd} CCCD, {cmnd} CMND) with {'list structure' if list_shape else 'identity context'}; public"
    elif has_contact and has_identity and phone >= 10:
        sev = "High"
        why = f"{phone} distinct phones with name/address labels; public"
    elif (list_shape and has_contact) or has_id or (has_contact and has_identity):
        sev = "Medium"
        why = f"contact/identity data ({phone} phones, {email} emails) with {'list structure' if list_shape else 'limited context'}; public"
    elif has_contact:
        sev = "Low"
        why = f"incidental contact data ({phone} phones, {email} emails), no list/identity"
    else:
        sev = "Info"
        why = "no PII counted"

    if sev in ("Critical", "High"):
        action = "Remove/restrict the file now; rotate/notify data owner; de-index; re-check with HEAD"
    elif sev == "Medium":
        action = "Restrict or remove; confirm whether the data is intended to be public; de-index"
    elif sev == "Review":
        action = "Authorized manual review (do not bulk OCR); restrict if it contains ID lists"
    elif sev == "Low":
        action = "Verify business need; keep behind auth if not intentional"
    else:
        action = "No action; keep monitoring"

    return {
        "url": doc.get("url", ""),
        "verdict": verdict,
        "severity": sev,
        "priority": PRIORITY[sev],
        "public": public,
        "pages": doc.get("pages"),
        "kind": doc.get("kind", ""),
        "cccd": cccd,
        "cmnd": cmnd,
        "phones": phone,
        "emails": email,
        "name_labels": name,
        "address_labels": addr,
        "list_structure": list_shape,
        "rationale": why,
        "action": action,
    }


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description="Sensitivity assessment for pii-scan.json (no values).")
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", default="pii-assessment.md")
    ap.add_argument("--json", metavar="FILE")
    args = ap.parse_args()

    try:
        doc = json.load(open(args.input, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"[!] cannot read input: {e}", file=sys.stderr)
        return 2

    docs = doc.get("docs") or []
    rows = sorted((assess(d) for d in docs), key=lambda r: (ORDER[r["severity"]], r["url"]))
    counts = {k: 0 for k in ORDER}
    for r in rows:
        counts[r["severity"]] += 1
    overall = next((k for k in ("Critical", "High", "Medium", "Review", "Low", "Info") if counts[k]), "Info")

    lines = ["# PII sensitivity assessment\n",
             f"- Target: `{doc.get('site','')}`",
             f"- Authorization: `{doc.get('authorization','')}`",
             f"- Generated: {dt.datetime.now().astimezone().isoformat(timespec='seconds')}",
             f"- Documents: {len(rows)}",
             f"- **Overall: {overall}**\n",
             "| # | Severity | Verdict | URL | CCCD | Phones | Emails | Names/Addr | List | Rationale | Priority action |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        lines.append(
            f"| {i} | **{r['severity']}** | {r['verdict']} | {r['url']} | {r['cccd']} | {r['phones']} "
            f"| {r['emails']} | {r['name_labels']}/{r['address_labels']} | {'yes' if r['list_structure'] else 'no'} "
            f"| {r['rationale']} | {r['action']} |"
        )
    lines.append("\n## Priority order\n")
    for r in sorted(rows, key=lambda x: (x["priority"], ORDER[x["severity"]])):
        if r["severity"] in ("Info", "Low"):
            continue
        lines.append(f"{r['priority']}. **{r['severity']}** — {r['url']}\n   {r['action']}")
    lines.append("\n> Counts only. No full phone, CCCD/CMND, name, email or address is included. "
                 "Hints are deterministic triage, not a final legal/PII classification.\n")

    open(args.out, "w", encoding="utf-8").write("\n".join(lines))
    if args.json:
        json.dump({"overall": overall, "counts": counts, "findings": rows},
                  open(args.json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Wrote {args.out} ({len(rows)} documents, overall {overall})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
