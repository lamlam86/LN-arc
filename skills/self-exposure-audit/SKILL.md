---
name: self-exposure-audit
description: Use when an organization wants to check whether documents on its OWN web properties (contracts, HR files, spreadsheets, exports) are publicly reachable or indexed, and needs a removal plan. Metadata only; never extracts personal data.
---

# Self-Exposure Audit (own properties)

Audit **one organization's own domain(s)** for documents that should not be public:
contracts, HR/payroll files, customer exports, spreadsheets, scans, and archives.
The goal is **find, classify by filename, and remove** — not to collect content.

> This is an authorized self-audit. It is not a tool for gathering other people's
> personal data, and it never opens, downloads, OCRs, or extracts document contents.

## Preconditions (must hold before any request)

1. The operator owns or administers the domain, or holds **written authorization**
   for the exact host list. Record the authorization reference in the report.
2. Scope is limited to those hosts. Refuse wildcard "find any leaked file on the
   internet" requests, third-party domains, and person-targeted queries.
3. If ownership/authorization is unclear, stop and ask.

## Hard Boundaries

| Allowed | Prohibited |
|---|---|
| Crawl the owned site's own pages and `sitemap.xml` | Crawling or dorking third-party domains |
| `HEAD` a document to confirm it is publicly reachable | Downloading, opening, OCR-ing, or previewing documents |
| Classify by **URL/filename only** (e.g. "looks like HR") | Extracting names, phone numbers, ID numbers, salaries, or any PII |
| Check whether a URL is indexed via a `site:`-scoped query | Bulk scraping search engines or bypassing CAPTCHA |
| Report URL, type, size, status, remediation | Building lists of individuals or storing document contents |

Never reproduce a personal data value, even one glimpsed in a search snippet.
Redact it and report only the URL/type.

## Method

1. **Confirm scope** — list owned hosts and authorization reference.
2. **Passive inventory**
   - Fetch `/robots.txt` (note `Disallow` and `Sitemap:` lines).
   - Fetch `/sitemap.xml` (and nested sitemaps) for document URLs.
   - Crawl same-origin HTML pages up to a small page/depth budget, collecting
     links to document extensions: `pdf, doc, docx, xls, xlsx, ppt, pptx, csv,
     txt, rtf, odt, ods, zip, rar, 7z, tar, gz`.
   - Flag directory listings (`Index of /`).
3. **Confirm reachability** — send `HEAD` to each unique document URL. Treat
   `200` as public, `401/403` as protected, `404` as gone. Do not follow into the
   body. Record `Content-Type` and `Content-Length`.
4. **Classify by filename/path only** — use keyword groups:
   `hr`, `nhân sự`, `tuyển dụng`, `cv`, `resume`, `contract`, `hợp đồng`,
   `payroll`, `lương`, `salary`, `invoice`, `hoá đơn`, `customer`, `khách hàng`,
   `cccd`, `cmnd`, `passport`, `phone`, `sđt`, `export`, `backup`.
   Label as **likely** — never as confirmed content.
5. **Index check** — generate `site:<owned-host> …` queries and review result
   metadata manually in the browser. Do not auto-scrape search engines.
6. **Report** — URL, status, type, size, likely category, severity, owner of the
   fix, and removal steps. Note what was **not** checked.

## Removal Playbook (include in the report)

1. Remove the file from the web root or move it behind authentication.
2. Block the directory/extension at the edge (nginx/Apache/CDN rule).
3. Add `X-Robots-Tag: noindex` for document responses and a `robots.txt` rule.
4. Request removal in Google Search Console (and Bing) for indexed URLs.
5. Purge CDN caches; verify with `HEAD` that the URL is now `401/403/404`.
6. If the document contained credentials or ID data, start the incident process
   (rotate secrets, notify the data owner, assess breach-notification duties).
7. Re-scan after 24–72h to confirm de-indexing.

## Tools

### 1. Public document inventory (remote, metadata only)

```bash
python scripts/doc_exposure_scan.py https://your-domain.example \
  --max-pages 150 --max-depth 2 --delay 0.5 \
  --json doc-findings.json --md doc-findings.md --dorks
```

- Metadata only; documents are `HEAD`-checked, never downloaded.
- `--dorks` prints `site:`-scoped queries for manual review.

### 2. Local PII triage (counts only, never values)

When the data owner asks "how sensitive is this file?", run the detector on
**local copies they provide** — not on files pulled from the internet:

```bash
python scripts/pii_detect.py --authorization "PO-2026-014" \
  --path ./authorized-hr-export --json pii-summary.json --md pii-summary.md
```

- Reads local paths only; URLs are rejected.
- Reports **counts by type** (phone, 12-digit ID, 9-digit ID, passport, email,
  date of birth, name/DOB labels) and a coarse risk level.
- Never prints, stores, or exports a detected value; never modifies the source.
- Text formats are built in; PDF/DOCX/XLSX need optional libraries
  (`pdfminer.six`, `python-docx`, `openpyxl`), otherwise reported as unsupported.
- The output ranks files for remediation; it does **not** build a PII database.

Use `exposure-assessment` to score findings and `recon-report` to publish.

## Final Check

- [ ] Authorization reference recorded; every host is owned/in scope.
- [ ] No document body downloaded or opened.
- [ ] No PII value in notes, JSON, or report.
- [ ] Findings classified by filename only, labelled "likely".
- [ ] Removal steps and re-verification date included.
