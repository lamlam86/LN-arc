#!/usr/bin/env python3
"""Publish Markdown reports to the web UI.

Scans the repo's report locations and generates web/src/lib/reports-data.ts, which
the Tasks -> Reports page imports. Bundling the content (instead of serving it from
public/) keeps the reports behind the app's authentication proxy.

Language variants are grouped by base name:
  reports/<id>.vi.md + reports/<id>.en.md  -> one report with two versions

Sources (reports/ wins over a task directory with the same task id):
  reports/*.md
  dist/artex-windows-amd64/data/tasks/<id>/recon-report.md
  data/tasks/<id>/recon-report.md

Usage:
  python reports/sync_web.py
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "web", "src", "lib", "reports-data.ts")
LANGS = ("vi", "en")
DEFAULT_LANG = "vi"


def read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def read_title(text: str, path: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return os.path.splitext(os.path.basename(path))[0]


def read_summary(text: str) -> str:
    m = re.search(
        r"(?im)^##\s+\d*\.?\s*(executive summary|tóm tắt điều hành)\s*$([\s\S]*?)(?=^##\s|\Z)",
        text,
    )
    if not m:
        return ""
    for line in m.group(2).splitlines():
        line = line.strip()
        if line.startswith("- "):
            s = line[2:].strip()
            return s if len(s) <= 240 else s[:237] + "…"
    return ""


def task_id_of(path: str, title: str) -> str:
    m = re.search(r"(?i)task\s*#?\s*(\d+)", title)
    if m:
        return m.group(1)
    parent = os.path.basename(os.path.dirname(path))
    if parent.isdigit():
        return parent
    m = re.search(r"(?i)task[-_ ]?(\d+)", os.path.basename(path))
    return m.group(1) if m else ""


def js(value: object) -> str:
    s = json.dumps(value, ensure_ascii=False)
    return s.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def find_task_report(root: str) -> str | None:
    """Find a task's report at the top level or inside an intent directory."""
    names = ("recon-report.md", "recon_report.md")
    for n in names:
        p = os.path.join(root, n)
        if os.path.isfile(p):
            return p
    matches = []
    for dirpath, _dirs, files in os.walk(root):
        for n in files:
            if n.lower() in names:
                matches.append(os.path.join(dirpath, n))
    return max(matches, key=os.path.getmtime) if matches else None


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    groups: dict[str, dict] = {}

    def add(report_id: str, lang: str, path: str) -> None:
        if not os.path.isfile(path):
            return
        content = read_text(path)
        title = read_title(content, path)
        g = groups.setdefault(report_id, {
            "id": report_id,
            "taskId": task_id_of(path, title),
            "mtime": 0.0,
            "versions": {},
        })
        if not g["taskId"]:
            g["taskId"] = task_id_of(path, title)
        g["mtime"] = max(g["mtime"], os.path.getmtime(path))
        g["versions"][lang] = {"lang": lang, "title": title, "content": content}

    # reports/ is authoritative and supports <id>.vi.md / <id>.en.md.
    reports_dir = os.path.join(ROOT, "reports")
    if os.path.isdir(reports_dir):
        for name in sorted(os.listdir(reports_dir)):
            low = name.lower()
            if not low.endswith(".md") or low == "readme.md":
                continue
            m = re.match(r"^(.+)\.(vi|en)\.md$", name, re.I)
            if m:
                add(m.group(1), m.group(2).lower(), os.path.join(reports_dir, name))
            else:
                add(os.path.splitext(name)[0], "en", os.path.join(reports_dir, name))

    # Task-directory reports are added only when reports/ has no entry for that task.
    covered_tasks = {g["taskId"] for g in groups.values() if g["taskId"]}
    for base in (
        os.path.join(ROOT, "dist", "artex-windows-amd64", "data", "tasks"),
        os.path.join(ROOT, "data", "tasks"),
    ):
        if not os.path.isdir(base):
            continue
        for tid in sorted(os.listdir(base)):
            if not tid.isdigit() or tid in covered_tasks:
                continue
            p = find_task_report(os.path.join(base, tid))
            if p:
                add(f"task-{tid}", "en", p)
                covered_tasks.add(tid)

    items = []
    for g in groups.values():
        versions = [g["versions"][lang] for lang in LANGS if lang in g["versions"]]
        if not versions:
            continue
        default = next((v for v in versions if v["lang"] == DEFAULT_LANG), versions[0])
        items.append({
            "id": g["id"],
            "title": default["title"],
            "taskId": g["taskId"],
            "created": dt.datetime.fromtimestamp(g["mtime"]).astimezone().isoformat(timespec="seconds"),
            "size": len(default["content"].encode("utf-8")),
            "summary": read_summary(default["content"]),
            "defaultLang": default["lang"],
            "versions": versions,
        })

    items.sort(key=lambda x: x["created"], reverse=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    lines = [
        "// AUTO-GENERATED by reports/sync_web.py. Do not edit by hand.",
        "// Re-run the script after adding or updating a report.",
        "",
        "export interface ReportVersion {",
        "  lang: string;",
        "  title: string;",
        "  content: string;",
        "}",
        "",
        "export interface BundledReport {",
        "  id: string;",
        "  title: string;",
        "  taskId: string;",
        "  created: string;",
        "  size: number;",
        "  summary: string;",
        "  defaultLang: string;",
        "  versions: ReportVersion[];",
        "}",
        "",
        f"export const reports: BundledReport[] = {js(items)};",
        "",
    ]
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # Remove the old public copy so report bodies are not served unauthenticated.
    public_reports = os.path.join(ROOT, "web", "public", "reports")
    if os.path.isdir(public_reports):
        for name in os.listdir(public_reports):
            try:
                os.remove(os.path.join(public_reports, name))
            except OSError:
                pass
        try:
            os.rmdir(public_reports)
        except OSError:
            pass

    print(f"Published {len(items)} report(s) to {OUT}")
    for i in items:
        langs = ", ".join(v["lang"] for v in i["versions"])
        print(f"  - {i['id']}: {i['title']} [{langs}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
