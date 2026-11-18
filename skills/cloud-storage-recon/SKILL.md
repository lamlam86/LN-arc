---
name: cloud-storage-recon
description: Use when checking whether an authorized organization's cloud storage (S3, GCS, Azure Blob, Firebase) referenced by in-scope assets is publicly listable, without downloading objects or testing write access.
---

# Cloud Storage Recon (detailed)

## Objective

Determine whether storage owned by the organization, or referenced by in-scope
assets, allows anonymous listing — and report it. Read-only.

## Inputs

- In-scope domains, JS bundles, traffic, docs.
- Permission to issue read-only storage requests.
- No credentials and no signed URLs.

## Step 1 — Discover storage references

| Source | Look for |
|---|---|
| DNS | CNAME to `*.s3.amazonaws.com`, `storage.googleapis.com`, `*.blob.core.windows.net`, `*.firebaseio.com`, `*.r2.cloudflarestorage.com` |
| JS bundles | bucket URLs, `firebaseConfig`, upload endpoints |
| HTML/sitemap | direct object URLs |
| Traffic | upload/download hosts and signed-URL patterns |
| Public docs | storage references |
| Config exposure | bucket names from `exposure-recon` (name only) |

Only check buckets belonging to the organization or clearly referenced by its assets.

## Step 2 — Read-only checks

| Provider | Listing request |
|---|---|
| AWS S3 | `https://<bucket>.s3.amazonaws.com/?list-type=2&max-keys=5` |
| GCS | `https://storage.googleapis.com/storage/v1/b/<bucket>/o?maxResults=5` |
| Azure Blob | `https://<account>.blob.core.windows.net/<container>?restype=container&comp=list&maxresults=5` |
| Firebase RTDB | `https://<project>.firebaseio.com/.json?shallow=true` |
| Cloudflare R2 (S3 API) | `https://<account>.r2.cloudflarestorage.com/<bucket>?list-type=2&max-keys=5` |

Interpretation:

- `200` + XML/JSON listing → **public listing**; report, do not page through.
- `403 AccessDenied` / `401` → private (good).
- `404` → wrong name/region or not a bucket.
- `200` single object → object public, not listing.
- Redirect to a login/console → private/management, stop.

## Step 3 — Do not cross these lines

- No object downloads (a HEAD/size check is enough).
- No write/delete/ACL tests.
- No bucket-name brute force beyond names already observed.
- No signed-URL guessing or credential use.
- Stop at the first `403`; do not enumerate further.

## Step 4 — Analyze (report only)

- Public listing exposes object names → structure and possible sensitive filenames.
- Public write is **not** tested; mark "unverified".
- Link bucket → in-scope host → owner.
- Note stale/forgotten buckets no longer used by the app.

## Step 5 — Register

- `insert_assets` for storage endpoints/services.
- Feed `exposure-assessment` for severity.

## Evidence table

| Provider | Bucket/container | URL | Status | Listing | Objects seen | Note |
|---|---|---|---|---|---|---|

## Pitfalls

- Downloading a sample object "to confirm".
- Testing write access.
- Enumerating private bucket names.
- Confusing an object URL with a listing.
- Ignoring region-specific endpoints.

## Checklist

- [ ] Only owned/referenced buckets checked.
- [ ] No downloads, no write tests, no brute force.
- [ ] Private buckets marked and left alone.
- [ ] Findings passed to assessment/report.
