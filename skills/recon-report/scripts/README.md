# recon-report renderer

`render_report.py` turns a JSON model into `recon-report.md`. Start from
`report-model.example.json`, fill it with **observed** data, then render:

```bash
python scripts/render_report.py \
  --input report-model.json \
  --out recon-report.md \
  --title "Recon report — example.com"
```

## Model

All fields are optional; missing sections render as `not collected`.

| Field | Type | Meaning |
|---|---|---|
| `task` | object | `id`, `name`, `status`, `started`, `finished` |
| `scope` | string[] | Authorized hosts/URLs |
| `constraints` | string[] | Rules, exclusions, rate limits |
| `summary` | string[] | Executive summary bullets |
| `goals` | object[] | `goal`, `status`, `evidence` |
| `assets` | object | Lists under `domains`, `subdomains`, `ips`, `services`, `technologies` |
| `assets.*[]` | string or object | Object form: `value`, `note`, `source` |
| `dns` | object[] | `name`, `type`, `value`, `note` |
| `endpoints` | object[] | `method`, `url`, `params`, `auth`, `source` |
| `parameters` | object[] | `name`, `location`, `methods`, `risk`, `why`, `evidence` |
| `auth` | object[] | `surface`, `endpoint`, `behaviour`, `note` |
| `coverage` | object | `total`, `tested`, `untested`, `untested_assets[]`, `note` |
| `exposures` | object[] | `severity`, `title`, `url`, `evidence`, `impact`, `remediation` |
| `google_dork` | object | `engine`, `queries[]` (`query`, `engine`, `results`, `in_scope`, `verification`, `status`, `note`), `findings[]` (`query`, `url`, `type`, `verification`, `status`, `note`), `notes[]` |
| `traffic` | object[] | `method`, `url`, `status`, `content_type`, `ref` |
| `timeline` | object[] | `time`, `event` |
| `assessment` | object | `note`, `risks[]` (`title`, `severity`, `status`, `exploitability`, `action`) |
| `priority_actions` | string[] | Ordered remediation steps |
| `gaps` | string[] | What was not covered |
| `methodology` | string[] | Tools, skills, rate, limitations |

## Safety

- Put only the **location/type** of a secret in `evidence`, never the value.
- Do not include raw request/response bodies or personal data.
- The renderer redacts common token patterns and private-key blocks, but it is a
  net, not a guarantee: review the output before delivering it.
