# GreenITESO-Testing

Framework de automatización de pruebas E2E para GreenITESO con **Playwright (sync API) + pytest**, gestionado con **uv**.

Somos 3 equipos. **Ningún equipo prueba su propio trabajo**: cada equipo escribe las pruebas de los módulos de otro equipo. `tests/equipoN/` contiene las pruebas de los módulos del equipo N. Cada equipo define qué módulos tiene.

## Setup

```bash
brew install uv                         # o: curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync                                 # crea .venv con las dependencias de uv.lock
uv run playwright install chromium      # navegadores de Playwright
cp .env.example .env                    # y llenar BASE_URL, TEST_USER, TEST_PASSWORD
```

- Para agregar una dependencia usa `uv add <paquete>` (o `uv add --dev <paquete>`), **nunca** `pip install`. Sube `pyproject.toml` y `uv.lock` en el mismo commit.
- `.env` no se sube al repo. Las variables se leen solo desde `src/configs/environment.py`; no uses `os.getenv` en ningún otro archivo.

## Correr pruebas

```bash
uv run pytest -m sanity                          # suite diaria
uv run pytest -m full                            # suite completa (release a prod)
uv run pytest tests/equipo1/test_Metricas.py     # un módulo
uv run pytest -k test_01_02_003                  # un test
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
    common_actions.py       # acciones de UI reutilizables entre módulos/equipos
    helpers.py              # chequeos de estado, esperas, assert_action
    locators.py             # clase Locators (selectores XPath/CSS)
    logger.py               # get_logger(__name__)
tests/
  equipo1/ equipo2/ equipo3/
    test_<Modulo>.py        # SOLO declaraciones de tests
Jenkinsfile
ci/frontend-release-trigger.yml   # workflow para el repo de frontend (opcional)
```

**Regla 1:1:** a cada `tests/equipoN/test_<Modulo>.py` le corresponde un `src/actions/<Modulo>_actions.py` con el mismo `<Modulo>`. Ejemplo: `tests/equipo1/test_Metricas.py` → `src/actions/Metricas_actions.py`. Como `src/actions/` lo comparten los 3 equipos, los nombres de módulo no se pueden repetir entre equipos (si chocan, ponles prefijo, p. ej. `Equipo2Login`).

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

## Configuración y fixtures

- `conftest.py` configura `pytest-playwright` (headless, slow_mo, `base_url`, viewport, timeouts) con lo que hay en `environment.py`. El fixture `page` ya trae los timeouts default.
- Cuando un test falla se guarda un screenshot full-page en `reporting/screenshots/` y se adjunta a Allure en automático.
- Como `base_url` ya está configurado, `page.goto("/ruta")` funciona. También está `common_actions.go_to(page, "/ruta")`.

## CI: Jenkins

`Jenkinsfile` (pipeline declarativo):

- **Sanity diario:** cron `H 6 * * *` en `America/Mexico_City`. Usa los defaults, o sea `SUITE=sanity`.
- **Full en release:** el job se dispara por la API `buildWithParameters` con `SUITE=full`.
- Parámetros: `SUITE`, `BASE_URL`, `BROWSER`, `WORKERS` (módulos en paralelo, default 4) y `EXTRA_PYTEST_ARGS`.
- Necesita los plugins Pipeline, Credentials Binding, JUnit y Allure (con la tool `allure` configurada), y una credencial *Username with password* con id `greeniteso-test-user`.
- Publica JUnit, el reporte de Allure y guarda screenshots y logs como artifacts.

**Trigger automático desde el frontend (opcional):** `ci/frontend-release-trigger.yml` se copia al repo de frontend como `.github/workflows/trigger-e2e-full.yml`. Cuando se publica un release (que no sea prerelease), llama a Jenkins con `SUITE=full`. Para esto Jenkins tiene que ser accesible desde internet. Mientras no haya un servidor, el build full se lanza a mano desde Jenkins con *Build with Parameters → SUITE=full*.
