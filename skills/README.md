# Recon skills

Skills shipped with this build. Each directory contains a `SKILL.md`; the app
loads them per agent according to `agent_skill_visibility`.

| Skill | Use for |
|---|---|
| `api-recon` | Frontend API reconnaissance: routes, endpoints, parameters, UI triggers. |
| `subdomain-enum` | Passive subdomain discovery (DNS, SANs, CT, crawl links). |
| `dns-recon` | DNS records: A/AAAA, CNAME, MX, NS, TXT/SPF/DMARC, reverse DNS. |
| `tls-cert-recon` | Certificates, SANs, expiry, protocol and chain inspection. |
| `http-fingerprint` | Headers, redirects, framework markers, favicon, robots/sitemap. |
| `content-discovery` | Safe curated path/file enumeration; baseline-404 aware. |
| `port-service-recon` | Light port/service checks on in-scope IPs. |
| `js-endpoint-recon` | Extract endpoints/params/secret locations from JS bundles. |
| `traffic-analysis` | Summarize captured traffic into an endpoint inventory (no replay). |
| `archive-recon` | Historical hosts/paths via Wayback, URLScan, CT; verify current state. |
| `cloud-storage-recon` | Public listing checks for owned S3/GCS/Azure/Firebase storage. |
| `visual-recon` | Playwright screenshots and visual inventory of in-scope hosts. |
| `scope-coverage` | Scope definition, asset registration, untested-asset coverage. |
| `exposure-recon` | Publicly reachable files/config/backups/debug surfaces. |
| `exposure-assessment` | Severity/exploitability assessment of observed exposures. |
| `self-exposure-audit` | Own-domain document exposure audit (metadata only). |
| `recon-report` | Compile a Markdown report; publish it to Tasks → Reports. |
| `playwright-cli` | Browser automation primitives. |
| `scopesentry` | ScopeSentry MCP platform management. |

## Conventions

- Read-only, authorized scope only; no exploitation, brute force, or credential use.
- Rate-limit requests; stop on WAF/429.
- Redact secrets and personal data; report location/type only.
- Register discovered assets with `insert_assets` and record facts for coverage.
