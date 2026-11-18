---
name: port-service-recon
description: Use when doing light TCP port and service reconnaissance on authorized IPs (common web/remote ports, low rate) to map reachable services and their protocols.
---

# Light Port / Service Recon (detailed)

## Objective

Map reachable services on authorized IPs using a small, agreed port set — not a
full port scan.

## Inputs

- In-scope IPs resolved from authorized hosts.
- Agreed port set (default below) and rate limit.
- Permission for TCP connect checks.

## Default port set

`80, 443, 8080, 8443, 8000, 8888, 3000, 5000, 9000, 9443, 22, 21, 25, 587, 3389, 1433, 3306, 5432, 6379, 9200, 27017`

Start with web ports; add remote/database ports only if the engagement allows.
Never expand to `1-65535` without explicit permission.

## Step 1 — Verify the IPs

- Resolve each in-scope host; keep the host→IP mapping.
- Exclude shared/CDN IPs where a port check would not represent the target.
- Note IPv6 addresses separately.

## Step 2 — TCP connect checks

Portable options:
- PowerShell: `Test-NetConnection -ComputerName <ip> -Port <port> -InformationLevel Quiet`
- Bash: `timeout 2 bash -c "</dev/tcp/<ip>/<port>" && echo open`
- `nc -z -w 2 <ip> <port>`

Rules: one attempt per port, 2–3s timeout, delay between hosts, stop on filtering
or IDS-like responses.

## Step 3 — Characterize open services (minimal)

| Port type | Action | Record |
|---|---|---|
| HTTP | `HEAD`/`GET` with correct `Host` | status, `Server`, title |
| HTTPS | TLS handshake | issuer, SAN, expiry |
| SSH/FTP/SMTP | banner only (first line) | protocol/version string |
| Databases/caches | **do not interact** | open/closed only |

Do not attempt default credentials, protocol exploitation, or data access.

## Step 4 — Analyze (report only)

- Unexpected admin/database/cache ports on a public IP → hygiene finding.
- Alternate HTTPS ports and host-header-dependent backends.
- Port 80 with no HTTPS redirect.
- Same service on multiple IPs (load balancer).
- Closed/filtered ports: report "not reachable", never "secure".

## Step 5 — Register

- `insert_assets`: `service` rows (host, port, protocol, service type), `ip` rows.
- Record the exact port list, timing and result per port.
- Hand HTTP services to `http-fingerprint`; TLS to `tls-cert-recon`.

## Evidence table

| IP | Host | Port | State | Protocol | Service/banner | Note |
|---|---|---|---|---|---|---|

## Pitfalls

- Full-range scanning by accident.
- Aggressive retries triggering IDS.
- Interacting with databases/caches.
- Treating a CDN IP as the origin.
- Reporting filtered ports as closed/secure.

## Output

- Port matrix per IP with open/closed/filtered.
- Service notes and hand-offs.
- Explicit port list and rate used.

## Checklist

- [ ] Only in-scope IPs and agreed ports.
- [ ] Low rate, short timeouts, stopped on filtering.
- [ ] No exploitation/default credentials.
- [ ] Services registered; port list recorded.
