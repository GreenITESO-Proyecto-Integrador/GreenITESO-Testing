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

# Saldo inicial del usuario de la Tienda: el catálogo de CI no da 20 pts en un día y canjear no se
# deshace. 50 pts alcanzan para un marco (20) y dejan un fondo (100) fuera del saldo (caso 009).
store_email="${TEST_STORE_EMAIL:-e2e.store@iteso.mx}"
STORE_EMAIL="$store_email" "${compose[@]}" exec -T -e STORE_EMAIL backend python manage.py shell -c '
import os
from green_iteso.accounts.models import UserProfile
email = os.environ["STORE_EMAIL"]
if not UserProfile.objects.filter(user__email__iexact=email).update(available_points=50):
    raise SystemExit(f"No existe el perfil de {email}")
print(f"{email}: 50 pts disponibles")
'
echo "Stack listo en $BASE_URL"
