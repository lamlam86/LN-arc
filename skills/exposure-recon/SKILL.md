---
name: exposure-recon
description: Use when checking an authorized target for information exposed on the internet (leaked source and config files, backups, open storage, public keys, debug endpoints, archived pages).
---

# Internet Exposure Recon

With **authorization**, find information about a target that is **already publicly reachable** on the internet: source-control metadata, config and secret files, backups and dumps, open object storage, API documentation, debug endpoints, and archive/indexed copies of removed content.

This is **attack-surface discovery only**. It is not vulnerability exploitation and not credential abuse.

---

## Boundaries and Prohibitions (Required Reading; Violations Exceed Scope)

| Area | Allowed | Prohibited |
|---|---|---|
| **Objective** | Detect publicly reachable files, listings, docs, and metadata | Exploiting, modifying, or deleting target state |
| **Requests** | Read-only `GET`/`HEAD` at a low rate | POST/PUT/DELETE, brute force, fuzzing for vulns |
| **Authentication** | Anonymous requests only | Logging in, bypassing auth, reusing discovered credentials |
| **Secrets found** | Record the location and redact the value | Reading the full value, using it, or exfiltrating data |
| **Third parties** | The authorized target and its in-scope assets | People, unrelated orgs, breach/paste/dark-web dumps |

Rules:
1. Confirm authorization and the exact in-scope hosts before the first request.
2. Stay anonymous. Never send a discovered key, cookie, or token in a later request.
3. Cap download size (a few KB per hit is enough to fingerprint it). Never bulk-download dumps or personal data.
4. Rate-limit and back off on 429/5xx. Stop on WAF blocks instead of evading them.
5. Report only; do not retain secret values, personal data, or full file bodies.

---

## What Counts as Exposure

| Category | Typical paths / signals |
|---|---|
| **VCS metadata** | `/.git/HEAD`, `/.git/config`, `/.svn/entries`, `/.hg/`, `/.bzr/` |
| **Env / config / secrets** | `/.env`, `/.env.local`, `/config.json`, `/config.yml`, `/docker-compose.yml`, `/web.config`, `/wp-config.php`, `/.npmrc`, `/.aws/credentials`, `/id_rsa`, `*.pem`, `*.p12`, `*.jks` |
| **Backups / dumps / logs** | `*.bak`, `*.old`, `*.orig`, `*.zip`, `*.tar.gz`, `*.sql`, `*.dump`, `*.log`, `.DS_Store`, `Thumbs.db`, `*~` |
| **Source maps / debug** | `*.js.map`, `/actuator`, `/actuator/env`, `/actuator/heapdump`, `/debug/pprof/`, `/phpinfo.php`, `/server-status`, `/metrics`, `/trace` |
| **API documentation** | `/swagger-ui/`, `/swagger-ui.html`, `/v3/api-docs`, `/openapi.json`, `/api-docs`, `/graphql` (introspection), `/redoc` |
| **Open storage / dashboards** | S3/GCS/Azure Blob listings, Firebase RTDB, Elasticsearch/OpenSearch, Kibana, MinIO, CouchDB `/_all_dbs`, Jenkins, Grafana, Prometheus |
| **Metadata files** | `/robots.txt`, `/sitemap.xml`, `/.well-known/security.txt`, `/crossdomain.xml`, `/clientaccesspolicy.xml` |
| **Client bundles** | Hardcoded endpoints, API base URLs, and key **locations** in JS (report path only, redact value) |
| **Archived copies** | Wayback Machine, URLScan, certificate-transparency subdomains (passive lookups only) |

---

## Method

1. **Scope and baseline.** Record the authorized base URL(s). Fetch the site root and one random 404-like path to learn the "not found" signature (status, size, body) — many SPAs return 200 for everything.
2. **Probe candidate paths** with a small curated list (see `scripts/exposure_probe.py`). Prefer a few high-signal paths over large wordlists.
3. **Classify each response**:
   - `HIT` — status 200 and the body matches the expected signature (e.g. `.git/HEAD` starts with `ref: refs/`).
   - `PROTECTED` — 401/403: do not attempt to bypass.
   - `FALLBACK` — 200 but identical to the SPA/404 signature: not an exposure.
4. **Fingerprint, do not exfiltrate.** Record URL, status, content-type, byte count, and a short signature label. Never store the file body or secret value.
5. **Cloud storage.** Check listing endpoints read-only. If access is denied or the bucket is private, stop — do not enumerate object names.
6. **Archives.** Use passive archive/CT sources to find old or forgotten hosts and files; still apply the same read-only rules.
7. **Report** each finding with impact and remediation: remove the file, block the path, rotate any secret (never display it), restrict bucket permissions.

---

## Evidence Template

```
Finding:   Exposed <artifact type>
URL:       https://<host>/<path>
Status:    200  Content-Type: <type>  Size: <bytes>
Signature: <why it is a real match, no secret value>
Impact:    <what an anonymous visitor could learn>
Remediation: remove/block the path; rotate affected credentials; restrict storage
```

---

## Verification Checklist

- [ ] Authorization and in-scope hosts confirmed.
- [ ] Baseline 404/SPA signature captured; hits compared against it.
- [ ] No authentication attempted, no bypass, no POST/PUT/DELETE.
- [ ] Request rate limited; stopped on block pages.
- [ ] No secret value or personal data stored in notes or reports.
- [ ] Every finding has URL, evidence signature, impact, and remediation.
