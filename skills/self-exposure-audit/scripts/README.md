# doc_exposure_scan.py

Metadata-only inventory of documents on **your own** web property.

```bash
python doc_exposure_scan.py https://your-domain.example \
  --authorization "PO-2026-014" \
  --max-pages 150 --max-depth 2 --delay 0.5 \
  --json doc-findings.json --md doc-findings.md --dorks
```

## What it collects

- `robots.txt` and `sitemap.xml` seeds (documents and page URLs).
- Same-origin HTML links whose path ends in a document extension.
- `HEAD` status, `Content-Type`, and `Content-Length` for each document.
- Directory listings (`Index of /`).
- A "likely category" from filename/path keywords only (identity, payroll, hr,
  contract, customer, finance, contact, backup), ordered by sensitivity.

## What it does not do

- No document download, opening, OCR, or preview.
- No extraction of names, phone numbers, ID numbers, or other personal data.
- No third-party crawling.
- No automated search-engine scraping; `--dorks` only prints queries for manual
  review in a browser.

## Output

- `--json`: full structured result (URLs, status, type, size, category).
- `--md`: removal-oriented table plus notes.

# pii_detect.py

Redacted PII **triage** for local files the data owner authorized you to review.
It reports counts only and never emits a detected value.

```bash
python pii_detect.py --authorization "PO-2026-014" --path ./hr-export \
  --json pii-summary.json --md pii-summary.md
```

- Rejects URLs; local paths only.
- Counts: VN phone, 12-digit ID, 9-digit ID, passport, email, date of birth,
  name/DOB labels. Coarse risk: `high` if an ID/passport pattern is present,
  `medium` for phone or 3+ emails, else `low`.
- Plain text is built in; `.pdf`/`.docx`/`.xlsx` work only if `pdfminer.six`,
  `python-docx`, or `openpyxl` is installed.
- The output contains file paths, type counts, and risk — **no values**.

Pair with `exposure-assessment` (scoring) and `recon-report` (publishing).
