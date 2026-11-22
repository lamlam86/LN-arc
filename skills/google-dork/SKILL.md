---
name: google-dork
description: Use when building and reviewing site-scoped Google dorks for an authorized domain to find publicly indexed documents, configs, backups, admin panels and API docs (manual review, no scraping, no PII harvesting).
---

# Google Dork Recon

Build targeted search queries for an **authorized** domain and review the indexed
results for attack-surface exposure.

## Boundaries

- Scope: only the authorized root domain and its subdomains.
- **Manual review** in a browser (or the `web_search` tool). Do not scrape Google
  or bypass CAPTCHA; automated querying violates the search provider's terms.
- Read-only: review titles/snippets/URLs, then verify with `HEAD`/small `GET`.
- **No PII harvesting.** Never build dorks for national IDs, phone lists, HR or
  contract files, customer data, or personal information. If asked, refuse and
  point to `self-exposure-audit` for the organization's own metadata-only check.
- Do not download exposed documents, use credentials, or bypass authentication.
- Redact secrets in notes/screenshots; report location and type only.

## Step 1 — Scope

List the authorized root and known subdomains. Every query must include
`site:<domain>` or `site:*. <domain>` so results stay in scope.

## Step 2 — Query categories

| Goal | Example query |
|---|---|
| Indexed documents | `site:example.com filetype:pdf` |
| Office/spreadsheet | `site:example.com (filetype:docx OR filetype:xlsx OR filetype:pptx)` |
| Data/export files | `site:example.com (filetype:csv OR filetype:txt OR filetype:json)` |
| Config / env | `site:example.com (inurl:.env OR inurl:config OR inurl:settings)` |
| Backups / dumps | `site:example.com (ext:bak OR ext:old OR ext:zip OR ext:sql OR ext:log)` |
| VCS metadata | `site:example.com (inurl:.git OR inurl:.svn)` |
| Directory listing | `site:example.com intitle:"index of"` |
| Admin / login | `site:example.com (inurl:admin OR inurl:login OR inurl:dashboard)` |
| API docs | `site:example.com (inurl:swagger OR inurl:api-docs OR inurl:openapi)` |
| Debug / errors | `site:example.com (inurl:debug OR inurl:phpinfo OR intext:"stack trace")` |
| Subdomains | `site:*.example.com -www` |
| Archive copies | `site:example.com` plus the Wayback/URLScan steps from `archive-recon` |

## Step 3 — Review results

For each result record: query, URL, title/snippet, file type, indexed date if
shown, and whether it is still live. Do **not** open or download the document.

Verify live exposure with a read-only `HEAD` (or `GET` with a small range):

- `200` + expected content-type → public; report.
- `401/403` → protected; stop.
- `404` → stale index; note for removal.
- Redirect → check the target stays in scope.

Feed confirmed URLs to `exposure-recon` and `exposure-assessment`.

## Step 4 — Triage and report

| Severity | Example |
|---|---|
| High | Anonymous access to backups, configs, source archives |
| Medium | Internal docs, export files, admin/API documentation |
| Low | Public docs that only aid fingerprinting |
| Info | Stale indexed URL that now 404s |

Report per finding: URL, type, why it matters, remediation (remove file, block
path, `X-Robots-Tag: noindex`, Search Console removal), and whether it was
downloaded (it was not).

## Step 5 — Removal

1. Remove/block the file at the edge.
2. Add `X-Robots-Tag: noindex` and a `robots.txt` rule.
3. Request removal in Google Search Console / Bing Webmaster.
4. Re-check the URL with `HEAD` and re-run the query after 24–72h.

## Pitfalls

- Running queries without `site:` (unscoped results).
- Scraping Google programmatically.
- Opening/downloading sensitive documents.
- Treating an indexed snippet as proof of current exposure.
- Searching for personal data (prohibited).

## Checklist

- [ ] Every query is scoped to the authorized domain.
- [ ] Manual review only; no scraping.
- [ ] No PII queries; secrets redacted.
- [ ] Live status verified with read-only requests.
- [ ] Findings and removal steps recorded.
