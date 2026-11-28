#!/usr/bin/env python3
"""Render a recon report model (JSON) into a consistent Markdown report.

The model is filled by the agent from observed recon data only. This script does
not fetch anything; it only formats. Common secret patterns are redacted as a
safety net, but the author must still review the output.

Usage:
    python render_report.py --input report-model.json --out recon-report.md
    python render_report.py --input report-model.json --title "Recon report — example.com"
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\boc_sk_[A-Za-z0-9_\-]{8,}"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
]


def redact(text: object) -> str:
    s = "" if text is None else str(text)
    for pat in SECRET_PATTERNS:
        s = pat.sub("[REDACTED]", s)
    return s


def cell(text: object) -> str:
    """Escape a Markdown table cell."""
    return redact(text).replace("|", "\\|").replace("\n", " ").strip()


def bullets(items: object, empty: str = "_not collected_") -> str:
    if not items:
        return empty + "\n"
    if isinstance(items, dict):
        return "\n".join(f"- **{k}**: {redact(v)}" for k, v in items.items()) + "\n"
    return "\n".join(f"- {redact(i)}" for i in items) + "\n"


def asset_rows(items: object) -> str:
    if not items:
        return "_not collected_\n"
    rows = ["| Asset | Note | Source |", "|---|---|---|"]
    for it in items:
        if isinstance(it, dict):
            rows.append(f"| {cell(it.get('value'))} | {cell(it.get('note'))} | {cell(it.get('source'))} |")
        else:
            rows.append(f"| {cell(it)} |  |  |")
    return "\n".join(rows) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Render recon report Markdown from a JSON model.")
    ap.add_argument("--input", required=True, help="report model JSON")
    ap.add_argument("--out", default="recon-report.md")
    ap.add_argument("--title", default="Recon report")
    args = ap.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            m = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[!] cannot read model: {e}", file=sys.stderr)
        return 2

    task = m.get("task") or {}
    assets = m.get("assets") or {}
    coverage = m.get("coverage") or {}
    out: list[str] = []

    out.append(f"# {redact(args.title)}\n")
    out.append(f"Generated: {dt.datetime.now().astimezone().isoformat(timespec='seconds')}\n")
    meta = [
        ("Task", task.get("id")),
        ("Name", task.get("name")),
        ("Status", task.get("status")),
        ("Started", task.get("started")),
        ("Finished", task.get("finished")),
    ]
    if any(v for _, v in meta):
        out.append("| Field | Value |\n|---|---|")
        for k, v in meta:
            if v:
                out.append(f"| {cell(k)} | {cell(v)} |")
        out.append("")

    out.append("## 1. Executive summary\n")
    out.append(bullets(m.get("summary")))

    out.append("\n## 2. Scope & authorization\n")
    out.append(bullets(m.get("scope")))
    if m.get("constraints"):
        out.append("\n**Constraints**\n")
        out.append(bullets(m.get("constraints")))

    out.append("\n## 3. Goals & status\n")
    goals = m.get("goals") or []
    if goals:
        out.append("| Goal | Status | Evidence |\n|---|---|---|")
        for g in goals:
            out.append(f"| {cell(g.get('goal'))} | {cell(g.get('status'))} | {cell(g.get('evidence'))} |")
    else:
        out.append("_not collected_")
    out.append("")

    out.append("## 4. Asset inventory\n")
    labels = [
        ("domains", "Domains"), ("subdomains", "Subdomains"), ("ips", "IP addresses"),
        ("services", "Services / ports"), ("technologies", "Technologies"),
    ]
    for key, label in labels:
        out.append(f"### {label}\n")
        out.append(asset_rows(assets.get(key)))
        out.append("")

    dns = m.get("dns") or []
    if dns:
        out.append("### DNS records\n")
        out.append("| Name | Type | Value | Note |\n|---|---|---|---|")
        for d in dns:
            out.append(
                f"| {cell(d.get('name'))} | {cell(d.get('type'))} "
                f"| {cell(d.get('value'))} | {cell(d.get('note'))} |"
            )
        out.append("")

    out.append("## 5. Endpoint / API surface\n")
    eps = m.get("endpoints") or []
    if eps:
        out.append("| Method | URL / Path | Parameters | Auth | Source |\n|---|---|---|---|---|")
        for e in eps:
            out.append(
                f"| {cell(e.get('method'))} | {cell(e.get('url'))} | {cell(e.get('params'))} "
                f"| {cell(e.get('auth'))} | {cell(e.get('source'))} |"
            )
    else:
        out.append("_not collected_")
    out.append("")

    params = m.get("parameters") or []
    if params:
        out.append("### 5.1 Parameter analysis\n")
        out.append(
            "| Parameter | Location | Methods | Risk class | Why it matters | Evidence |\n"
            "|---|---|---|---|---|---|"
        )
        for p in params:
            out.append(
                f"| {cell(p.get('name'))} | {cell(p.get('location'))} | {cell(p.get('methods'))} "
                f"| {cell(p.get('risk'))} | {cell(p.get('why'))} | {cell(p.get('evidence'))} |"
            )
        out.append("\n_Assessment only: no payloads were sent and values are redacted._")
        out.append("")

    auth = m.get("auth") or []
    if auth:
        out.append("### 5.2 Authentication & session surface\n")
        out.append("| Surface | Endpoint | Observed behaviour | Notes |\n|---|---|---|---|")
        for a in auth:
            out.append(
                f"| {cell(a.get('surface'))} | {cell(a.get('endpoint'))} "
                f"| {cell(a.get('behaviour'))} | {cell(a.get('note'))} |"
            )
        out.append("")

    out.append("## 6. Coverage\n")
    if coverage:
        out.append(
            f"- Total assets: **{redact(coverage.get('total', 0))}**\n"
            f"- Tested: **{redact(coverage.get('tested', 0))}**\n"
            f"- Untested: **{redact(coverage.get('untested', 0))}**\n"
        )
        if coverage.get("note"):
            out.append(f"\n{redact(coverage.get('note'))}\n")
        if coverage.get("untested_assets"):
            out.append("\n**Untested assets**\n")
            out.append(bullets(coverage.get("untested_assets")))
    else:
        out.append("_not collected_")
    out.append("")

    out.append("## 7. Exposed information\n")
    exps = m.get("exposures") or []
    if exps:
        out.append("| Severity | Finding | URL | Evidence | Impact | Remediation |\n|---|---|---|---|---|---|")
        for e in exps:
            out.append(
                f"| {cell(e.get('severity'))} | {cell(e.get('title'))} | {cell(e.get('url'))} "
                f"| {cell(e.get('evidence'))} | {cell(e.get('impact'))} | {cell(e.get('remediation'))} |"
            )
        out.append("\n_Secret values are intentionally redacted; only location and type are reported._")
    else:
        out.append("_No public exposure was identified during this run._")
    out.append("")

    gd = m.get("google_dork")
    if gd:
        out.append("\n### Google dork / search-engine exposure\n")
        if gd.get("engine"):
            out.append(f"**Engine:** {redact(gd['engine'])}\n")
        queries = gd.get("queries") or []
        if queries:
            out.append(
                "| Query | Engine | Results reviewed | In-scope hits | Verification | Status | Note |\n"
                "|---|---|---|---|---|---|---|"
            )
            for q in queries:
                out.append(
                    f"| {cell(q.get('query'))} | {cell(q.get('engine'))} | {cell(q.get('results'))} "
                    f"| {cell(q.get('in_scope'))} | {cell(q.get('verification'))} | {cell(q.get('status'))} "
                    f"| {cell(q.get('note'))} |"
                )
        hits = gd.get("findings") or []
        if hits:
            out.append("\n**In-scope results**\n")
            out.append("| Query | URL | Type | Verification | Status | Note |\n|---|---|---|---|---|---|")
            for h in hits:
                out.append(
                    f"| {cell(h.get('query'))} | {cell(h.get('url'))} | {cell(h.get('type'))} "
                    f"| {cell(h.get('verification'))} | {cell(h.get('status'))} | {cell(h.get('note'))} |"
                )
        notes = gd.get("notes") or []
        if notes:
            out.append("\n")
            out.append(bullets(notes))
        if not queries and not hits and not notes:
            out.append("_not collected_\n")
        out.append("")

    asm = m.get("assessment")
    if asm:
        out.append("\n### Exploitability assessment\n")
        if asm.get("note"):
            out.append(redact(asm["note"]) + "\n")
        risks = asm.get("risks") or []
        if risks:
            out.append("| Risk | Severity | Evidence status | Exploitability | Priority action |\n|---|---|---|---|---|")
            for r in risks:
                out.append(
                    f"| {cell(r.get('title'))} | {cell(r.get('severity'))} | {cell(r.get('status'))} "
                    f"| {cell(r.get('exploitability'))} | {cell(r.get('action'))} |"
                )
    actions = m.get("priority_actions") or []
    if actions:
        out.append("\n### Priority actions\n")
        for i, a in enumerate(actions, 1):
            out.append(f"{i}. {redact(a)}")
        out.append("")
    out.append("")

    out.append("## 8. Traffic evidence\n")
    tr = m.get("traffic") or []
    if tr:
        out.append("| Method | URL | Status | Content-Type | Reference |\n|---|---|---|---|---|")
        for t in tr:
            out.append(
                f"| {cell(t.get('method'))} | {cell(t.get('url'))} | {cell(t.get('status'))} "
                f"| {cell(t.get('content_type'))} | {cell(t.get('ref'))} |"
            )
    else:
        out.append("_not collected_")
    out.append("")

    out.append("## 9. Timeline\n")
    tl = m.get("timeline") or []
    if tl:
        out.append("| Time | Event |\n|---|---|")
        for t in tl:
            out.append(f"| {cell(t.get('time'))} | {cell(t.get('event'))} |")
    else:
        out.append("_not collected_")
    out.append("")

    out.append("## 10. Gaps & next steps\n")
    out.append(bullets(m.get("gaps")))

    out.append("\n## 11. Methodology\n")
    out.append(bullets(m.get("methodology")))

    text = "\n".join(out).rstrip() + "\n"
    try:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
    except OSError as e:
        print(f"[!] cannot write report: {e}", file=sys.stderr)
        return 1
    print(f"Wrote {args.out} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
