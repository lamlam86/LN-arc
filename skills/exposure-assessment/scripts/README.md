# exposure-assessment scorer

`assess.py` scores findings that were **already observed** during recon. It does
not probe anything and never validates exploitability.

```bash
python scripts/assess.py --input findings.json --out assessment.md
```

## Input

```json
{
  "target": "example.com",
  "findings": [
    {
      "id": "F1",
      "title": "Exposed .git/HEAD",
      "category": "vcs",
      "url": "https://example.com/.git/HEAD",
      "reachability": "anonymous",
      "confirmation": "confirmed",
      "data_class": "source",
      "blast_radius": "host",
      "evidence": "HTTP 200, body starts with 'ref: refs/'",
      "impact": "Repository structure may be recoverable by an anonymous visitor.",
      "remediation": "Block /.git/ and redeploy without VCS metadata.",
      "limits": "History not downloaded; no exploit attempted."
    }
  ]
}
```

| Field | Values |
|---|---|
| `category` | `secrets`, `backup`, `storage`, `vcs`, `debug`, `api-docs`, `metadata`, `other` |
| `reachability` | `anonymous`, `authenticated`, `internal`, `unknown` |
| `confirmation` | `confirmed`, `probable`, `unverified` |
| `data_class` | `credentials`, `pii`, `config`, `source`, `docs`, `metadata`, `none` |
| `blast_radius` | `environment`, `platform`, `host`, `unknown` |

## Scoring rules

- Base score by category, adjusted by data class, reachability, confirmation, and blast radius.
- **Conservative caps:** Critical requires confirmed anonymous access to
  credentials or PII; all other findings top out at High. Unverified findings
  cannot exceed Medium, and `api-docs`/`metadata` are capped at Medium.
- Severity: `>=85 Critical`, `>=70 High`, `>=50 Medium`, `>=25 Low`, else `Info`.
- Priority: Critical/High = 1, Medium = 2, Low = 3, Info = 5.

The score is a triage aid, not CVSS. Report the evidence and limits, not just the number.
