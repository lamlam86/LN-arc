#!/usr/bin/env python3
"""Deterministic, conservative severity scorer for recon exposure findings.

This does not test anything. It scores findings the agent already observed and
caps severity when reachability is not anonymous or confirmation is weak, so an
unverified guess can never be reported as Critical.

Usage:
    python assess.py --input findings.json --out assessment.md
    python assess.py --input findings.json --json assessment.json
"""

from __future__ import annotations

import argparse
import json
import sys

CATEGORY_BASE = {
    "secrets": 88,
    "backup": 78,
    "storage": 76,
    "vcs": 72,
    "debug": 66,
    "other": 40,
    "api-docs": 28,
    "metadata": 12,
}
DATA_BUMP = {"credentials": 10, "pii": 10, "config": 5, "source": 4, "docs": 0, "metadata": 0, "none": -10}
REACH_BUMP = {"anonymous": 8, "authenticated": -25, "internal": -35, "unknown": -8}
CONF_BUMP = {"confirmed": 4, "probable": 0, "unverified": -15}
BLAST_BUMP = {"environment": 6, "platform": 4, "host": 0, "unknown": -3}

LABELS = [(85, "Critical"), (70, "High"), (50, "Medium"), (25, "Low"), (0, "Info")]
PRIORITY = {"Critical": 1, "High": 1, "Medium": 2, "Low": 3, "Info": 5}


def severity(score: int) -> str:
    for floor, label in LABELS:
        if score >= floor:
            return label
    return "Info"


def score_one(f: dict) -> dict:
    cat = str(f.get("category", "other")).lower()
    reach = str(f.get("reachability", "unknown")).lower()
    conf = str(f.get("confirmation", "unverified")).lower()
    data = str(f.get("data_class", "none")).lower()
    blast = str(f.get("blast_radius", "unknown")).lower()

    s = CATEGORY_BASE.get(cat, 40)
    s += DATA_BUMP.get(data, 0)
    s += REACH_BUMP.get(reach, -8)
    s += CONF_BUMP.get(conf, -15)
    s += BLAST_BUMP.get(blast, -3)

    # Conservative caps: Critical requires confirmed anonymous access to
    # credentials or PII. Everything else tops out at High. Unverified findings
    # cannot exceed Medium, and public docs/metadata cannot exceed Medium.
    critical_eligible = (
        reach == "anonymous" and conf == "confirmed" and data in ("credentials", "pii")
    )
    if not critical_eligible:
        s = min(s, 84)
    if conf == "unverified":
        s = min(s, 69)
    if cat in ("api-docs", "metadata"):
        s = min(s, 69)

    s = max(0, min(100, s))
    sev = severity(s)
    return {
        "id": f.get("id", ""),
        "title": f.get("title", "(untitled)"),
        "url": f.get("url", ""),
        "severity": sev,
        "score": s,
        "priority": PRIORITY[sev],
        "reachability": reach,
        "confirmation": conf,
        "data_class": data,
        "evidence": f.get("evidence", ""),
        "impact": f.get("impact", ""),
        "remediation": f.get("remediation", ""),
        "limits": f.get("limits", "No exploitation attempted; severity reflects reachability and data class only."),
    }


def table(rows: list[dict]) -> str:
    out = ["| # | Severity | Priority | Finding | Reachability | Evidence |", "|---|---|---|---|---|---|"]
    for r in rows:
        ev = str(r["evidence"]).replace("|", "\\|").replace("\n", " ")[:160]
        out.append(
            f"| {r['id']} | **{r['severity']}** | {r['priority']} | {r['title']} "
            f"| {r['reachability']} | {ev} |"
        )
    return "\n".join(out)


def render(doc: dict, rows: list[dict]) -> str:
    counts = {k: 0 for k in ("Critical", "High", "Medium", "Low", "Info")}
    for r in rows:
        counts[r["severity"]] += 1
    out = ["# Exposure assessment\n"]
    if doc.get("target"):
        out.append(f"Target: `{doc['target']}`\n")
    out.append("## Summary\n")
    out.append("| Severity | Count |\n|---|---|")
    for k in counts:
        out.append(f"| {k} | {counts[k]} |")
    out.append("")
    out.append(
        "> No exploitation was attempted. Severity reflects observed reachability, "
        "confirmation strength, and data class only.\n"
    )
    out.append("## Findings\n")
    out.append(table(rows))
    out.append("")
    out.append("## Detail\n")
    for r in rows:
        out.append(f"### {r['id']} — {r['title']}\n")
        out.append(f"- **Severity:** {r['severity']} (score {r['score']}, confidence {r['confirmation']})")
        out.append(f"- **Priority:** {r['priority']}")
        out.append(f"- **URL:** {r['url']}")
        out.append(f"- **Reachability:** {r['reachability']}")
        out.append(f"- **Data class:** {r['data_class']}")
        if r["evidence"]:
            out.append(f"- **Evidence:** {r['evidence']}")
        if r["impact"]:
            out.append(f"- **Why it matters:** {r['impact']}")
        out.append(f"- **Limits:** {r['limits']}")
        if r["remediation"]:
            out.append(f"- **Remediation:** {r['remediation']}")
        out.append("")
    out.append("## Remediation order\n")
    for r in sorted(rows, key=lambda x: (x["priority"], -x["score"])):
        out.append(f"{r['priority']}. **{r['title']}** — {r['remediation'] or 'remove/block and rotate as needed'}")
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Score observed exposure findings (no exploitation).")
    ap.add_argument("--input", required=True, help="findings JSON")
    ap.add_argument("--out", default="assessment.md")
    ap.add_argument("--json", metavar="FILE", help="also write the scored rows as JSON")
    args = ap.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[!] cannot read input: {e}", file=sys.stderr)
        return 2

    findings = doc.get("findings", doc if isinstance(doc, list) else [])
    if not isinstance(findings, list):
        print("[!] input must be a list or {\"findings\": [...]}", file=sys.stderr)
        return 2

    rows = sorted((score_one(f) for f in findings), key=lambda r: (-r["score"], r["id"]))
    try:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(render(doc if isinstance(doc, dict) else {}, rows))
    except OSError as e:
        print(f"[!] cannot write output: {e}", file=sys.stderr)
        return 1
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2)

    print(f"Wrote {args.out} ({len(rows)} findings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
