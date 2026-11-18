# syntax=docker/dockerfile:1
#
# Runtime image: install common tools and copy a precompiled Linux single binary.
# CI's binaries job cross-compiles pure Go without QEMU and places each target's binary
# at dist/<TARGETARCH>/artex in the build context. Multi-architecture arm64 builds only
# emulate the apt layer, avoiding slower emulated Next/Go compilation.
#
# Prepare the binary before building the image manually:
#   cd web && npm run build:static && cd ..
#   cp -r web/out server/webui/dist
#   CGO_ENABLED=0 GOARCH=amd64 go build -tags embedui -o dist/amd64/artex ./cmd/artex
#   docker build -t artex:local .
FROM python:3.12-slim-bookworm
ARG TARGETARCH
# Common tools: ripgrep / curl / vim and recon utilities (adjust as needed).
# Install Node 20.x from NodeSource: bookworm's apt nodejs is 18, while Playwright requires >=20.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates ripgrep curl wget vim git jq unzip \
      dnsutils iputils-ping netcat-openbsd inetutils-telnet whois nmap \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*
# Preinstall Playwright MCP and CLI globally so npx needs no runtime download.
# @playwright/mcp: run the browser MCP with `npx @playwright/mcp` (globally installed; no -y/@latest needed).
# @playwright/cli: provides playwright-cli; verify it runs with --help after installation.
# Also install playwright for browser management, then use --with-deps to preinstall chromium
# and its system dependencies so MCP/CLI work immediately without downloading a browser at runtime.
# playwright-cli defaults to the "chrome" channel (/opt/google/chrome/chrome), so Chrome must be
# installed too; otherwise every `playwright-cli open` fails with a missing-distribution error.
RUN npm install -g @playwright/mcp@latest @playwright/cli@latest playwright@latest \
    && playwright-cli --help \
    && playwright install --with-deps chromium \
    && playwright install chrome \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# The container runs as root, where Chrome refuses to start with its sandbox enabled.
# Bake a CLI config that launches without the sandbox (playwright-cli otherwise picks the
# "chrome" channel and dies with "Running as root without --no-sandbox is not supported").
RUN mkdir -p /app/.playwright && cat > /app/.playwright/cli.config.json <<'JSON'
{
  "browser": {
    "launchOptions": {
      "args": ["--no-sandbox", "--disable-dev-shm-usage"]
    }
  }
}
JSON
# Precompiled binary for the target architecture (dist/amd64/artex or dist/arm64/artex)
COPY dist/${TARGETARCH}/artex /app/artex
# The supervisor restarts the process based on its exit code, allowing one-click updates to take effect.
# It also forwards SIGTERM to artex: docker stop only signals PID 1. Without forwarding,
# artex cannot shut down gracefully and is forcibly killed with SIGKILL after 10 seconds.
COPY start.sh /app/start.sh
RUN chmod +x /app/artex /app/start.sh
COPY skills/ /app/skills/
# Keep the persistent JWT key outside the browsable data workspace.
ENV ARTEX_JWT_KEY_DIR=/app/auth
VOLUME ["/app/data", "/app/auth"]
EXPOSE 8787 8788
ENTRYPOINT ["/app/start.sh"]
CMD ["-addr", ":8787", "-proxy", ":8788"]
