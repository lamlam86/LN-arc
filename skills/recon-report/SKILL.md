---
name: recon-report
description: Use when the user asks for a full report, summary, or export of reconnaissance results — subdomains, DNS, services, URLs, APIs, parameters, exposures, coverage — for a task or engagement.
---

# Recon Report

Compile everything that was **actually reconnoitered** into one reviewable report.
It is a factual record plus a risk assessment, not a vulnerability scan and not a
guess about what might exist.

## Output

- Default: `recon-report.md` in the current task/session working directory.
- Bilingual delivery: `reports/<id>.vi.md` and `reports/<id>.en.md`; never mix
  languages inside one file.
- Optional structured copy: `recon-report.json` (the renderer model).
- To publish to the UI: copy under `reports/`, run
  `python reports/sync_web.py`, open **Tasks → Reports**.
- Tell the user the absolute path when finished.

## Task completion trigger

When you are the planner and the next `prove_goal` would mark the **last unmet
objective**, generate this report first:

1. Write `recon-report.md` in the task working directory.
2. Follow the 11-section structure below; redact secrets and PII.
3. Verify the file exists and is non-empty before calling `prove_goal`.

Do not complete a task without a non-empty report. For a completed task that has
no report yet, generate it on the next wake-up before anything else.

## Sources (order of trust)

1. **Task context** already in the prompt: goal, scope, constraints, graph overview, goal state.
2. **Coverage tools**: `graph_overview`, `list_untested_assets`.
3. **Asset library**: `list_assets` (domains, subdomains, IPs, services, endpoints, apps).
4. **Traffic tools**: `traffic_search` → `traffic_get` / `traffic_blob` (hashes and summaries, no bodies).
5. **Files on disk**: saved responses, screenshots, transcripts, harvested JS, wordlists used.
6. **Skills used**: `subdomain-enum`, `dns-recon`, `tls-cert-recon`, `http-fingerprint`,
   `content-discovery`, `port-service-recon`, `js-endpoint-recon`, `traffic-analysis`,
   `archive-recon`, `cloud-storage-recon`, `visual-recon`, `api-recon`, `exposure-recon`,
   `google-dork`, `google-dork-pii` (results file: `google-dork-results.json`).

Mark every row with its source. Label inferred facts `inferred`; never present them
as observed.

## Required sections (full report)

The renderer emits 11 numbered sections. Everything requested below lives inside
them: subdomains/DNS in §4, URL/API/parameter/auth surfaces in §5, risk in §7.

| # | Section | Must contain |
|---|---|---|
| 1 | Executive summary | scope, asset counts, coverage %, 3–6 key findings, top risks |
| 2 | Scope & authorization | in-scope hosts, CIDRs, constraints, date range, authorization reference |
| 3 | Goals & status | each goal, met/unmet, evidence reference |
| 4 | Asset inventory (incl. subdomains & DNS) | counts by type; subdomain host/IP/CNAME/status/title/TLS/source; MX/NS/TXT, SPF/DMARC observations; services/ports; technologies with confidence |
| 5 | Endpoint / API surface (incl. paths & parameters) | URL/path table (status, type, size, auth); API table (method, path template, params, auth, content type); **5.1 parameter analysis**; **5.2 authentication & session surface** |
| 6 | Coverage | total / tested / untested per type, blockers |
| 7 | Exposed information + assessment | severity, evidence, impact, remediation; **exploitability assessment**; **priority actions** |
| 8 | Traffic evidence | method, URL, status, content-type, hash/reference; no bodies |
| 9 | Timeline | when each major discovery happened |
| 10 | Gaps & next steps | prioritized, with the skill that would cover each gap |
| 11 | Methodology & limits | tools, request rate, wordlists, vantage point, explicit limits |

Appendix (when large): full endpoint list, full asset list, glossary — attach as
extra tables at the end without renumbering.

### Google dork / search-engine exposure (inside §7)

When `google-dork` or `google-dork-pii` ran (or `google-dork-results.json` exists),
add a **Google dork / search-engine exposure** subsection to §7 with:

| Query | Engine | Results reviewed | In-scope hits | Verification | Status | Note |
|---|---|---|---|---|---|---|

- One row per query; include queries that returned nothing.
- `findings` (in-scope URLs only): query, URL, type, verification (`HEAD`/small
  `GET`), status, note. Never list out-of-scope results as findings.
- If the engine ignored `site:` or returned unrelated results, state that the
  coverage is **inconclusive**, not clean, and count the noise separately.
- Do not download documents, bypass CAPTCHA or harvest PII.

## Subdomains, paths and APIs

- **Subdomains**: every host gets IPs, CNAME, status, title, TLS issuer, source and
  in-scope flag. Dead and out-of-scope hosts are listed, not silently dropped.
- **Paths**: group by host; record status, content-type, size and whether the path
  is a page, API, static asset, redirect, protected area or fallback.
- **APIs**: normalize IDs (`/users/123` → `/users/:id`) and list query/body
  parameter names. Note method, auth requirement and content type.
- **Counts must reconcile** with the asset library and coverage endpoint.

## Parameter analysis (important)

List every parameter observed in URLs, forms, JSON bodies, headers or cookies.
Classify the **potential** risk; do not test it.

| Parameter names / locations | Potential risk class | Why it matters |
|---|---|---|
| `id`, `uid`, `user_id`, `account`, `tenant`, `org`, `company`, `project`, `order`, `invoice` | IDOR / BOLA candidate | object reference may be swapped to another owner's object |
| `url`, `uri`, `path`, `file`, `dir`, `download`, `redirect`, `next`, `return`, `continue`, `callback` | open redirect / path traversal / SSRF candidate | server may fetch or resolve a user-controlled destination |
| `q`, `query`, `search`, `filter`, `sort`, `order`, `limit`, `offset`, `page`, `fields`, `include`, `expand` | injection / data exposure surface | query builders, ORM filters and field selection often mishandled |
| `cmd`, `exec`, `command`, `ping`, `host`, `ip`, `port`, `dns`, `proxy`, `webhook` | command/SSRF candidate | direct server-side action or fetch |
| `template`, `view`, `layout`, `lang`, `format`, `ext`, `filename` | template injection / path traversal candidate | file or template resolution from user input |
| `role`, `scope`, `permission`, `admin`, `token`, `key`, `secret`, `session`, `remember` | authz / mass-assignment candidate | privilege or session material in client-controlled input |
| `file`, `upload`, `import`, `xml`, `json`, `csv`, `zip`, `archive` | upload / parser surface | file type, size and parser behaviour matter |
| `amount`, `price`, `quantity`, `discount`, `status`, `action`, `method`, `mode` | business-logic / race candidate | value trust and state transitions |

For each row record: parameter, location (query/body/path/header/cookie), methods,
sample value **redacted**, risk class, why, evidence, status (`observed`/`inferred`).
**Never send payloads, tamper with values, or attempt exploitation.**

## Evidence rules

- Facts only. No exploit claims, no fabricated endpoints, no "probably vulnerable".
- One finding = one verifiable observation with URL/status/evidence.
- No secrets: report location/type only, never the value. No PII.
- No raw request/response bodies; use hashes or references.
- Separate **confirmed** (observed) from **potential** (needs a separate authorized test).
- State what was not tested: authenticated areas, SOAP operations, destructive paths.

## Writing rules

- Vietnamese and English versions must carry identical facts and numbers.
- Short sentences; tables over prose for inventories.
- Every number traceable to a source; if truncated, say so.
- Risks ordered by priority; remediation actionable (remove/block/rotate/restrict).
- Executive summary readable by a non-technical owner; appendix for engineers.

## Renderer

```bash
python scripts/render_report.py --input report-model.json --out recon-report.md \
  --title "Recon report — <target>"
```

The model supports `parameters`, `dns`, `auth`, and `priority_actions` in addition to
assets/endpoints/exposures/assessment. Schema: `scripts/README.md`; start from
`scripts/report-model.example.json`.

## Final check

- [ ] Counts reconcile with the asset library and coverage.
- [ ] Every subdomain/path/API appears in scope.
- [ ] Parameter analysis covers URL, body, header and cookie inputs.
- [ ] Google dork results (if run) are in §7 with query, in-scope hits and
      inconclusive/noise notes.
- [ ] No secret, token, cookie, private key or PII in the output.
- [ ] Confirmed vs potential clearly separated.
- [ ] Untested items listed as gaps with the skill that would cover them.
- [ ] Bilingual versions match; file path reported to the user.
