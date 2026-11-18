---
name: archive-recon
description: Use when discovering historical or forgotten hosts, paths and parameters for an authorized target through passive archives (Wayback CDX, URLScan, certificate transparency) and verifying what is still reachable.
---

# Archive / Historical Recon (detailed)

## Objective

Find what was once public for an authorized target, then verify what is still live
— without copying archived data or bypassing access controls.

## Inputs

- In-scope root/hosts.
- Permission for passive lookups and read-only verification.
- Current sitemap/robots for comparison.

## Step 1 — Pull history (passive)

| Source | Endpoint |
|---|---|
| Wayback CDX | `https://web.archive.org/cdx/search/cdx?url=<host>/*&output=json&collapse=urlkey&limit=5000` |
| URLScan | `https://urlscan.io/api/v1/search/?q=domain:<host>` |
| CT logs | `https://crt.sh/?q=%25.<root>&output=json` |
| Search cache | `web_search` for `site:<host>` plus rare paths |
| Organization repos | only the org's own public repositories |

Deduplicate URLs, strip tracking parameters, keep in-scope hosts only.

## Step 2 — Extract

- Paths and file types (`.aspx`, `.php`, `.json`, `.zip`, `.bak`).
- Query parameter names.
- Old subdomains and third-party hosts.
- API versions (`/v1`, `/api/old`).
- Admin/upload/debug paths.

## Step 3 — Verify current state (read-only)

For each candidate:
- `HEAD`, then a small `GET` if needed; 5s timeout.
- Classify: `200` live, `401/403` protected, `301/302` redirect (check scope),
  `404` gone, `000` unreachable.
- Compare with current site structure: removed-but-live is the interesting case.

## Step 4 — Analyze (report only)

- Forgotten endpoints still reachable.
- Old admin/upload surfaces.
- Legacy parameters no longer used by the UI.
- Subdomains resolving but not linked.
- Archived pages containing version/build info (do not copy bodies).

Never treat an archived page as proof of current exposure; only the live check counts.

## Step 5 — Register

- `insert_assets` for live endpoints.
- Keep a separate "archived-only / dead" list.

## Evidence table

| URL | Source | First seen | Current status | Content-Type | Note |
|---|---|---|---|---|---|

## Pitfalls

- Fetching archived bodies with secrets/PII.
- Reporting dead URLs as findings.
- Following archive links off-scope.
- Ignoring redirects to a different (possibly out-of-scope) host.
- Using archive snapshots to bypass a login wall.

## Output

- Live historical endpoints vs. dead.
- Parameter name discoveries.
- Hand-offs to `content-discovery` and `exposure-recon`.

## Checklist

- [ ] Only in-scope hosts verified.
- [ ] No archived bodies/secrets copied.
- [ ] Live vs archived-only separated.
- [ ] Out-of-scope redirects not followed.
- [ ] Live endpoints registered.
