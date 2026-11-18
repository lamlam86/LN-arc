---
name: exposure-assessment
description: Use when judging how dangerous a recon finding or public exposure is (severity, who could reach it, what data it reveals, remediation priority) without exploiting it.
---

# Exposure Assessment

Turn observed recon facts into a **risk judgement**: how exposed it is, what class of data it reveals, how much damage that could cause, and what to fix first.

This skill produces **assessment and remediation**, not exploitation. It never tries to break in, use a found credential, or prove impact by attacking.

## Hard Boundaries

| Allowed | Prohibited |
|---|---|
| Rate severity from what was already observed | Exploiting, fuzzing for vulnerabilities, payloads |
| Say whether something is publicly readable | Logging in, bypassing auth, using discovered keys/tokens |
| Describe the **class** of data at risk | Reproducing secret values, PII, or file bodies |
| Recommend remediation and verification steps | Downloading dumps, enumerating private storage |
| State confidence and limits of the evidence | Claiming "exploitable" without evidence |

If real exploit validation is requested, stop: that is a separate authorized engagement, outside recon-only scope.

## Inputs

Use only evidence that already exists in the task:
- `exposure-recon` results (URL, status, content-type, size, signature).
- `api-recon` results (public endpoints, auth requirements, parameters).
- `graph_overview`, `list_untested_assets`, traffic references (`traffic_search` hashes).
- Activity/transcripts and files under the task working directory.

If a finding has no evidence, mark it `unverified` and rate it conservatively — do not invent reachability.

## Assessment Dimensions

For each finding, record:

1. **Reachability** — anonymous / authenticated / internal only / unknown.
2. **Confirmation** — confirmed (signature matched) / probable / unverified.
3. **Data class** — source code, credentials, customer PII, internal config, logs, metadata, public docs.
4. **Sensitivity** — how damaging disclosure would be (secret rotation cost, regulatory impact).
5. **Blast radius** — one host, a shared platform, or a whole environment.
6. **Exploitability (conceptual)** — whether an anonymous visitor can *read/reach it today*; not a PoC.
7. **Remediation** — remove/block, rotate, restrict, monitor.

## Severity Rubric

Use the bundled scorer, or this matrix by hand:

| Severity | Typical case |
|---|---|
| **Critical** | Anonymous read access to credentials, private keys, or a full customer data dump |
| **High** | Anonymous read access to source code, backups, internal config, or a writable public store |
| **Medium** | Debug/metrics/admin surface reachable anonymously, directory listing, or sensitive metadata without secrets |
| **Low** | Public docs/API schema that only increases reconnaissance convenience |
| **Info** | Presence of a file with no sensitive content (e.g. `robots.txt`) |

Modifiers: confirmed + public raises; auth required lowers; unknown reachability lowers confidence (not severity of the underlying issue). Never rate a guess as Critical.

## Output Per Finding

```
Finding:       <short title>
Severity:      Critical | High | Medium | Low | Info   (confidence: high/medium/low)
Reachability:  anonymous | authenticated | internal | unknown
Evidence:      <URL, status, content-type, signature — no secret value>
Data at risk:  <class only: source | credentials | PII | config | metadata | docs>
Why it matters:<what an anonymous visitor could learn or do with that data class>
Limits:        <what was NOT verified; no exploitation attempted>
Remediation:   <remove/block path, rotate secret, restrict bucket/role, add monitoring>
Priority:      <1 (now) … 5 (backlog)>
```

## Report Add-On

When writing `recon-report.md`, add an **Assessment** section (after "Exposed information") containing:
- A severity summary table: `Critical / High / Medium / Low / Info` counts.
- The top 3 risks with one-line rationale.
- A remediation order (what to fix first and why).
- An explicit statement: *"No exploitation was attempted; severity reflects reachability and data class only."*

## Scorer

```bash
python scripts/assess.py --input findings.json --out assessment.md
```

Start from `scripts/findings.example.json`; schema in `scripts/README.md`. The scorer is deterministic and conservative: unverified or authenticated findings cannot reach Critical.

## Final Check

- [ ] Every verdict cites observed evidence.
- [ ] No secret value, PII, or raw body in the report.
- [ ] "Exploitable" is only used for confirmed anonymous *read* access — never for an untested attack.
- [ ] Remediation and priority are actionable.
- [ ] Limits of validation are stated.
