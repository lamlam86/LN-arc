---
name: google-dork-pii
description: Use when an authorized target's Google-indexed public documents must be checked for exposed lists of Vietnamese phone numbers or CCCD/CMND citizen IDs — run a scoped dork, triage each result read-only, and report only aggregate, redacted evidence.
---

# Google Dork → PII exposure confirmation

Find documents that Google has indexed on an **authorized** domain, then decide
which ones actually expose a *list of people* (phone numbers and/or CCCD/CMND)
rather than merely mentioning those words.

This skill is a **defensive reporting** workflow. The output is a short list of
URLs with counts and a verdict, so the data owner can remove or restrict the
documents. It is **not** a data-extraction or people-search tool.

---


Relationship to `self-exposure-audit`: that skill is metadata-only (filename and
`HEAD`). This skill is the **content-confirmation** step for the same authorized
domain. It may download a document, but only to count matches in memory; it still
never stores a value or a body. Do not run it on a domain the other skill would
reject.

---

## Hard boundaries

| Allowed | Prohibited |
|---|---|
| Scoped `site:` dork via a real browser | Dorking third-party or unrelated domains |
| Anonymous `GET` of a result to confirm it is public | Auth bypass, cookies/tokens from the target, credential use |
| In-memory text extraction and **counts** | Writing document bodies, full numbers, names, or addresses to disk/chat/report |
| Masked samples (`09xxxxxx67`, `096xxxxxx234`) | Reproducing any full phone/CCCD/CMND value |
| Stopping at `401/403/429` | Evading WAF, rotating proxies to defeat a block, bulk crawling |
| Manual/authorized OCR of a scanned PDF | Automated OCR at scale or building a PII database |

Rate-limit: keep the scanner delay ≥1 s per document; the dorker already pauses
between pages. If Google or the target blocks you, stop and report the block.

---

## Step 1 — Create the output directory

Write every artifact under the **task working directory**, never into this
skill's `scripts/` directory:

```bash
OUT="recon/gdork-pii-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
echo "$OUT"
```

Scripts live in `${SKILL_DIR}/scripts/` (the loader expands `${SKILL_DIR}` to the
absolute skill path). Run them directly; do not modify them.

---

## Step 2 — Run the scoped dork

Start from one `site:` domain and a quoted OR group. The runner splits
`(A OR B OR C)` into one query per branch while preserving `site:` — this is
what keeps Google from silently dropping the site filter.

```bash
python3 "${SKILL_DIR}/scripts/google_dork.py" \
  --query 'site:camau.baohiemxahoi.gov.vn ("CCCD" OR "số điện thoại" OR "SĐT") filetype:pdf' \
  --num 40 --pages 4 --delay-min 2 --delay-max 4 \
  --csv "$OUT/dork.csv" --json "$OUT/dork.json" \
  --profile "${SKILL_DIR}/scripts/chrome-profile"
```

The bundled `scripts/chrome-profile` is a local-only browser profile. If it is
missing, the script creates a fresh profile. If Google blocks headless with an
"unusual traffic" page, rerun with:

```bash
python3 "${SKILL_DIR}/scripts/google_dork.py" ... \
  --headful --wait-captcha 180
```

and solve the CAPTCHA in the opened window, or use an authorized egress proxy
with `--proxy http://host:port`. Do not rotate proxies to defeat a block.

Useful flags:

| Situation | Flag |
|---|---|
| Google returns a consent page | handled automatically |
| "unusual traffic" / `/sorry/` page | `--proxy http://host:port` (authorized egress) or stop |
| Headless gets challenged in a container | `--xvfb` (needs `xvfb-run`) |
| You must solve a CAPTCHA yourself | `--headful --wait-captcha 180` |
| Google dropped `site:` on later pages | handled: retries with basic HTML (`gbv=1`) |

The script prints each title + URL and writes both files. **Do not** open result
URLs in the chat or paste document bodies into context.

If the dork returns zero in-scope results, record that negative result and stop;
do not broaden to other domains.

---

## Step 3 — Triage the documents (read-only, redacted)

```bash
python3 "${SKILL_DIR}/scripts/doc_pii_scan.py" \
  --authorization "PO-2026-014" \
  --input "$OUT/dork.csv" \
  --site camau.baohiemxahoi.gov.vn \
  --max-bytes 20000000 --delay 1.0 \
  --out-dir "$OUT"
```

Outputs:

- `$OUT/pii-scan.json` — per-document aggregate evidence (read this).
- `$OUT/pii-scan.md` — the same, sorted by score, for the report.
- No response body is saved; full PII values are never emitted.

### Step 3b — Sensitivity assessment (severity + priority)

Turn the counts into a risk judgement for the data owner:

```bash
python3 "${SKILL_DIR}/scripts/pii_assess.py" \
  --input "$OUT/pii-scan.json" \
  --out "$OUT/pii-assessment.md" \
  --json "$OUT/pii-assessment.json"
```

Outputs `pii-assessment.md` and `pii-assessment.json` with one row per document:

| Level | Typical case |
|---|---|
| **Critical** | ≥10 distinct CCCD/CMND in a list, publicly readable |
| **High** | ≥3 IDs with list/identity context, or ≥1 ID with list context, or ≥10 phones + names/addresses |
| **Medium** | contact/identity data with list structure or limited context |
| **Review** | scanned/image PDF (no text layer) — needs authorized manual review |
| **Low** | 1–2 incidental contact details, no list/identity |
| **Info** | no PII counted, or not publicly readable |

The assessment is deterministic triage, not a legal PII classification. It never
prints values; it uses only `pii-scan.json` counts/labels/structure. Use it as the
input to the analyst verdict in Step 4 and to the remediation priority in Step 6.

The scanner only performs anonymous `GET`, blocks cross-host redirects outside
`--site`, and stops reading at `--max-bytes`. `401/403` → `blocked`; do not retry
with credentials.

### What the JSON gives you

Per document:

| Field | Meaning |
|---|---|
| `kind` | `pdf`, `html`, `csv`, `xlsx`, `docx`, `text`, `binary` |
| `pages`, `text_chars`, `note` | extraction coverage; `no_text` usually means a scanned PDF |
| `counts` / `distinct` | occurrences and distinct values: `vn_phone`, `cccd_12_valid`, `cmnd_9_digit`, `email` |
| `labels` | hits for `phone`, `cccd`, `name`, `address`, `table` labels |
| `structure.lines_with_multiple_pii` | lines carrying ≥2 PII values (table/list shape) |
| `structure.lines_with_label_and_pii` | label + value on the same line |
| `structure.distinct_pii_per_1k_chars` | density |
| `score` / `verdict_hint` / `confidence_hint` | deterministic hint, not the final answer |
| `masked_samples` | at most 3 masked shapes per type; never full values |

Only CCCD-shaped 12-digit numbers that pass the province/century check are
counted in `cccd_12_valid`; random 12-digit account numbers are excluded.

---

## Step 4 — LLM judgment (the decision)

You are the analyst. Read `pii-scan.json` and decide per URL. Do **not** fetch the
document again and do **not** ask for the raw text.

| Final verdict | Criteria (all observed from the JSON) |
|---|---|
| **confirmed_list** | `distinct.cccd_12_valid ≥ 3` **or** `distinct.vn_phone ≥ 5`; **and** a matching label (`labels.cccd` or `labels.phone`); **and** list structure (`lines_with_multiple_pii ≥ 2` or `labels.table ≥ 1`); not `no_text` |
| **probable_list** | counts meet the threshold but structure/labels are weak, **or** `verdict_hint` is `likely_list` while one signal is missing |
| **single_record** | one person's ID/contact detail (≤1 CCCD, ≤2 phones, no multi-value lines) — not a list |
| **incidental_contact** | 1–2 phones, no CCCD, no multi-value lines — ordinary contact info |
| **mention_only** | the terms appear but no repeated values (policy text, forms, guides) |
| **needs_manual_review** | `no_text` (scanned PDF), legacy `.doc/.xls`, truncated download, or extraction note |
| **not_exposed** | `blocked` (401/403/429), 404, out of scope, or not a document |

Rules:

- Prefer `possible` over `confirmed` when the evidence is a single page or a
  single signal. Never invent values you did not see counted.
- `mention_only` and `incidental_contact` are **not** findings.
- If a document is `needs_manual_review`, say so and recommend an authorized
  manual check; do not OCR it yourself unless the data owner approved it.
- Keep the user's language (Vietnamese) in the final summary.

---

## Step 5 — Record evidence in the graph

For every **confirmed_list** / **probable_list** URL:

1. Register the document as an endpoint asset (batch them):
   ```json
   {"assets":[{"type":"endpoint","url":"https://.../file.pdf","method":"GET",
     "status_code":200,"description":"Public document with exposed PII list"}]}
   ```
2. Record one fact per document (or one consolidated fact if many):
   ```json
   {"summary":"Public PDF on <host> exposes a list of phone numbers and CCCD numbers",
    "detail":"phone_distinct=12, cccd_valid_distinct=9, score=12, verdict=confirmed_list; values not retained",
    "evidence":"doc_pii_scan.py: verdict_hint=likely_list score=12 labels.cccd=4 lines_with_multiple_pii=14",
    "confidence":"observed"}
   ```

Never put a full number, name, or address in `detail`/`evidence`.

---

## Step 6 — Report to the data owner

Create `$OUT/pii-exposure.md` (or a section in the task report) with:

1. **Scope & authorization** — domain, date, authorization reference.
2. **Method** — dork query, number of results, anonymous GET only, redaction policy.
3. **Confirmed exposures** — table: URL, type, pages, distinct phone count,
   valid CCCD count, list-shape evidence, final verdict, confidence.
4. **Not findings** — mention-only / incidental / blocked / needs manual review.
5. **Impact** — explain that a name+phone+CCCD list enables identity fraud,
   account takeover and targeted scams; do **not** enumerate the values.
6. **Remediation** — remove or move behind auth, block the path/extension,
   `X-Robots-Tag: noindex`, Search Console removal, CDN purge, then re-verify
   with `HEAD` (expect 401/403/404).
7. **Limits** — scanned PDFs, truncated files, Google coverage, no OCR.

Publish with the `recon-report` skill to **Tasks → Reports** (`reports/` +
`reports/sync_web.py`) and give the user the absolute path.

---

## Dependencies and troubleshooting

```bash
python3 -c "import playwright, pypdf; print('ok')" || {
  python3 -m pip install --user playwright pypdf
  python3 -m playwright install chromium
}
```

| Symptom | Action |
|---|---|
| `Executable doesn't exist` (Playwright) | `python3 -m playwright install chromium` |
| `xvfb-run: command not found` | use headless, or install `xvfb` (the Docker image includes it) |
| Google `/sorry/` page | stop; optionally `--proxy` on an authorized egress, or `--headful --wait-captcha 180` |
| PDFs come back with `no_text` | scanned/image PDF; recommend authorized manual review, do not bulk OCR |
| `unsupported: pypdf not installed` | install `pypdf`; other formats (DOCX/XLSX/HTML/CSV/TXT) work without it |
| `private/loopback host blocked` | only for an authorized internal target: add `--allow-private` |
| Huge/slow document | lower `--max-bytes`; `truncated: true` is reported and the verdict stays conservative |

## Final check

- [ ] Authorization reference recorded; the domain is in task scope.
- [ ] Dork stayed on the `site:` domain; no other domains were searched.
- [ ] Every download was anonymous `GET`; `401/403/429` was not bypassed.
- [ ] No document body and no full PII value in files, facts, or chat.
- [ ] `pii-assessment.md` exists and its Critical/High rows are prioritised.
- [ ] Each URL has a final verdict and a confidence; hints are not blindly copied.
- [ ] Confirmed/probable URLs are registered as assets with a fact.
- [ ] Remediation and re-verification steps are in the report.
