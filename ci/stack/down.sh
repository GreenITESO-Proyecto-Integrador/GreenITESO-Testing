#!/usr/bin/env bash
# Tira el stack desechable y sus datos (la base vive en tmpfs, no queda nada).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="${BACKEND_DIR:-.}" FRONTEND_DIR="${FRONTEND_DIR:-.}" \
  docker compose -f "$here/compose.yaml" down --volumes --remove-orphans
