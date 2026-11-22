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
    DASHBOARD_ADMIN_TITLE = "//main//p[normalize-space(.)='Dashboard']"
    DASHBOARD_TREND_TITLE = "//h2[normalize-space(.)='Tendencia (últimas 4 semanas)']"
    DASHBOARD_TREND_SECTION = "//section[.//h2[normalize-space(.)='Tendencia (últimas 4 semanas)']]"
    # Relativos: se encadenan desde DASHBOARD_TREND_SECTION / una gráfica. Llevan "xpath=" porque
    # Playwright solo detecta XPath si empieza con "//" o "..". En Recharts v3 las etiquetas del eje
    # van en una capa aparte (recharts-xAxis-tick-labels), no dentro de recharts-xAxis.
    DASHBOARD_TREND_CHART = "xpath=.//*[contains(@class,'recharts-wrapper')]"
    DASHBOARD_TREND_X_TICK = (
        "xpath=.//*[contains(@class,'recharts-xAxis-tick-labels')]"
        "//*[contains(@class,'recharts-cartesian-axis-tick-value')]"
    )
    DASHBOARD_MY_CAMPAIGNS_TITLE = "//h2[normalize-space(.)='Mis campañas']"
    DASHBOARD_MY_CAMPAIGN_CARD_TITLE = (
        "//section[.//h2[normalize-space(.)='Mis campañas']]//*[@role='button']//*[@data-slot='card-title']"
    )
    DASHBOARD_CAMPAIGNS_PAGINATION = "//nav[@aria-label='Paginación de campañas']"
    DASHBOARD_EMPTY_CAMPAIGNS = "//h3[normalize-space(.)='Aún no participas en campañas']"
    DASHBOARD_NO_FILTER_MATCH = "//h3[normalize-space(.)='Ninguna campaña coincide con los filtros']"
    DASHBOARD_JOIN_CAMPAIGN_LINK = "//a[normalize-space(.)='Unirme a una campaña']"
    DASHBOARD_ACTIVE_GROUP_TITLES = "//section[.//h2[normalize-space(.)='Misiones activas']]//h3"
    DASHBOARD_NO_ACTIVE_MISSIONS = "//h3[normalize-space(.)='No tienes misiones activas']"
    DASHBOARD_PROFILE_ERROR_TITLE = "//h3[normalize-space(.)='No se pudo cargar tu impacto']"
    DASHBOARD_PROFILE_ERROR_RETRY = (
        "//section[.//h3[normalize-space(.)='No se pudo cargar tu impacto']]//button[normalize-space(.)='Reintentar']"
    )

    # --- Feed (pages/Feed) ---
    FEED_TITLE = "//h1[normalize-space(.)='Muro Social']"
    FEED_CONTENT_TEXTAREA = "//textarea[@placeholder='¿Qué acción sostenible realizaste hoy?']"
    FEED_PUBLISH_BUTTON = "//button[@type='submit'][normalize-space(.)='Publicar']"
    FEED_ADD_IMAGE_BUTTON = "//button[.//span[normalize-space(.)='Añadir imagen']]"
    FEED_UPLOAD_MODE_BUTTON = "//button[normalize-space(.)='Subir archivo']"
    FEED_URL_MODE_BUTTON = "//button[normalize-space(.)='Enlace URL']"
    FEED_FILE_INPUT = "//input[@type='file']"
    FEED_URL_INPUT = "//input[@type='url']"
    FEED_DROPZONE_HINT = "//p[contains(normalize-space(.), 'Arrastra tu foto de evidencia aquí')]"
    FEED_IMAGE_PREVIEW = "//img[@alt='Previsualización de evidencia']"
    FEED_REMOVE_IMAGE_BUTTON = "//button[@aria-label='Eliminar imagen seleccionada']"
    FEED_FORMAT_ERROR = "//p[normalize-space(.)='Formato no soportado. Usa imágenes JPG, PNG o WebP.']"
    FEED_SIZE_ERROR = "//p[normalize-space(.)='El archivo excede el tamaño máximo permitido de 5 MB.']"
    # Dentro de una tarjeta de post se usan como card.locator("xpath=." + Locs.X).
    FEED_POST_CONTENT = "//p[contains(@class,'whitespace-pre-wrap')]"
    FEED_POST_AUTHOR = "//h3"
    FEED_POST_IMAGE = "//img[@alt='Evidencia']"
    FEED_EDITED_LABEL = "//span[normalize-space(.)='(Editado)']"
    FEED_EDIT_POST_BUTTON = "//button[@title='Editar publicación']"
    FEED_DELETE_POST_BUTTON = "//button[@title='Eliminar publicación']"
    FEED_EDIT_TEXTAREA = "//textarea[not(@placeholder)]"
    FEED_SAVE_EDIT_BUTTON = "//button[normalize-space(.)='Guardar']"

    # --- Notificaciones (pages/Notifications, NotificationToast, BadgeUnlockModal) ---
    NOTIFICATIONS_TITLE = "//h1[normalize-space(.)='Notificaciones']"
    NOTIFICATIONS_SUBTITLE = "//h1[normalize-space(.)='Notificaciones']/following-sibling::p"
    NOTIFICATIONS_ITEM = "//*[@data-slot='card'][.//button[@aria-label='Eliminar notificación']]"
    NOTIFICATIONS_BELL_BADGE = "//*[@aria-label='Notificaciones']//*[contains(@aria-label, 'notificaciones sin leer')]"
    NOTIFICATIONS_TOAST = "//*[@role='status'][@aria-live='polite'][.//button[@aria-label='Cerrar notificación']]"
    NOTIFICATIONS_EMPTY_TEXT = "//p[normalize-space(.)='No tienes notificaciones.']"
    NOTIFICATIONS_ERROR_ALERT = "//*[@role='alert'][normalize-space(.)='No se pudieron cargar las notificaciones.']"
    NOTIFICATIONS_BADGE_DIALOG = "//*[@role='dialog'][.//*[normalize-space(.)='¡Insignia desbloqueada!']]"

    # --- Perfil (pages/Profile) ---
    PROFILE_NAME_TITLE = "//main//h1"

    # --- Locators parametrizables ---
    @staticmethod
    def button_with_text(text: str) -> str:
        return f"//button[contains(normalize-space(.), {_xpath_literal(text)})]"

    @staticmethod
    def menuitem_with_text(text: str) -> str:
        return f"//*[@role='menuitem'][contains(normalize-space(.), {_xpath_literal(text)})]"

    @staticmethod
    def element_with_test_id(test_id: str) -> str:
        return f"[data-testid='{test_id}']"

    @staticmethod
    def heading_with_text(text: str, level: int | None = None) -> str:
        tag = f"h{level}" if level else "*[self::h1 or self::h2 or self::h3 or self::h4 or self::h5 or self::h6]"
        return f"//{tag}[contains(normalize-space(.), {_xpath_literal(text)})]"

    @staticmethod
    def group_with_aria(label: str) -> str:
        return f"//*[@role='group'][@aria-label={_xpath_literal(label)}]"

    @staticmethod
    def link_with_aria(label: str) -> str:
        return f"//*[self::a or @role='link'][@aria-label={_xpath_literal(label)}]"

    @staticmethod
    def element_with_aria(label: str) -> str:
        return f"//*[@aria-label={_xpath_literal(label)}]"

    @staticmethod
    def button_with_aria(label: str) -> str:
        return f"//button[@aria-label={_xpath_literal(label)}]"

    @staticmethod
    def button_with_title(title: str) -> str:
        return f"//button[@title={_xpath_literal(title)}]"

    @staticmethod
    def dialog_with_title(text: str) -> str:
        return f"//*[@role='dialog'][.//*[contains(normalize-space(.), {_xpath_literal(text)})]]"

    @staticmethod
    def status_with_text(text: str) -> str:
        return f"//*[@role='status'][contains(normalize-space(.), {_xpath_literal(text)})]"

    @staticmethod
    def alert_with_text(text: str) -> str:
        return f"//*[@role='alert'][contains(normalize-space(.), {_xpath_literal(text)})]"

    @staticmethod
    def text_exact(text: str) -> str:
        return f"//*[normalize-space(.)={_xpath_literal(text)}]"

    @staticmethod
    def text_contains(text: str) -> str:
        return f"//*[contains(normalize-space(.), {_xpath_literal(text)})]"

    @staticmethod
    def role_with_descendant_text(role: str, text: str) -> str:
        """Element with `role` that contains a descendant whose whole text is `text` (e.g. a card)."""
        return f"//*[@role={_xpath_literal(role)}][.//*[normalize-space(.)={_xpath_literal(text)}]]"

    @staticmethod
    def li_with_text(text: str) -> str:
        return f"//li[.//*[normalize-space(.)={_xpath_literal(text)}]]"

    @staticmethod
    def combobox_with_id(element_id: str) -> str:
        return f"//*[@role='combobox'][@id={_xpath_literal(element_id)}]"

    @staticmethod
    def option_with_text(text: str) -> str:
        return f"//*[@role='option'][normalize-space(.)={_xpath_literal(text)}]"


def _xpath_literal(value: str) -> str:
    """Quote `value` as an XPath string literal, using concat() when it holds both quote kinds."""
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    return "concat(" + ", \"'\", ".join(f"'{part}'" for part in parts) + ")"


Locs = Locators
