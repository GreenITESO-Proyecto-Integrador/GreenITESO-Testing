# GreenITESO-Testing

Framework de automatización de pruebas E2E para GreenITESO con **Playwright (sync API) + pytest**, gestionado con **uv**.

Somos 3 equipos. **Ningún equipo prueba su propio trabajo**: cada equipo escribe las pruebas de los módulos de otro equipo. `tests/equipoN/` contiene las pruebas de los módulos del equipo N. Cada equipo define qué módulos tiene.

## Setup

```bash
brew install uv                         # o: curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync                                 # crea .venv con las dependencias de uv.lock
uv run playwright install chromium      # navegadores de Playwright
if [ ! -e .env ] && [ ! -L .env ]; then cp .env.example .env; fi  # no sobrescribir
# Revisa y configura BASE_URL, AUTH_MODE, cuentas y E2E_CLEANUP antes de iniciar sesión o probar.
uv run python -m src.utils.auth --role student   # login manual con Microsoft, una vez por rol
uv run python -m src.utils.auth --role admin
uv run python -m src.utils.auth --role leader
uv run python -m src.utils.auth --role campaign_leader   # líder propio del módulo Campañas
uv run python -m src.utils.auth --role store             # cuenta propia del módulo Tienda (canjes)
uv run python -m src.utils.auth --role actions           # cuenta propia de Registro de acciones
```

Por default, las pruebas corren contra la **versión desplegada en producción** (`BASE_URL` en `.env.example`). La API está en el mismo dominio, porque nginx manda `/api/` al backend.

`E2E_CLEANUP` también está activado por defecto: iniciar o terminar una corrida puede modificar datos mediante la API, incluso antes de ejecutar el primer caso. Revisa el destino y las cuentas, usa un ambiente aislado para pruebas que cambien datos y acuerda el alcance antes de usar un ambiente compartido. Desactivar la limpieza no convierte los casos en pruebas de solo lectura.

- Para agregar una dependencia usa `uv add <paquete>` (o `uv add --dev <paquete>`), **nunca** `pip install`. Sube `pyproject.toml` y `uv.lock` en el mismo commit.
- `.env` no se sube al repo. Las variables se leen solo desde `src/configs/environment.py`; no uses `os.getenv` en ningún otro archivo.

## Correr pruebas

```bash
uv run pytest -m sanity                          # suite diaria
uv run pytest -m full                            # suite completa (release a prod)
uv run pytest tests/Auth/test_Auth.py            # un módulo
uv run pytest -k test_00_01_006                  # un test
uv run pytest -m sanity --headed --slowmo 300    # viendo el navegador
uv run pytest -m full --browser firefox
allure serve reporting/allure-results            # reporte (requiere: brew install allure)
```

Lo que genera cada corrida va en `reporting/` (allure-results, screenshots de los tests que fallan, logs) y no se sube al repo.

## Estructura

```
conftest.py                 # fixtures globales: config de Playwright, screenshot + adjunto Allure al fallar
src/
  configs/environment.py    # única fuente de configuración (.env → constantes)
  actions/<Modulo>_actions.py   # TODA la lógica de cada módulo
  utils/
    auth.py                 # sesión de prueba: tokens del backend → sessionStorage (modos refresh/mock)
    api.py                  # ApiClient (API con los tokens de los roles de prueba) y api_for_page(page)
    mocks.py                # mocks de red: mock_api_error/json, capture_json_response, socket de notificaciones
    test_data.py            # marcador de datos de prueba (unique_name) + limpieza al final de la corrida
    common_actions.py       # acciones de UI reutilizables entre módulos/equipos (login_as, go_to, ...)
    helpers.py              # chequeos de estado, esperas, assert_action
    locators.py             # clase Locators (selectores XPath/CSS)
    logger.py               # get_logger(__name__)
tests/
  <Modulo>/                 # una carpeta por módulo del test plan (Auth, Campanas, Clanes, ...)
    __init__.py             # docstring con el ID del módulo, la ruta y sus casos TC-MM-NNN
    test_<Modulo>.py        # SOLO declaraciones de tests
  equipo1/ equipo2/ equipo3/   # cuando se haga el reparto, cada carpeta de módulo se mueve aquí
Jenkinsfile
.github/workflows/e2e-branch.yml  # E2E de dev/preprod en GitHub Actions con un stack desechable
ci/stack/                   # compose.yaml (db + backend mock + frontend), up.sh, down.sh, seed_users.py
ci/dispatch/trigger-e2e.yml # workflow que se copia a Backend y Frontend para disparar el E2E
ci/frontend-release-trigger.yml   # workflow para el repo de frontend (opcional)
```

**Módulos:** hay 14, que son los del test plan en Notion: Auth (01), Navegacion (02), Dashboard (03), Campanas (04), Catalogo (05), RegistroAcciones (06), Auditoria (07), Tienda (08), Feed (09), Notificaciones (10), Clanes (11), Leaderboard (12), Perfil (13) y Onboarding (14). Mientras no esté hecho el reparto, viven en `tests/<Modulo>/`. Después se mueven completos a `tests/equipoN/<Modulo>/`. Los nombres de las carpetas no llevan acentos ni ñ. Hasta el reparto, los tests usan `EE = 00` de forma provisional (p. ej. `test_00_01_006_checkLogout`). `tests/Auth/` es el módulo de referencia ya implementado.

**Regla 1:1:** a cada `test_<Modulo>.py` le corresponde un `src/actions/<Modulo>_actions.py` con el mismo `<Modulo>`. Ejemplo: `tests/equipo1/test_Metricas.py` → `src/actions/Metricas_actions.py`. Como `src/actions/` lo comparten los 3 equipos, los nombres de módulo no se pueden repetir entre equipos (si chocan, ponles prefijo, p. ej. `Equipo2Login`).

## Capas y convenciones

### 1. Tests: `tests/equipoN/test_<Modulo>.py`

Aquí solo se declaran los tests. No van locators, ni lógica, ni `page.click`. Cada test es una sola línea que llama a la acción del mismo nombre.

- **Nombre:** `test_<EE>_<MM>_<NNN>_<descripcionCamelCase>`. `EE` es el número de equipo/feature, `MM` el número de módulo y `NNN` el consecutivo (p. ej. `test_01_02_003_checkCreateReport`). La descripción empieza con un verbo como `check...`.
- **Markers:** cada test lleva `@pytest.mark.full`, y además `@pytest.mark.sanity` si es crítico y rápido. Todo test sanity también es full.
- **Dependencias:** `@pytest.mark.dependency(name="<nombre exacto del test>", depends=[...])`. El `name` siempre es igual al nombre de la función. En `depends` van los tests que preparan datos o estado (el setup del módulo suele ser el `_001`). Si un test del que depende falla, este se marca como *skipped*, no como fallido.
- **Allure:** `@allure.description("<Módulo>: <qué valida>")`.
- **Cuerpo:** `assert_action(actions.<mismo_nombre>, page)`.
- Orden de decoradores: `sanity` → `full` → `dependency` → `allure.description`.

```python
import allure
import pytest

from src.actions import Metricas_actions as actions
from src.utils.helpers import assert_action


@pytest.mark.sanity
@pytest.mark.full
@pytest.mark.dependency(name="test_01_02_003_checkCreateReport", depends=["test_01_02_001_checkSetUp"])
@allure.description("Métricas: Crear un reporte nuevo")
def test_01_02_003_checkCreateReport(page):
    assert_action(actions.test_01_02_003_checkCreateReport, page)
```

### Paralelismo: módulos en paralelo, tests de un módulo en orden

Con `pytest-xdist` y `--dist=loadfile` (ya está en `addopts`), cada archivo `test_<Modulo>.py` se manda completo a un mismo worker. Así, **los módulos corren en paralelo** y **los tests de un mismo módulo corren en orden en el mismo proceso**, por lo que `pytest-dependency` sigue funcionando dentro del módulo.

- Por eso las dependencias **solo pueden ser entre tests del mismo módulo**. Ese es el scope default de `pytest-dependency`; no uses `scope="session"`. Si un módulo necesita algo de otro, hazlo en su propio test de setup (`_001`) llamando a la action o a una common action.
- Los módulos tienen que ser **independientes entre sí**, porque corren al mismo tiempo contra el mismo ambiente. Crea tus propios datos con nombres únicos (prefijo del módulo + timestamp), no edites ni borres datos que use otro módulo y, si un módulo cambia el estado global de la cuenta (configuración, perfil), usa un usuario de prueba distinto.
- Cada worker escribe su propio log (`run_<fecha>_gw0.log`, `gw1`, ...).

```bash
uv run pytest -m full -n 4       # 4 módulos a la vez
uv run pytest -m full -n auto    # tantos como CPUs
uv run pytest -m full            # sin -n: secuencial, útil para depurar con --headed
```

### 2. Actions: `src/actions/<Modulo>_actions.py`

Aquí vive todo el proceso de cada test.

- **Funciones públicas:** una por test, con **el mismo nombre que el test**, que reciben `page: Page` y regresan `bool` (`True` = pasó). `assert_action` falla el test si regresan algo falsy. Si algo es inesperado, se vale lanzar una excepción con un mensaje claro (`RuntimeError(...)`).
- **Funciones privadas** con prefijo `_` (`_open_filters`, `_read_dropdown_text`, ...) para la lógica interna del módulo. Si algo sirve a más de un módulo, súbelo a `common_actions.py` o `helpers.py`.
- **Constantes** del módulo a nivel de archivo con `_MAYUSCULAS` (`_SHORT_TIMEOUT = 5_000`, textos esperados, nombres de datos de prueba). Los caches por página van en dicts indexados por `id(page)`.
- **Type hints** en todas las firmas (`Sequence[str]`, `str | None`, `-> bool`). Los parámetros de configuración van como keyword-only: `def _wait_x(page: Page, value: str, *, timeout: int) -> bool`.
- **Esperas:** nada de `time.sleep` ni de waits fijos largos. Usa polling con deadline (`deadline = time.monotonic() + timeout / 1000` y un `while` con `page.wait_for_timeout(100-200)`) o las esperas de Playwright (`locator.wait_for`, `expect`). También está `helpers.wait_until`.
- **Selectores:** siempre desde `Locs` (`page.locator(Locs.X)` o `page.locator(Locs.button_with_text("Guardar"))`), o con `get_by_role(..., name=re.compile(..., re.IGNORECASE))`. Escribir XPath inline solo se vale como *fallback* local.
- **Fallbacks robustos:** intenta primero la forma normal. Si falla, prueba otros candidatos (varios locators, `force=True`) y como último recurso `page.evaluate(...)` con JS para interactuar con el DOM o shadow DOM. Registra cada fallback con `logger.debug`.
- **Excepciones:** en chequeos que se vale que fallen, usa `except Exception:  # noqa: BLE001` y regresa `False`. No te tragues errores en silencio dentro del flujo principal.
- `logger = get_logger(__name__)` arriba del archivo. Usa `logger.info` para los pasos importantes y `logger.debug` para el detalle. Usa formato `%s`, no f-strings, en los mensajes de log.

### 3. Common actions: `src/utils/common_actions.py`

Acciones de UI **reutilizables entre módulos y equipos**: navegación (`go_to`), login/logout, clicks robustos, llenar campos de widgets, abrir menús, etc.

- Son públicas y sin `_`, con un docstring de una línea que diga qué hacen.
- Los timeouts van keyword-only con default (`*, timeout: int = 5_000`).
- Si no logran la acción, **lanzan excepción** (`RuntimeError("... was not visible")`, o la última excepción capturada). Las que solo consultan estado regresan `bool` (p. ej. `editor_selections_match`).
- El patrón típico es: buscar candidatos → `click_first_visible` con reintentos hasta el deadline → reintento con `force=True` → excepción.

### 4. Helpers: `src/utils/helpers.py`

Utilidades que **no hacen una acción de negocio**, sino que revisan o esperan un estado:

- `is_*` / `has_*` → regresan `bool` y **nunca lanzan excepción** (aceptan `*, timeout: int = 200` para checks rápidos).
- `wait_for_*` → hacen polling hasta un deadline y **lanzan `RuntimeError`** con un mensaje descriptivo si se acaba el tiempo. También pueden fallar antes si detectan un estado inválido (p. ej. "Sign In visible; requiere relogin").
- `reveal_*` / `ensure_*` → intentan llevar la UI a un estado (abrir un menú para que aparezca un botón) y regresan `bool`.
- Incluye `assert_action` y `locator_has_visible_match`, que son la base para lo demás.

### 5. Locators: `src/utils/locators.py`

Una sola clase `Locators` (alias `Locs`) para toda la app:

- **Constantes** en MAYÚSCULAS para los elementos fijos: `SIGN_IN_BUTTON`, `AUTHENTICATED_AVATAR`, `MAIN_MENU`, ...
- **`@staticmethod` parametrizables** que regresan el string del XPath/CSS, con nombre `<tag>_with_<criterio>(valor)`: `span_with_text`, `div_with_class`, `link_with_aria`, `button_with_text`, `div_with_role`, ... Se usa `contains(...)` para tolerar clases y textos parciales, y `|` para unir alternativas.
- Antes de crear un locator nuevo, revisa si ya existe uno genérico que sirva. Si el frontend tiene `data-testid`, úsalo antes que texto o clases (`element_with_test_id`).

## Sesión: login sin pasar por Microsoft en cada test

Los tests no usan la pantalla de login. `common_actions.login_as(page, role)` consigue tokens **reales** del backend y los inyecta en el `sessionStorage` del frontend con `page.add_init_script`, usando las mismas llaves que `GreenITESO-Frontend/src/lib/auth/session.ts`. Es lo mismo que hacen los tests del frontend, pero con tokens que el backend sí acepta.

```python
def test_07_01_002_checkPendingEvidence(page: Page) -> bool:
    login_as(page, "admin")   # antes de navegar; "student", "admin", "leader" o email="..."
    go_to(page, "/audit")
    ...
```

Hay dos modos, que se eligen con `AUTH_MODE` en `.env`:

| Modo | Para qué | Cómo consigue los tokens |
|---|---|---|
| `refresh` (default) | Ambientes desplegados (prod) | Una persona inicia sesión con Microsoft **una vez por usuario** con `uv run python -m src.utils.auth --role <rol>`. Se guarda su refresh token y en cada corrida se canjea en `/api/v1/auth/refresh/`. |
| `mock` | Stack local | `POST /api/v1/auth/login/` con `id_token = "mock:<email>"`. El backend solo lo acepta con `MICROSOFT_AUTH_MODE=mock` (local, sin desplegar). |

**Si el dueño de la cuenta no está en tu máquina:** que inicie sesión en el sitio desde su navegador, abra DevTools → Console y corra el snippet `DEVTOOLS_SNIPPET` de `src/utils/auth.py` (copia la sesión al portapapeles). Te la manda por un canal privado, tú copias su texto y corres `pbpaste | uv run python -m src.utils.auth --role <rol> --import`. El import canjea el refresh token de inmediato, así que la copia enviada deja de servir. El dueño **no** debe usar "Cerrar sesión" antes de que la importes (eso invalida el token); basta con cerrar la pestaña.

**Detalles del modo `refresh`:**
- Los refresh tokens **se pueden usar una sola vez** y duran **7 días**. Cada renovación guarda el token nuevo en `~/.greeniteso-e2e/auth/<email>.json`, que está fuera del repo; se puede cambiar con `AUTH_STATE_DIR`. Si pasan más de 7 días sin corridas, o alguien usa el token en otro lado, hay que repetir el login manual. El error lo dice.
- Los workers de xdist comparten ese archivo con un lock, así que solo uno canjea el token y los demás reusan el access token.
- El navegador recibe el access token y un refresh token **de relleno**. Si el frontend canjeara el token real, lo invalidaría para la siguiente corrida.
- No se guardan contraseñas. En prod no existe el login `mock:`, por eso este modo usa cuentas reales de @iteso.mx.
- El rol ADMIN se asigna en la BD de ese ambiente con `manage.py assign_user_role <email> ADMIN`, y eso lo tiene que hacer alguien con acceso.

**En los dos modos:**
- La sesión se inyecta una sola vez por pestaña. Así, el test de "Cerrar sesión" funciona: después de salir, la sesión no regresa al navegar.
- Los tests que necesitan entrar **sin sesión** (como el de la pantalla de login) simplemente no llaman `login_as`.
- El rol de líder de clan no es global: el usuario `leader` tiene que tener su clan como parte del setup del módulo. Campañas usa su propio `campaign_leader` (el backend permite un solo liderazgo por usuario); si ese usuario ya lidera un clan, el setup lo reusa en vez de crear uno.
- La Tienda usa su propio `store`: canjear cambia su saldo e inventario y no se puede deshacer. En el stack desechable, `up.sh` le da 50 pts iniciales; en un ambiente desplegado necesita saldo real y artículos que aún no tenga (si no, el canje falla como BLOQUEADO).
- Registro de acciones usa su propio `actions`: registrar cambia sus puntos y gasta su cupo diario por acción, y el backend cuenta también los registros rechazados, así que la limpieza no libera el cupo. Cada corrida elige acciones con cupo; si ya no queda (p. ej. una segunda corrida el mismo día con una sola acción con foto), el test falla como BLOQUEADO. Necesita el onboarding hecho (clan institucional): sin él, el backend rechaza todo registro.
- `login_as` marca el recorrido guiado como visto (en `localStorage`) para que no tape la UI. Solo los tests del recorrido usan `login_as(page, role, skip_tour=False)`.

## Mocks de red: cuándo usarlos

`src/utils/mocks.py` intercepta peticiones con `page.route`. Úsalos **solo** para estados que las cuentas reales no pueden alcanzar (error del servidor + "Reintentar", listas vacías, usuario nuevo) y para interceptar difusiones que llegarían a usuarios reales (p. ej. el POST de una campaña global o el websocket de notificaciones). Los caminos felices van contra el backend real. Los mocks se registran antes de `go_to`.

## Datos de prueba en prod: marcar y limpiar

Las pruebas corren contra prod, así que **todo dato que cree un test lleva el marcador de la corrida**. Se genera con `src/utils/test_data.py`:

```python
from src.utils.test_data import unique_name

name = unique_name("Clan", max_length=100)    # "E2E-2611061530-ab12 Clan 1"
```

- Úsalo en todo texto que identifique lo creado: contenido de posts, nombre de clan, título de campaña o propuesta, bio y nickname. Respeta los límites del backend con `max_length`: nickname 50, clan 100, campaña 150 y bio 500.
- Hay un solo marcador por corrida, el mismo en todos los workers. Al terminar, `conftest.py` llama `cleanup_run` una vez desde el proceso controlador, y este usa la API con los usuarios de prueba para:
  - borrar los posts marcados;
  - rechazar las propuestas de campaña pendientes que estén marcadas;
  - iniciar y finalizar las campañas marcadas, porque no se pueden borrar;
  - salir de los clanes sin marcador a los que un usuario de prueba se unió durante la corrida (se registran con `register_membership`; p. ej. Campañas reusa el clan real que ya lidera `campaign_leader`). Va después de las campañas;
  - disolver los clanes marcados. Va después de las campañas, porque al disolver un clan se ocultan sus campañas PRIVATE;
  - borrar (soft delete) las notificaciones marcadas, en mensaje o título, de cada usuario de prueba. Va al final, porque rechazar propuestas y disolver clanes también genera notificaciones con el marcador;
  - rechazar los action logs que crearon los usuarios de prueba durante la corrida, lo que revierte sus puntos;
  - restaurar el perfil de cada usuario de prueba (bio, preferencias, visibilidad y avatar) a como estaba antes de la corrida.
- Al iniciar, también limpia los marcadores de corridas que no terminaron y tienen más de 3 horas.
- El resumen sale en la terminal y en `reporting/logs/cleanup_<marcador>.json`. Para depurar sin limpiar, usa `E2E_CLEANUP=false`.
- **Lo que no se puede deshacer:** los canjes en la tienda, las campañas finalizadas (quedan en el historial), las notificaciones que les llegan a usuarios reales, el costo de cambiar el nickname, las propuestas de campaña rechazadas (no hay DELETE; quedan como REJECTED) y las imágenes del feed que se subieron pero nunca se adjuntaron a un post (las de un post se borran junto con él). Los tests que hacen esto van solo en `full`, y hay que evitar que interactúen con usuarios reales; por ejemplo, no enviar solicitudes a clanes ajenos.
- Si un test crea algo que la limpieza no cubre, agrega el paso en `test_data.py`. No lo dejes al aire.

## Configuración y fixtures

- `conftest.py` configura `pytest-playwright` (headless, slow_mo, `base_url`, viewport, timeouts) con lo que hay en `environment.py`. El fixture `page` ya trae los timeouts default.
- Cuando un test falla se guarda un screenshot full-page en `reporting/screenshots/` y se adjunta a Allure en automático.
- Como `base_url` ya está configurado, `page.goto("/ruta")` funciona. También está `common_actions.go_to(page, "/ruta")`.

## CI: dev y preprod en GitHub Actions (stack desechable)

dev y preprod **no están desplegados** (en el backend, `CLOUD_DEPLOYMENT_ENABLED` está apagado; solo prod tiene URL). Para probar cada cambio que entra a esas ramas, `.github/workflows/e2e-branch.yml` arma el ambiente dentro del runner y lo tira al terminar:

1. **Disparo:** cada push a `dev` o `preprod` en Backend o Frontend corre su `trigger-e2e.yml` (copia de `ci/dispatch/trigger-e2e.yml`), que manda un `repository_dispatch` (`greeniteso-branch-updated`, con `repo`, `branch` y `sha`) a este repo. También se puede lanzar a mano en *Actions → E2E - rama → Run workflow*.
2. **Checkout:** el repo que disparó va en su commit exacto y el otro en la punta de la misma rama.
3. **Stack** (`ci/stack/up.sh`): Postgres en tmpfs, backend con `MICROSOFT_AUTH_MODE=mock` (migra y carga el catálogo al arrancar) y frontend con su Dockerfile real (nginx manda `/api/` y `/ws/` al backend), todo en `http://localhost:8080`. `seed_users.py` crea los 6 usuarios `e2e.*@iteso.mx` con onboarding hecho, `assign_user_role` deja al admin como ADMIN y el usuario `store` recibe 50 pts disponibles.
4. **Suite:** `pytest -m full -n 4` con `AUTH_MODE=mock`. No hace falta guardar sesiones ni tokens, y como la base es nueva en cada corrida no se acumula nada.
5. **Resultados:** resumen en la página de la corrida, artifact `e2e-<rama>-<run>` con JUnit, Allure, screenshots, logs y `stack.log` (logs del backend/frontend). Con el secreto opcional `E2E_STATUS_TOKEN` (fine-grained PAT con *Commit statuses: write* en Backend y Frontend) deja el estado `e2e/<rama>` (✅/❌) en el commit que disparó.

Para correrlo en local (necesita Docker):

```bash
BACKEND_DIR=../GreenITESO-Backend FRONTEND_DIR=../GreenITESO-Frontend ci/stack/up.sh
BASE_URL=http://localhost:8080 AUTH_MODE=mock AUTH_STATE_DIR=/tmp/e2e-auth \
  TEST_STUDENT_EMAIL=e2e.student@iteso.mx TEST_ADMIN_EMAIL=e2e.admin@iteso.mx \
  TEST_LEADER_EMAIL=e2e.leader@iteso.mx TEST_CAMPAIGN_LEADER_EMAIL=e2e.campaign.leader@iteso.mx \
  TEST_STORE_EMAIL=e2e.store@iteso.mx TEST_ACTIONS_EMAIL=e2e.actions@iteso.mx \
  uv run pytest -m full -n 4
ci/stack/down.sh
```

Lo que hay que configurar una vez:
- En Backend y Frontend: copiar `ci/dispatch/trigger-e2e.yml` a `.github/workflows/trigger-e2e.yml` y crear el secreto `E2E_DISPATCH_TOKEN` (fine-grained PAT o GitHub App con acceso solo a GreenITESO-Testing y *Contents: Read and write*). Sin el secreto, el trigger falla (en rojo) para que no se salte el E2E en silencio.
- En Testing (opcional): el secreto `E2E_STATUS_TOKEN` para los estados en los commits.

Cuando dev o preprod se desplieguen, la misma suite puede apuntar a su URL con `BASE_URL`, pero ahí aplica el modo `refresh` (sesiones reales por ambiente), como en prod.

## CI: Jenkins (prod)

`Jenkinsfile` (pipeline declarativo):

- **Sanity diario:** cron `H 6 * * *` en `America/Mexico_City`. Usa los defaults, o sea `SUITE=sanity`.
- **Full en release:** el job se dispara por la API `buildWithParameters` con `SUITE=full`.
- Parámetros: `SUITE`, `BASE_URL` (default: prod), `API_BASE_URL`, `AUTH_MODE`, `BROWSER`, `WORKERS` (módulos en paralelo, default 4) y `EXTRA_PYTEST_ARGS`.
- Necesita los plugins Pipeline, JUnit y Allure (con la tool `allure` configurada), y las sesiones de los usuarios de prueba guardadas en el agente: el login manual se corre una vez en el agente con el usuario de Jenkins.
- Publica JUnit, el reporte de Allure y guarda screenshots y logs como artifacts.

**Trigger automático desde el frontend (opcional):** `ci/frontend-release-trigger.yml` se copia al repo de frontend como `.github/workflows/trigger-e2e-full.yml`. Cuando se publica un release (que no sea prerelease), llama a Jenkins con `SUITE=full`. Para esto Jenkins tiene que ser accesible desde internet. Mientras no haya un servidor, el build full se lanza a mano desde Jenkins con *Build with Parameters → SUITE=full*.
