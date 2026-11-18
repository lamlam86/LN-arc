---
name: content-discovery
description: Use when safely enumerating paths and files on an authorized web target with a small curated list, baseline-404 comparison and no brute force, to find directories, docs, admin surfaces and exposed artifacts.
---

# Safe Content Discovery (detailed)

## Objective

Find reachable paths on an authorized web target — with a small curated list,
low rate and false-positive control. Not a directory brute-force tool.

## Inputs

- Verified base URLs (host + scheme after redirects).
- Baseline 404/SPA signature from `http-fingerprint`.
- Existing endpoints (`list_assets`) to avoid duplicates.

## Step 1 — Baseline and controls

1. Request `/__recon_<random>__`; record status, length, content-type, body hash.
2. If it returns `200` with the app shell, treat identical responses as `FALLBACK`.
3. Note WAF/CDN behaviour: 403 page shape, rate-limit headers, CAPTCHA.
4. Set a delay (≥0.5–1s), a hard stop on repeated 429/403, and a maximum request count.

## Step 2 — Curated path groups

| Group | Examples | Purpose |
|---|---|---|
| Structure | `/robots.txt`, `/sitemap.xml`, `/sitemap_index.xml`, `/.well-known/security.txt` | discover more paths |
| Docs / API | `/docs`, `/api`, `/swagger`, `/swagger-ui/`, `/openapi.json`, `/graphql` | API surface |
| Admin / dev | `/admin`, `/login`, `/dashboard`, `/test`, `/dev`, `/staging`, `/debug` | access surfaces (record only) |
| Static / assets | `/static/`, `/assets/`, `/js/`, `/css/`, `/images/` | bundle discovery |
| Common | `/favicon.ico`, `/crossdomain.xml`, `/humans.txt`, `/.DS_Store` | fingerprint |
| Error / fallback | random path, deep path, URL-encoded path | calibrate |

Do **not** include backup/config/secret paths here — use `exposure-recon` so they
are classified, redacted and assessed consistently.

## Step 3 — Classify every response

- `HIT` — 200 and the body matches the expected type (not the fallback).
- `PROTECTED` — 401/403; record and stop. Do not attempt bypass.
- `REDIRECT` — record `Location`; verify it is in scope.
- `FALLBACK` — identical to baseline; not a hit.
- `ERROR` — 5xx; record once, do not retry aggressively.

## Step 4 — Deepen carefully

Only after a real hit:
- fetch the page, not its files;
- record title, visible form actions, script URLs;
- add discovered links to a small queue (depth ≤ 2, same origin);
- never recurse into file downloads or archives.

## Step 5 — Register

- `insert_assets` for verified paths (method, URL, status, content-type).
- Note the exact list used so the run is reproducible.
- `list_untested_assets` to update coverage.

## Evidence table

| Path | Status | Content-Type | Size | Verdict | Title / note | Source list |
|---|---|---|---|---|---|---|

## Risk signals (report only)

- Public admin/debug/install pages.
- Directory listing enabled.
- API docs exposing internal operations.
- Backup/config/secret paths (delegate to `exposure-recon`).
- SPA fallback hiding real 404s.
- WAF blocks that reveal filtering rules.

## Pitfalls

- Large wordlists or recursion.
- Calling every 200 a hit.
- Following redirects off-scope.
- Downloading files to "verify" them.
- Retrying through 429/403 blocks.

## Output

- Hits table with status/type/evidence.
- Counts: requests sent, hits, protected, fallbacks, blocks.
- Explicit "no brute force / small list" note.

## Checklist

- [ ] Baseline recorded and applied.
- [ ] Small curated list, delay, request cap.
- [ ] Stopped on blocks instead of evading.
- [ ] No bodies downloaded, no auth attempts.
- [ ] Hits registered with evidence.
