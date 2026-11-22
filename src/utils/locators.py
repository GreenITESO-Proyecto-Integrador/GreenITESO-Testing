"""Locators reutilizables (XPath/CSS) para la UI de GreenITESO.

- Locators fijos: constantes en MAYÚSCULAS dentro de la clase.
- Locators parametrizables: @staticmethod que reciben el texto/atributo y regresan el selector.

El frontend no tiene data-testid, así que se usan aria-label, roles y textos visibles.
"""


class Locators:
    """Collection of XPath/CSS helpers for the GreenITESO UI."""

    # --- Login (pages/Login/Login.tsx) ---
    LOGIN_BRAND = "//main//p[normalize-space(.)='GreenITESO']"
    LOGIN_TITLE = "//h1[normalize-space(.)='Inicia sesión']"
    LOGIN_BUTTON = "//button[contains(normalize-space(.), 'Iniciar sesión con @iteso.mx')]"
    LOGIN_INSTITUTIONAL_NOTICE = "//p[normalize-space(.)='Usa exclusivamente tu cuenta institucional @iteso.mx.']"
    LOGIN_NOT_CONFIGURED_ALERT = "//*[@role='alert'][contains(., 'Microsoft login no está configurado')]"

    # --- Sesión (components/auth/*) ---
    SESSION_CHECKING = "//*[normalize-space(.)='Verificando sesión…']"
    ACCESS_DENIED_TITLE = "//h1[normalize-space(.)='Acceso Restringido']"
    ACCESS_DENIED_BADGE = "//span[normalize-space(.)='Error 403 · Prohibido']"
    ACCESS_DENIED_BACK_BUTTON = "//button[contains(normalize-space(.), 'Volver al inicio')]"

    # --- Layout (components/layout/Navbar.tsx, components/onboarding/OnboardingGate.tsx) ---
    USER_MENU_BUTTON = "//button[@aria-label='Menú de usuario']"
    ONBOARDING_DIALOG = "//*[@role='dialog'][.//*[normalize-space(.)='Completa tu perfil']]"

    # --- Dashboard (pages/Dashboard) ---
    DASHBOARD_IMPACT_TITLE = "//h2[normalize-space(.)='Tu impacto']"

    # --- Leaderboard (pages/Leaderboard, components/shared/Pagination.tsx) ---
    LEADERBOARD_TITLE = "//main//h1[normalize-space(.)='Tablas de clasificación']"
    LEADERBOARD_TABS = "//*[@role='tablist'][@aria-label='Tablas de clasificación']//button[@role='tab']"
    LEADERBOARD_TABLE = "//main//table"
    LEADERBOARD_ROWS = "//main//table/tbody/tr"
    LEADERBOARD_NAME_HEADER = "//main//table/thead//th[2]"
    LEADERBOARD_LOADING = "//*[@role='status'][contains(normalize-space(.), 'Cargando clasificación')]"
    LEADERBOARD_EMPTY_TITLE = "//main//h2[normalize-space(.)='Aún no hay clasificación']"
    LEADERBOARD_ERROR_TITLE = "//main//h2[normalize-space(.)='No se pudo cargar la clasificación']"
    LEADERBOARD_RETRY_BUTTON = "//main//button[normalize-space(.)='Reintentar']"
    LEADERBOARD_PAGER = "//nav[starts-with(@aria-label, 'Paginación de')]"
    LEADERBOARD_PAGER_PROGRESS = "//nav[starts-with(@aria-label, 'Paginación de')]//*[@role='progressbar']"
    LEADERBOARD_PAGER_PREV = "//nav[starts-with(@aria-label, 'Paginación de')]//button[@aria-label='Página anterior']"
    LEADERBOARD_PAGER_NEXT = "//nav[starts-with(@aria-label, 'Paginación de')]//button[@aria-label='Página siguiente']"

    # --- Perfil (pages/Profile) ---
    PROFILE_NAME_TITLE = "//main//h1"

    # --- Locators parametrizables ---
    @staticmethod
    def button_with_text(text: str) -> str:
        return f"//button[contains(normalize-space(.), '{text}')]"

    @staticmethod
    def menuitem_with_text(text: str) -> str:
        return f"//*[@role='menuitem'][contains(normalize-space(.), '{text}')]"

    @staticmethod
    def element_with_test_id(test_id: str) -> str:
        return f"[data-testid='{test_id}']"

    @staticmethod
    def leaderboard_tab_with_text(text: str) -> str:
        return f"//*[@role='tablist']//button[@role='tab'][normalize-space(.)='{text}']"

    @staticmethod
    def leaderboard_cell_with_position(row: int, column: int) -> str:
        """Cell of the ranking table; `row` and `column` are 1-based."""
        return f"//main//table/tbody/tr[{row}]/td[{column}]"

    @staticmethod
    def leaderboard_row_with_name(name: str) -> str:
        return f"//main//table/tbody/tr[.//td[contains(normalize-space(.), '{name}')]]"


Locs = Locators
