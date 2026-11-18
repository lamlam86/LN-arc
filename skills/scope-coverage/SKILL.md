---
name: scope-coverage
description: Use when planning, registering and tracking reconnaissance coverage for a task — writing scope, recording facts, finding untested assets and producing a coverage plan.
---

# Scope & Coverage Management (detailed)

## Objective

Keep reconnaissance inside its authorization boundary and make coverage
measurable and reproducible.

## Inputs

- Task goal, description, constraints.
- `graph_overview`, `list_assets`, `list_untested_assets`.
- Existing scope rows.

## Step 1 — Read before writing

1. `graph_overview` — current asset counts, frontier, coverage.
2. `list_assets` — what is already registered (don't duplicate).
3. Read the task's goal and constraints from the prompt.

## Step 2 — Define scope

- `add_task_scope` for domains, IPs, CIDRs; include a `reason` for each.
- `set_constraints`:
  - allow: read-only HTTP, DNS, low-rate port checks, passive OSINT;
  - deny: exploitation, brute force, high-rate scanning, out-of-scope hosts.
- Never add a host the user did not authorize.

## Step 3 — Plan coverage by asset type

| Asset type | Minimum pass | Skill |
|---|---|---|
| subdomain | DNS + HTTP status + title | `subdomain-enum`, `http-fingerprint` |
| service | port/protocol + TLS | `port-service-recon`, `tls-cert-recon` |
| URL/path | status + type + title | `content-discovery` |
| API endpoint | method + params + auth | `api-recon`, `traffic-analysis` |
| traffic | endpoint/param inventory | `traffic-analysis` |
| exposure | public file/config checks | `exposure-recon` |
| storage | public listing check | `cloud-storage-recon` |

## Step 4 — Execute and record

After each pass:
- `insert_assets` for discoveries,
- `record_fact` with: what was checked, method, result, limits.
- Mark the asset tested only when probed **and** a fact is recorded.

## Step 5 — Close gaps

- `list_untested_assets` → pick the smallest skill for each gap.
- Distinguish `not reachable` from `not tested`.
- Do not mark a child asset tested because the parent was.

## Step 6 — Report coverage

- total / tested / untested / out-of-scope, per type;
- blockers (rate limit, WAF, auth wall);
- recommended next passes;
- hand to `recon-report` (coverage section).

## Anti-patterns

- Testing outside the written scope.
- Registering assets without `company_id`/task attribution.
- Coverage inflated by counting requests, not assets.
- Leaving duplicate assets (case/trailing dot) that split coverage.
- Marking "no response" as tested.

## Checklist

- [ ] Scope written before probing.
- [ ] Deny constraints respected.
- [ ] Every tested asset has a recorded fact.
- [ ] Duplicates merged; attribution set.
- [ ] Untested/blocked assets listed explicitly.
