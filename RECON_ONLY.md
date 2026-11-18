# Recon-only mode

This fork removes the exploitation / vulnerability workflow from ARTEX and keeps
reconnaissance capabilities only.

## Removed

- Agent tools: `report_finding`, `list_findings`, `list_task_findings`,
  `update_finding_report`, `bind_finding_traffic`, `get_finding_traffic`,
  and all retest tools.
- Agents and prompts: `reporter`, `retester`; the `pentest` prompt was rewritten
  as a reconnaissance-only prompt. Worker / planner / main-agent / goals prompts
  no longer instruct exploitation, PoC creation, or vulnerability reporting.
- Backend packages: `report/`, `evidence/`, `agent/finding_*.go`,
  `agent/retester.go`, `db/finding_*.go`, `db/findings.go`,
  `server/finding_*.go`, `server/findings_groups.go`.
- API routes: all `/api/exploration/findings/*`, `/api/report`, and retest routes.
- Web UI: Findings list/detail, task Findings/Retests/Report tabs, dashboard
  findings cards, retest and traffic-evidence dialogs.
- Database schema: `findings`, `finding_retests`, `finding_traffic_bindings`,
  `traffic_evidence_snapshots`, and the `on_finding` / `finding_message`
  trigger columns are no longer created for new installations.
- Interception judge policy: exploitation payloads, credential attacks, payload
  deployment, destructive mutations, and DoS are now DENY. Read-only recon
  (DNS, HTTP GET/HEAD, service probing, fingerprinting, crawling, safe
  enumeration, traffic capture) is ALLOW.

## Kept

- Asset graph: root domains, subdomains, IPs, apps, services, endpoints.
- DNS enrichment (A/AAAA/CNAME) and HTTP probing.
- Traffic recording proxy and `traffic_search` / `traffic_get` / `traffic_blob`.
- The `api-recon` skill (static bundle harvesting + runtime API discovery).
- Playwright MCP / CLI browser automation.
- ScopeSentry asset synchronization.
- Coverage tools: `add_task_scope`, `list_untested_assets`, `graph_overview`.
- Custom tools, MCP servers, skills, Bash execution, WebFetch.

## Database migration

On startup, `MigrateReconOnly` deletes the retired `reporter` / `retester`
agents, finding triggers, and finding-only tool rows from an existing database.
Historical findings tables are **not dropped automatically** to avoid destroying
data. To remove them manually on a development database:

```sql
DROP TABLE IF EXISTS finding_traffic_bindings;
DROP TABLE IF EXISTS traffic_evidence_snapshots;
DROP TABLE IF EXISTS finding_retests;
DROP TABLE IF EXISTS findings;
```

## Rebuild

```bash
# frontend
cd web && npm run build:static && cd ..
rsync -a --delete web/out/ server/webui/dist/

# backend (static, embedded UI)
CGO_ENABLED=0 go build -tags embedui -ldflags="-s -w" -o artex ./cmd/artex
```

## Notes

- `web/src/lib/api.ts`, `web/src/lib/types.ts`, and `src/lib/mock/` still contain
  some unused finding/retest type definitions and mock demo data. They are not
  referenced by any rendered page or backend route. Remove them if you want a
  fully clean tree.
- The notification subsystem remains, but nothing produces finding events after
  this change; it can be removed in a later pass if notifications are not needed.
