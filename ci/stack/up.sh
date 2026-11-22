#!/usr/bin/env bash
# Levanta el stack desechable (db + backend + frontend) desde los checkouts de las ramas y crea los
# usuarios de prueba. Al terminar, http://localhost:8080 está listo para AUTH_MODE=mock.
#
#   BACKEND_DIR=../GreenITESO-Backend FRONTEND_DIR=../GreenITESO-Frontend ci/stack/up.sh
#   ci/stack/down.sh     # para tirarlo
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
: "${BACKEND_DIR:?BACKEND_DIR apunta al checkout del backend}"
: "${FRONTEND_DIR:?FRONTEND_DIR apunta al checkout del frontend}"
export BACKEND_DIR FRONTEND_DIR
export BASE_URL="${BASE_URL:-http://localhost:8080}"

compose=(docker compose -f "$here/compose.yaml")

if ! "${compose[@]}" up -d --build --wait --wait-timeout 600; then
  "${compose[@]}" logs --tail 80 backend frontend >&2 || true
  exit 1
fi

admins="$(python3 "$here/seed_users.py")"
for email in $admins; do
  "${compose[@]}" exec -T backend python manage.py assign_user_role "$email" ADMIN
done
echo "Stack listo en $BASE_URL"
