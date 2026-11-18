#!/usr/bin/env bash
# Chạy ARTEX với biến môi trường trong .env (binary Go không tự đọc .env).
# Usage:
#   ./run.sh                 # chạy nền: nohup tự thêm, log vào artex.log
#   ./run.sh -addr :9000     # thêm tham số khác cho artex
set -euo pipefail
cd "$(dirname "$0")"

[ -x ./artex ] || { echo "[run] Không tìm thấy ./artex — hãy chạy ./build.sh trước" >&2; exit 1; }

# Nạp toàn bộ biến trong .env vào môi trường (set -a = export tự động).
if [ -f .env ]; then
	set -a
	# shellcheck disable=SC1091
	. ./.env
	set +a
fi

exec ./artex "$@"
