---
name: visual-recon
description: Use when capturing screenshots and a visual inventory of authorized web hosts with Playwright (pages, login walls, error/default pages) for human review.
---

# Visual Recon (detailed)

## Objective

Capture what each in-scope web asset actually presents, for inventory and review.

## Inputs

- In-scope URLs.
- `playwright-cli` skill or browser MCP.
- A task working directory for screenshots.

## Step 1 — Curated visit list

- root (`/`)
- login/SSO entry (no login attempt)
- admin/dashboard (expect a wall; do not authenticate)
- docs/help
- sitemap/robots
- a random 404 path
- any host with a different title/tech from fingerprinting

## Step 2 — Capture

For each URL:
1. `open` (or reuse the tab), `goto`, wait for load and network settle.
2. Note the final URL after redirects.
3. Full-page `screenshot`.
4. Snapshot the accessibility tree / title.
5. Record visible tech, language, branding, CDN/widgets.
6. For SPAs, wait for the route to render; note if it stays blank.

## Step 3 — What to look for

| Signal | Meaning |
|---|---|
| Title/branding mismatch | vhost points at another app |
| Default server/CMS page | unconfigured or forgotten host |
| Verbose error page | debug mode / stack trace |
| Directory listing | content exposure |
| Login wall | auth surface (record, do not test) |
| CAPTCHA/WAF page | blocking; record and stop |
| Mixed content / HTTP login | hygiene issue |
| Mobile layout differences | separate surface |

## Step 4 — Evidence handling

- Store screenshots under the task/session directory.
- Reference: URL, timestamp, screenshot path, final URL, title.
- Do not OCR or transcribe personal data.
- Do not publish screenshots outside the engagement.

## Step 5 — Register

- `insert_assets` for hosts/paths discovered visually.
- Add notes to services (title, tech, wall type).

## Pitfalls

- Submitting forms or logging in.
- Bypassing consent/CAPTCHA walls.
- Screenshotting personal data.
- Treating a visual default page as a vulnerability.
- Missing the post-redirect host (scope check).

## Output

| URL | Final URL | Title | Wall/tech observed | Screenshot | Note |
|---|---|---|---|---|---|

## Checklist

- [ ] Only in-scope URLs visited.
- [ ] No form submissions or auth attempts.
- [ ] Screenshots stored with URL/time references.
- [ ] Findings labelled visual observation.
- [ ] New assets registered.
