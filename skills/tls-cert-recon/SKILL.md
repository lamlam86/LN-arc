---
name: tls-cert-recon
description: Use when inspecting TLS certificates, SANs, expiry, protocol versions and chain of authorized hosts to inventory names and record operational and hygiene observations.
---

# TLS / Certificate Recon (detailed)

## Objective

Turn each TLS endpoint into inventory data: names (SANs), issuer, expiry, chain,
protocol and hostname behaviour.

## Inputs

- In-scope hosts/ports (usually 443, sometimes 8443/4545).
- Existing assets to avoid duplicate names.
- Permission to perform TLS handshakes (standard read-only recon).

## Step 1 — Collect

For each host:

```bash
openssl s_client -connect host:443 -servername host </dev/null \
  | openssl x509 -noout -subject -issuer -dates -ext subjectAltName
openssl s_client -connect host:443 -servername host </dev/null 2>/dev/null | grep -E "Protocol|Cipher"
```

Record:
- subject, issuer, serial, `notBefore` / `notAfter`, days remaining;
- SAN list (dedupe; strip wildcard for scope checks);
- chain: leaf + intermediates, verification result;
- negotiated protocol/cipher;
- port 80 → 443 redirect;
- hostname mismatch (cert valid for another name).

## Step 2 — Host-header / vhost behaviour

For shared infrastructure, compare:
- correct `Host`/SNI vs. wrong `Host` on the same IP/port;
- default backend responses (F5/IIS/nginx default pages);
- whether routing follows `Host` rather than SNI.

Record differences; do not attempt to bypass access controls.

## Step 3 — Analyze (report only)

| Observation | Meaning | Severity |
|---|---|---|
| Expiry < 30 days | operational risk | medium (ops) |
| Expired / not yet valid | outage risk | high (ops) |
| Hostname mismatch | misconfiguration | low–medium |
| Weak protocol (TLS 1.0/1.1) | hygiene | low–medium |
| Wildcard covering many hosts | scope note | info |
| Self-signed / internal CA | hygiene | low |
| SAN with out-of-scope names | discovery lead | info |

Do not test for TLS vulnerabilities (Heartbleed, downgrade, etc.) unless the
engagement explicitly includes it; this skill records configuration only.

## Step 4 — Register

- `insert_assets` for SAN-derived subdomains and services.
- Add TLS details to the service note (issuer, expiry, protocol).
- Out-of-scope SANs: record as "seen, not probed".

## Evidence table

| Host | Port | Issuer | Expires | Days | Protocol | SAN count | Chain | Note |
|---|---|---|---|---|---|---|---|---|

## Pitfalls

- Treating certificate SANs as in-scope automatically.
- Confusing "expiring soon" with a security vulnerability.
- Probing out-of-scope SANs.
- Missing hosts that serve different certs on different ports.

## Output

- Certificate table, SAN-derived host list, operational expiry list.
- A clear separation between security observations and availability risks.

## Checklist

- [ ] Handshakes only against in-scope hosts.
- [ ] SANs classified in/out of scope.
- [ ] Expiry, protocol, chain recorded.
- [ ] New names registered; out-of-scope names not probed.
