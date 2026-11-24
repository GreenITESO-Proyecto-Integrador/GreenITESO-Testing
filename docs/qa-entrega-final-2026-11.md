# Metodología de pruebas cruzadas de la entrega final

El Equipo 1 evaluó identidad, acceso y clanes del Equipo 2 entre el 22 y el 23 de noviembre de 2026 (CDMX). La entrega contiene 30 casos, con evidencia por caso y un video con capítulos y subtítulos en español.

[Resultados y capturas](https://lab.ferramos.com/resultados/) · [Video](https://lab.ferramos.com/video/) · [Matriz del wiki](https://github.com/GreenITESO-Proyecto-Integrador/GreenITESO-Infra/wiki/QA-entrega-final-2026-11-24)

## Fuentes y criterios

1. Tomar la asignación de pruebas cruzadas como alcance inicial. Usar la matriz preparada por Fernando como punto de partida y rastrear el alcance adicional a los issues, criterios del equipo dueño, PRs y comportamiento de la versión candidata. En la matriz publicada cada caso conserva sus referencias cuando están disponibles.
2. Para cada caso identificar requisito, rol, datos previos, acción, resultado esperado, entorno y resultado observado. Comparar las señales que requiere el criterio. Usar la interfaz para el recorrido, la respuesta de la API para el contrato y la base aislada para la persistencia.
3. Cubrir caminos positivos, negativos, estados vacíos, reintentos, recargas y diferencias entre roles. Para clanes y avatares usar contextos de navegador independientes. Los recorridos donde importa la visibilidad o una notificación requieren dos identidades distintas.
4. Ante un resultado ambiguo, repetir con las precondiciones anotadas y comprobar la señal exacta. En T1-15 se sincronizaron los controles del recorrido con el área visible y se variaron los datos del catálogo. El informe conserva el resultado de cada condición y la comprobación en producción.
5. Registrar **Aprobado**, **Fallido** o **Parcial** según el criterio. Una prueba local aprobada y un paso pendiente en producción pueden convivir en el mismo caso. Una reejecución con dos navegadores cuenta como dos ejecuciones y conserva el ID del caso.

## Automatización y entorno

Se usó Python con **pytest y Playwright**. Los archivos de [`release_qa/`](../release_qa/) reutilizan las utilidades de autenticación y navegación del repositorio. Los datos sintéticos usan cuentas distintas por escenario y, cuando se necesita, se preparan con la API o Django dentro de Docker. La suite de la entrega se invoca explícitamente. Conserva las aserciones que reproducen hallazgos y queda fuera del descubrimiento normal de `tests/`.

| Elemento | Revisión o entorno de la entrega |
| --- | --- |
| Frontend local | `7160a5ec0a33098b5783531affbf58439fbcba54` |
| Backend local | `33ffa43fca5baa1340f0ad143607a31c6fe71bd7` |
| Testing al ejecutar la entrega | `a0e7c973d0b507e8d8033f9c1f23b8de999115bd` |
| Stack | Django, PostgreSQL 18.6, Nginx y frontend en `http://localhost:8080` |
| Navegadores de las reejecuciones | Chromium y WebKit de Playwright |
| Aplicación real | `greeniteso.mocking.so`. Los resultados manuales registran el comportamiento servido. Los SHAs anteriores identifican el stack local. |

### Reproducción

Compose usa la etiqueta `postgres:18`. Para repetir la versión menor de la entrega, usar `postgres:18.6` en un override local. En la revisión evaluada, el Dockerfile de Frontend resolvió las dependencias sin lockfile.

Desde la raíz de GreenITESO-Testing, preparar checkouts separados de Frontend y Backend en las revisiones indicadas. Ajustar las rutas del ejemplo al checkout utilizado. El nombre de proyecto Compose conecta las pruebas de persistencia con el contenedor Django desechable.

```sh
uv sync --frozen
uv run --frozen playwright install chromium webkit

export BACKEND_DIR="/ruta/GreenITESO-Backend"
export FRONTEND_DIR="/ruta/GreenITESO-Frontend"
export BASE_URL=http://localhost:8080 API_BASE_URL=http://localhost:8080
export AUTH_MODE=mock E2E_CLEANUP=false

docker compose -f ci/stack/compose.yaml -p greeniteso-final-qa up -d --build --wait
uv run --frozen python ci/stack/seed_users.py
docker compose -f ci/stack/compose.yaml -p greeniteso-final-qa exec -T backend \
  python manage.py assign_user_role e2e.admin@iteso.mx ADMIN

uv run --frozen pytest -q --browser chromium --browser webkit \
  release_qa --junitxml=reporting/final-peer-qa.xml
```

La suite escribe en la base temporal y puede añadir campañas y clanes. Para comparar escenarios con catálogos vacío, de una campaña o de varias campañas, usar un stack recién creado para cada condición y preparar el catálogo correspondiente. El módulo `test_tour_retest.py` admite `TOUR_SEED_CAMPAIGN=1` para preparar una campaña y `TOUR_CAPTURE_IN_VIEWPORT=1` para comprobar los controles dentro de la pantalla antes de avanzar. Las capturas de identidad y clanes son opcionales y se habilitan con `GREENITESO_IDENTITY_EVIDENCE` y `FINAL_QA_CLAN_EVIDENCE`, apuntando a carpetas dentro de `reporting/`. Las capturas, videos y notas de estas suites y del perfil se escriben en subcarpetas por navegador. Ejecutar secuencialmente los escenarios que comparten el catálogo. Los nombres internos de algunos tests de perfil provienen de su corrida original. El resultado oficial se consulta por el ID publicado en la matriz.

Para confirmar la colección sin ejecutar las pruebas:

```sh
uv run --frozen pytest --collect-only -q --browser chromium --browser webkit release_qa
```

### Reejecución local con varias cuentas

Se ejecutaron 12 escenarios en Chromium y WebKit, para **24 ejecuciones, 22 aprobadas y 2 fallidas**. Ambas fallas corresponden a T1-09, la eliminación de la fila de membresía al abandonar un clan. Los puntos históricos se conservaron.

```sh
uv run --frozen pytest -q --browser chromium --browser webkit \
  release_qa/test_final_clans.py::test_t1_06_public_clan_creation_join_and_active_persistence \
  release_qa/test_final_clans.py::test_t1_07_private_requests_and_leader_controls \
  release_qa/test_final_clans.py::test_t1_07_private_code_is_single_use \
  release_qa/test_team2_acceptance.py::test_t109_attribution_and_leave \
  release_qa/test_team2_acceptance.py::test_t110_transfer_expel_dissolve \
  release_qa/test_team2_clan_audit.py::test_clan_edit_keeps_members_and_pending_requests \
  release_qa/test_team2_clan_audit.py::test_leader_revokes_unredeemed_invite_code \
  release_qa/test_team2_clan_audit.py::test_clan_profile_shows_active_clan_campaigns_to_members \
  release_qa/test_team2_clan_delivery.py::test_clan_roster_loads_public_member_avatar_and_hides_it_after_privacy_change \
  release_qa/test_team2_clan_delivery.py::test_clan_join_notification_reaches_open_browser_and_persists \
  release_qa/test_team2_clan_followthrough.py::test_expired_invite_is_hidden_and_cannot_be_redeemed \
  release_qa/test_membership_rejoin.py --junitxml=reporting/final-peer-qa-multi-account.xml
```

## Producción y captura de evidencia

- Ejecutar la comprobación de acceso sin sesión con `uv run --frozen python release_qa/production_smoke.py`. Comprueba la redirección de perfil, clanes y notificaciones y las respuestas de sus rutas de lectura sin sesión.
- El titular de la cuenta institucional proporcionó grabaciones de acceso y rechazo de cuenta personal. Para usos autenticados se operó la interfaz con la sesión existente. Se confirmó la recarga, se restauró la biografía original y se disolvió el clan temporal tras crear, editar, buscar y revocar su invitación. Las capturas se guardaron bajo el caso correspondiente.
- La entrega deja como pendientes de producción los pasos que necesitan otra identidad ITESO, como ingreso, solicitudes, transferencia y expulsión, canje, avisos y visibilidad desde otra cuenta. La expiración de una invitación requiere además esperar su vigencia real de 48 horas. El informe distingue estos pasos de los casos ejecutados en local con cuentas sintéticas.
- Las verificaciones del hub están en [`release_qa/hub_checks/`](../release_qa/hub_checks/). Comprueban el sitio de evidencia, incluidos enlaces, pantallas, capítulos, subtítulos y resultados. Ejemplo de verificación del cierre de cobertura: `uv run --frozen python release_qa/hub_checks/verify-multi-account.py https://lab.ferramos.com`.

## Uso de IA y revisión

- **Codex** ayudó a rastrear criterios, preparar escenarios y código Python/Playwright, ejecutar y revisar resultados, investigar posibles falsos negativos y compilar el hub. Agentes de Codex revisaron áreas de identidad y clanes en el stack aislado.
- **Gemini 4 Neon mediante Antigravity CLI** contrastó un resumen de cobertura y señaló posibles vacíos para ampliar la revisión. Las sugerencias se contrastaron con el código y el comportamiento observado antes de incorporarlas a la matriz.
- **AI Doc Maker, voz Clear**, generó la narración en español. Se renderizó el video con FFmpeg y se usó Whisper para el borrador de subtítulos, que se revisó contra el audio y la terminología del proyecto.
- **Evidencia y atribución.** Las afirmaciones se sustentan con aserciones, respuestas observadas, capturas, grabaciones del titular y criterios enlazados. Las pruebas automáticas locales se identifican como sintéticas y las tomas en el despliegue como producción. Se conservaron enlaces al material publicado en el hub. Las grabaciones originales, los estados de sesión, las cuentas personales y los registros brutos se mantienen fuera del repositorio.
