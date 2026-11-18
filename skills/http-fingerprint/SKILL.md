---
name: http-fingerprint
description: Use when fingerprinting an authorized web service (headers, redirects, framework markers, favicon hash, robots/sitemap, error shape) before deeper URL and API reconnaissance.
---

# HTTP Fingerprinting (detailed)

## Objective

Establish what each in-scope web service is, with evidence, before enumerating it.

## Inputs

- Verified live hosts (from `subdomain-enum` / `tls-cert-recon`).
- A baseline "not found" response for SPA detection.

## Step 1 — Baseline

Request a random unlikely path, e.g. `/__recon_<random>__`. Record status, size,
content-type and body hash. Every later `200` must be compared against this
signature — many SPAs return `200` with the app shell for every path.

## Step 2 — Collect per service

| Area | Record |
|---|---|
| Status / redirects | codes, `Location`, HTTP→HTTPS chain |
| Response headers | `Server`, `X-Powered-By`, `Via`, `X-AspNet-Version`, CDN hints |
| Security headers | HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy (present/absent) |
| Cookies | name, `Secure`, `HttpOnly`, `SameSite`, path (never the value) |
| Body markers | `__VIEWSTATE`, generator meta, script paths, framework classes |
| Favicon | mmh3 hash (base64) for public hash lookup |
| Robots / sitemap | `robots.txt`, `sitemap.xml`, `/Pages/sitemap.aspx`, RSS |
| Well-known | `/.well-known/security.txt`, `/.well-known/change-password` |
| Error shape | 404/500 page shape (SPA fallback? stack trace?) — do not trigger deliberately |
| Title / language | `<title>`, `lang`, meta description |

## Step 3 — Identify the stack

Name server, framework, CMS, CDN/WAF and JS libraries. For each, state
`observed` (direct marker) or `inferred` (behaviour). Avoid guessing from a single
header.

## Step 4 — Host-header behaviour

Send `HEAD` with the correct `Host` and with a wrong `Host` to the same IP/port.
Record: same app, default site, 400/404, or a different application. Do not try to
bypass any access control.

## Step 5 — Register & hand off

- `insert_assets` for services/endpoints with status/title/technologies.
- Give the baseline signature to `content-discovery` and `exposure-recon`.
- Note the redirect map for `subdomain-enum`.

## Risk signals (report only)

- Version/build disclosure.
- Missing security headers (hygiene).
- Debug banners or verbose errors.
- Default server/CMS pages.
- Host-header-dependent backends.
- Cookies missing `Secure`/`HttpOnly`/`SameSite`.
- Mixed content / HTTP available for a login page.

## Pitfalls

- Treating the SPA shell as a real page.
- Following redirects off-scope.
- Calling a header "vulnerable" without a concrete impact.
- Copying cookie or token values into notes.

## Output table

| Host:port | Status | Server | Framework | CDN/WAF | Title | Baseline size | Notes |
|---|---|---|---|---|---|---|---|

## Checklist

- [ ] Baseline signature captured and reused.
- [ ] Headers/cookies recorded with flags only.
- [ ] Stack claims labelled observed/inferred.
- [ ] No auth attempts or error-triggering payloads.
- [ ] Services registered.
