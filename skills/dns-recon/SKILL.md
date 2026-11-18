---
name: dns-recon
description: Use when recording an authorized domain's DNS footprint (A/AAAA, CNAME, MX, NS, TXT/SPF/DMARC, SOA, PTR) as read-only reconnaissance and mail-hygiene observations.
---

# DNS Recon (detailed)

## Objective

Document the DNS footprint of an authorized domain and flag hygiene or
infrastructure observations — without zone transfers or brute force.

## Inputs

- Authorized domain(s), task scope.
- Optional: authoritative nameservers discovered from `NS`/`SOA`.

## Step 1 — Enumerate records

Run each against the domain (PowerShell `Resolve-DnsName`, `nslookup`, or `dig`):

| Type | Why | Record |
|---|---|---|
| `A` / `AAAA` | hosting, dual-stack | addresses, TTL |
| `CNAME` | third-party services, takeover candidates | chain target |
| `MX` | mail providers | host + preference (no personal data) |
| `NS` | delegation/provider | nameservers |
| `SOA` | primary NS, serial | value |
| `TXT` | SPF, site verification | mechanism only |
| `TXT _dmarc` | DMARC policy | `p=`, `rua` host only |
| `PTR` | reverse DNS for resolved IPs | name |

Query both the system resolver and the authoritative NS; note disagreements
(propagation, stale records, split-horizon).

## Step 2 — Analyze (report, do not act)

- **SPF**: mechanism present? multiple records? `~all` vs `-all`.
- **DMARC**: policy `none`/`quarantine`/`reject`; alignment obvious?
- **CNAME**: points to a service that may be unclaimed → **potential** takeover;
  do not claim it without claiming the exact dangling target.
- **NS**: single provider? unusual TLD? delegation mismatch?
- **SOA serial** vs. current time (stale zone).
- **Wildcard**: `*.domain` resolves? Note it before subdomain work.
- **TTL** anomalies and round-robin behaviour.
- **IPv6** published but unreachable.
- **Private/RFC1918** addresses in public DNS.

## Step 3 — Scope and register

- `insert_assets` for subdomains/IPs/services found through DNS.
- Add any newly discovered parent/child domains only if they are in scope.

## Evidence table

| Name | Type | Value | TTL | Resolver | Note |
|---|---|---|---|---|---|

Keep TXT values as mechanisms; never paste a full DKIM/verification secret.

## Pitfalls

- Attempting `AXFR` without explicit permission (treat as intrusive).
- Recording personal email addresses from SOA/TXT.
- Confusing "no record" with "secure".
- Calling a CNAME "takeover" without evidence the target is unclaimed.

## Output

- Record tables per type.
- A short "mail/DNS hygiene" paragraph with observations.
- A "potential risks" list, clearly separated from confirmed facts.

## Checklist

- [ ] Only in-scope names queried.
- [ ] No AXFR unless explicitly authorized.
- [ ] TXT/SPF/DMARC reported as mechanisms, values minimized.
- [ ] Potential takeover labelled "potential".
- [ ] New assets registered.
