# LN-ARC

**LN-ARC** is a recon-only, LLM-driven multi-agent reconnaissance console. It maps
an authorized target's external surface — subdomains, DNS, TLS, services, URLs,
APIs, parameters and public exposures — and produces evidence-backed reports.

> LN-ARC is a recon-only derivative of an upstream open-source project, licensed
> under **AGPL-3.0**. Original copyright notices remain in `LICENSE` and the
> upstream project history. LN-ARC does not include exploitation or vulnerability
> weaponization workflows.

## Features

- **Multi-agent exploration** — planner, workers and a main agent share an asset
  graph, facts and coverage state.
- **Recon toolkit** — subdomain/DNS, TLS, HTTP fingerprinting, safe content
  discovery, light port checks, JavaScript endpoint mining, traffic analysis,
  archive/CT history, cloud-storage exposure and visual recon.
- **Skill suite** — 19 Markdown skills under `skills/`, loaded per agent and
  visible/toggleable in the UI.
- **Asset graph + coverage** — domains, subdomains, IPs, services, endpoints and
  applications, with untested-asset tracking.
- **Traffic capture** — recording proxy with `traffic_search` / `traffic_get` /
  `traffic_blob` tools.
- **Reports** — Markdown reports in Vietnamese/English, published to **Tasks →
  Reports**.
- **Auth** — single fixed account, JWT sessions, password reset scripts.

## Stack

| Layer | Technology |
|---|---|
| Backend | Go 1.26+ (module `github.com/hypnguyen1209/V-ARTEX`), embedded Next.js UI optional |
| Frontend | Next.js 16 / React 19 / Tailwind |
| Database | PostgreSQL 16 |
| LLM | Any OpenAI-compatible or Anthropic-compatible endpoint, configured in the UI or env |
| Browser tools | Playwright MCP/CLI (optional) |

## Requirements

- **Go 1.26+**
- **Node.js 20+** and npm
- **PostgreSQL 16** (Docker is the simplest option)
- **Python 3.10+** for `reports/sync_web.py` and skill checks
- Optional: Docker Desktop, Playwright browsers

## Quick start (Windows, development)

### 1. Database

```bat
docker run -d --name lnai-postgres ^
  -e POSTGRES_USER=artex ^
  -e POSTGRES_PASSWORD=change-me-please ^
  -e POSTGRES_DB=artex ^
  -p 5432:5432 postgres:16-alpine
```

If the container already exists: `docker start lnai-postgres`.

### 2. Backend

```bat
go build -o dist\artex-windows-amd64\lnai.exe ./cmd/artex
```

`start.bat` runs this binary and the Next.js dev server. It also exports:

```bat
set ARTEX_PG_DSN=postgres://artex:change-me-please@localhost:5432/artex?sslmode=disable
set ARTEX_ADMIN_PASSWORD=admin123
```

### 3. Frontend

```bat
cd web
npm install
cd ..
```

`start.bat` starts `npx next dev` on `http://localhost:3000` and proxies `/api`
to the backend on `http://localhost:8787`.

### 4. Run

```bat
start.bat
```

Open **http://localhost:3000**. On first run, initialize the password on
`/setup` using the setup token from the backend console, or set
`ARTEX_ADMIN_PASSWORD` before the first start.

### 5. Login

The account name is fixed and hidden in the UI; enter **only the password**.
If you forget it, run `reset-password.bat` (Windows) or `reset-password.sh`
(Linux/macOS) and restart the backend with `ARTEX_ADMIN_PASSWORD` set.

## Quick start (Linux / macOS)

```bash
# 1. PostgreSQL
docker run -d --name lnai-postgres \
  -e POSTGRES_USER=artex -e POSTGRES_PASSWORD=change-me-please \
  -e POSTGRES_DB=artex -p 5432:5432 postgres:16-alpine

# 2. Backend + frontend
cd web && npm install && cd ..
go build -o artex ./cmd/artex

export ARTEX_PG_DSN='postgres://artex:change-me-please@localhost:5432/artex?sslmode=disable'
export ARTEX_ADMIN_PASSWORD='admin123'
./artex -addr 127.0.0.1:8787 -proxy 127.0.0.1:8788

# 3. Frontend (another terminal)
cd web && npx next dev
```

`./start.sh` is the supervisor variant: it loads `.env` and restarts `./artex`
on crash. It expects the binary at `./artex`.

## Single binary (embedded UI)

Build the static frontend, copy it into the backend embed directory, then build
with `-tags embedui`:

```bash
cd web
npm run build:static
cd ..
rm -rf server/webui/dist
cp -r web/out server/webui/dist
CGO_ENABLED=0 go build -tags embedui -ldflags="-s -w" -o artex ./cmd/artex
```

Run `./artex` and open `http://127.0.0.1:8787`. On Windows, the equivalent output
path is `dist\artex-windows-amd64\lnai.exe`.

`./build.sh` automates the frontend + Go build. `./build.sh --release` packages
all supported targets (requires `zip`, `rsync` and Go).

## Environment variables

| Variable | Purpose |
|---|---|
| `ARTEX_PG_DSN` | PostgreSQL DSN (highest precedence; overrides `config.json`) |
| `ARTEX_ADMIN_PASSWORD` | Initialize the password on an empty installation (ignored after setup) |
| `ARTEX_SETUP_TOKEN` | One-time setup token instead of the console-printed value |
| `ARTEX_CORS_ORIGINS` | Exact browser origins for cross-origin UI access |
| `ARTEX_SKILL_DIR` | Skill root (default: `skills/` beside the executable) |
| `ARTEX_JWT_KEY_DIR` | Directory for `jwt.key` (default: beside the executable) |
| `ARTEX_LLM_PROVIDER` | `openai`, `openai-responses` or `anthropic` |
| `ARTEX_LLM_MODEL` | Model id |
| `ARTEX_LLM_BASE_URL` | OpenAI/Anthropic-compatible endpoint |
| `ARTEX_LLM_SESSION_HEADER` | Optional session header, e.g. `x-opencode-session` for OpenCode Go |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Provider key (or configure a profile in the UI) |
| `ARTEX_LLM_PROXY` | Optional outbound proxy (`http`/`https`/`socks5`) |

Configuration precedence for the database:
`ARTEX_PG_DSN` → `config.json` (`database.dsn` or individual fields) → defaults.
`config.json` is optional; see `config.example.json`.

## LLM configuration

1. Open **`/system/llm`** (the LLM settings page).
2. Create a profile: name, format (`openai` / `openai-responses` / `anthropic`),
   base URL, model, API key and, if the endpoint requires it, the **session
   header key** (for OpenCode Go: `x-opencode-session`).
3. Activate the profile. The engine hot-reloads without a restart.
4. Use **Test connection** to verify.

Environment variables are only a fallback: a persisted active profile takes
precedence. The backend binary does not read `.env` by itself — `start.sh` and
Docker load it; on Windows, `start.bat` sets the variables explicitly.

## Skills

Skills live in `skills/<name>/SKILL.md` and are loaded per agent according to
`agent_skill_visibility`.

- Shipped skills: `api-recon`, `subdomain-enum`, `dns-recon`, `tls-cert-recon`,
  `http-fingerprint`, `content-discovery`, `port-service-recon`,
  `js-endpoint-recon`, `traffic-analysis`, `archive-recon`,
  `cloud-storage-recon`, `visual-recon`, `scope-coverage`, `exposure-recon`,
  `exposure-assessment`, `self-exposure-audit`, `recon-report`,
  `playwright-cli`, `scopesentry`.
- Validate the suite:

```bash
python skills/check_skills.py
```

- Override the root with `ARTEX_SKILL_DIR`; restart the backend after changing
  skill files outside the running directory.

## Reports

Reports are Markdown files under `reports/`:

- `reports/<id>.vi.md` and `reports/<id>.en.md` for bilingual reports.
- The agent skill `recon-report` writes them; the report template lives in
  `skills/recon-report/SKILL.md`.
- Publish to **Tasks → Reports**:

```bash
python reports/sync_web.py
```

The script also finds `data/tasks/<id>/**/recon-report.md`. The generated
`web/src/lib/reports-data.ts` is local data; the repository ships an empty
placeholder so recon output is never committed.

## Docker (optional)

The Dockerfile consumes a **precompiled Linux binary**; it does not compile the
Go backend inside the image.

```bash
# 1. Build the binary and embedded UI
cd web && npm run build:static && cd ..
rm -rf server/webui/dist && cp -r web/out server/webui/dist
CGO_ENABLED=0 GOARCH=amd64 go build -tags embedui -o dist/amd64/artex ./cmd/artex

# 2. Build and run
cp .env.example .env      # set POSTGRES_PASSWORD and optional LLM keys
docker compose up -d --build
```

`docker-compose.yml` builds a local image (`ln-arc:local`) from this source and
mounts `./skills` and `./data`. The UI is served on `127.0.0.1:8787`; the
recording proxy uses `127.0.0.1:8788`.

> The compose service is still named `artex` for compatibility with existing
> environment files; it is the LN-ARC backend.

## Project layout

```
agent/            planner / worker / chat agents and recon skills integration
cmd/artex/        backend entry point
db/               PostgreSQL schema, migrations, asset/exploration stores
server/           HTTP API, auth, tools, reports, skills
skills/           Markdown skill suite
web/              Next.js frontend (dev server + static export)
reports/          local Markdown reports + sync_web.py
data/             runtime workspace (ignored by git)
```

## Security notes

- LN-ARC is **recon-only**: read-only discovery, no exploitation, no brute force,
  no credential use. Use it only on assets you are authorized to test.
- Do not commit `.env`, `jwt.key`, `data/`, logs or `reports/*.md`.
- The UI login account is fixed; protect the password and the database.
- The recording proxy is for your own traffic; do not intercept third-party
  traffic without authorization.

## Upstream

This project is a derivative work based on an upstream open-source project
licensed under AGPL-3.0. See [`LICENSE`](LICENSE) for the authoritative terms
and the upstream project history for original copyright notices.
