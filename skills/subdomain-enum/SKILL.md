---
name: subdomain-enum
description: Use when mapping the subdomain attack surface of an authorized domain using passive DNS, certificate SANs, CT logs and crawl links, without brute force.
---

# Subdomain Enumeration (passive, detailed)

## Objective

Produce a deduplicated, verified list of subdomains for an authorized root domain,
with IPs, CNAMEs, HTTP status, title and TLS issuer, registered as assets.

## Inputs

- Authorized root domain(s) and any known hosts.
- Task scope/constraints (`graph_overview`, `add_task_scope`).
- Existing assets (`list_assets`) to avoid duplicate work.

## Step 1 — Collect candidates (passive only)

1. **DNS basics**
   - `Resolve-DnsName <root> -Type A,AAAA,NS,MX,TXT` (PowerShell), `dig`, or `nslookup`.
   - Follow CNAME chains; note the final target.
2. **Certificate SANs**
   - For every live host: `openssl s_client -connect host:443 -servername host </dev/null | openssl x509 -noout -text`.
   - Every SAN under the root is a candidate; SANs outside the root are "seen, out of scope".
3. **Certificate Transparency**
   - `https://crt.sh/?q=%25.<root>&output=json` — dedupe `name_value`, split on newlines, keep `*.<root>` → strip wildcard.
   - Alternative: `https://api.certspotter.com/v1/issuances?domain=<root>&include_subdomains=true&expand=dns_names` if available.
4. **Site metadata**
   - `robots.txt`, `sitemap.xml`, `/Pages/sitemap.aspx`, RSS feeds, `security.txt`.
   - Crawl same-origin HTML links (depth 1–2) for absolute URLs and hostnames.
5. **Passive search**
   - `web_search` for `site:<root>` and `"<root>" -site:<root>`.
   - Public code/docs owned by the organization only.
6. **Third-party datasets** (SecurityTrails, VirusTotal, Shodan) only if the engagement permits and an API key is provided.

> Never run a DNS wordlist or wildcard brute force. If a wildcard `*.root` resolves, note it and stop treating random resolutions as findings.

## Step 2 — Verify each candidate

For every unique hostname:

| Check | Command / tool | Record |
|---|---|---|
| A / AAAA | `Resolve-DnsName` / `dig` | addresses, IPv6 reachable? |
| CNAME | same | target, third-party service |
| HTTP | `HEAD` then small `GET`, 5s timeout | status, redirect `Location`, `Server`, title |
| HTTPS | TLS handshake | issuer, expiry, SAN count |
| Scope | compare to task scope | in/out |

Classify: `live`, `redirect-only`, `protected (401/403)`, `parked`, `dead`,
`out-of-scope`. Do not probe an out-of-scope host even if it appears in a SAN.

## Step 3 — Register

`insert_assets` in one batch:
- `subdomain` for each host (domain field),
- `ip` for new addresses,
- `service` for `host:port` (protocol, service type, status),
- `endpoint` for verified URLs.

Attach the task's `company_id`; then `list_untested_assets` to hand new hosts to coverage.

## Evidence to record

host, source (DNS/SAN/CT/crawl/search), A/AAAA, CNAME, HTTP status, title,
TLS issuer/expiry, in-scope flag, timestamp. Keep the source so duplicates can be
reconciled later.

## Risk signals (report only)

- Wildcard DNS masking dead hosts.
- CNAME to an unclaimed third-party service → **potential** takeover candidate.
- Dev/staging/admin names reachable publicly.
- IPv6 published but unreachable.
- Hosts resolving to private RFC1918 addresses.

## Output format

| Host | IPs | CNAME | Status | Title | TLS issuer | Source | Scope |
|---|---|---|---|---|---|---|---|

Plus counts by source and by state, and an explicit note that no brute force was used.

## Pitfalls

- Counting `*.root` as a host.
- Treating DNS-only names as live services.
- Probing out-of-scope SANs.
- Registering duplicates with different casing/trailing dots.

## Checklist

- [ ] Passive sources only; public APIs rate-limited.
- [ ] Every host verified and classified.
- [ ] Out-of-scope names recorded but not probed.
- [ ] Assets registered with source and company/task attribution.
- [ ] No brute force, no wildcard scanning.
