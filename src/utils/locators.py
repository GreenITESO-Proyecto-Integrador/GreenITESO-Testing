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
    DASHBOARD_MY_CAMPAIGN_CARD = (
        "//section[.//h2[normalize-space(.)='Mis campañas']]"
        "//*[@role='button'][.//*[@data-slot='card-title']]"
    )
    DASHBOARD_MY_CAMPAIGN_CARD_TITLE = (
        "//section[.//h2[normalize-space(.)='Mis campañas']]//*[@role='button']//*[@data-slot='card-title']"
    )
    DASHBOARD_CAMPAIGNS_PAGINATION = "//nav[@aria-label='Paginación de campañas']"
    DASHBOARD_CAMPAIGNS_ERROR_TITLE = "//h3[normalize-space(.)='No se pudieron cargar tus campañas']"
    DASHBOARD_MISSIONS_ERROR_TITLE = "//h3[normalize-space(.)='No se pudieron cargar tus misiones']"
    DASHBOARD_CAMPAIGNS_RETRY = (
        "//section[.//h3[normalize-space(.)='No se pudieron cargar tus campañas']]"
        "//button[normalize-space(.)='Reintentar']"
    )
    DASHBOARD_TREND_ERROR_TITLE = "//h3[normalize-space(.)='No se pudo cargar tu tendencia']"
    DASHBOARD_TREND_ERROR_RETRY = (
        "//section[.//h3[normalize-space(.)='No se pudo cargar tu tendencia']]"
        "//button[normalize-space(.)='Reintentar']"
    )
    DASHBOARD_CAMPAIGN_DETAIL_DIALOG = "//*[@role='dialog'][.//h2]"
    DASHBOARD_EMPTY_CAMPAIGNS = "//h3[normalize-space(.)='Aún no participas en campañas']"
    DASHBOARD_NO_FILTER_MATCH = "//h3[normalize-space(.)='Ninguna campaña coincide con los filtros']"
    DASHBOARD_JOIN_CAMPAIGN_LINK = "//a[normalize-space(.)='Unirme a una campaña']"
    DASHBOARD_ACTIVE_MISSIONS_TITLE = "//h2[normalize-space(.)='Misiones activas']"
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
    # aria-label "Like, N like(s)" y aria-pressed (FeedPost.tsx)
    FEED_LIKE_BUTTON = "//button[starts-with(@aria-label, 'Like, ')]"
    FEED_TYPE_FILTER_GROUP_LABEL = "Filtrar por tipo de publicación"
    FEED_ORDER_FILTER_GROUP_LABEL = "Ordenar publicaciones"
    FEED_TYPE_PRESSED_CHIP = (
        "//*[@role='group'][@aria-label='Filtrar por tipo de publicación']//button[@aria-pressed='true']"
    )
    FEED_ORDER_PRESSED_CHIP = "//*[@role='group'][@aria-label='Ordenar publicaciones']//button[@aria-pressed='true']"
    FEED_HIDDEN_POST_BANNER = (
        "//*[@role='status'][contains(normalize-space(.), 'no aparece con el filtro u orden que tienes activo')]"
    )
    FEED_EMPTY_TEXT = (
        "//p[normalize-space(.)='No hay publicaciones por mostrar. ¡Sé el primero en compartir tu impacto!']"
    )
    FEED_LOAD_ERROR = "//*[normalize-space(.)='Error al cargar el muro social.']"

    # --- Notificaciones (pages/Notifications, NotificationToast, BadgeUnlockModal) ---
    NOTIFICATIONS_TITLE = "//h1[normalize-space(.)='Notificaciones']"
    NOTIFICATIONS_SUBTITLE = "//h1[normalize-space(.)='Notificaciones']/following-sibling::p"
    NOTIFICATIONS_ITEM = "//*[@data-slot='card'][.//button[@aria-label='Eliminar notificación']]"
    NOTIFICATIONS_BELL_BADGE = "//*[@aria-label='Notificaciones']//*[contains(@aria-label, 'notificaciones sin leer')]"
    NOTIFICATIONS_TOAST = "//*[@role='status'][@aria-live='polite'][.//button[@aria-label='Cerrar notificación']]"
    NOTIFICATIONS_EMPTY_TEXT = "//p[normalize-space(.)='No tienes notificaciones.']"
    NOTIFICATIONS_ERROR_ALERT = "//*[@role='alert'][normalize-space(.)='No se pudieron cargar las notificaciones.']"
    NOTIFICATIONS_BADGE_DIALOG = "//*[@role='dialog'][.//*[normalize-space(.)='¡Insignia desbloqueada!']]"

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

    # --- Catálogo de acciones (pages/ActionCatalog) ---
    CATALOG_TITLE = "//main//h1[normalize-space(.)='Catálogo de acciones']"
    CATALOG_LOADING = "//*[@role='status'][contains(normalize-space(.), 'Cargando catálogo')]"
    CATALOG_CARD = "//main//ul/li//*[@data-slot='card']"
    CATALOG_CARD_TITLE = "//main//ul/li//*[@data-slot='card-title']"
    CATALOG_CARD_POINTS = "//main//ul/li//*[@data-slot='card']//span[contains(normalize-space(.), ' pts')]"
    CATALOG_NO_IMPACT_NOTICE = (
        "//main//ul/li//*[@data-slot='card'][contains(normalize-space(.), 'Impacto ambiental pendiente de calibrar')]"
    )
    CATALOG_EMPTY_TITLE = "//main//h2[normalize-space(.)='No hay acciones activas']"
    CATALOG_ERROR_TITLE = "//main//h2[normalize-space(.)='No se pudo cargar el catálogo']"
    CATALOG_RETRY_BUTTON = "//main//button[normalize-space(.)='Reintentar']"
    # Relativos a una tarjeta (card.locator(Locs.X)); llevan "xpath=" como los de Tienda.
    CATALOG_CARD_DESCRIPTION = "xpath=.//p[contains(@class,'text-sm')][not(ancestor::button)]"
    CATALOG_CARD_EXPAND_BUTTON = "xpath=.//button[starts-with(normalize-space(.),'Ver más')]"
    CATALOG_CARD_COLLAPSE_BUTTON = "xpath=.//button[starts-with(normalize-space(.),'Ver menos')]"

    @staticmethod
    def catalog_card_with_name(name: str) -> str:
        """Tarjeta del catálogo cuyo título contiene `name`."""
        return f"//main//ul/li//*[@data-slot='card'][.//*[@data-slot='card-title'][contains(normalize-space(.), '{name}')]]"

    # --- Perfil (pages/Profile) ---
    PROFILE_HEADER = "//header[.//h1]"
    PROFILE_NAME_TITLE = "//main//h1"
    PROFILE_ROLE_BADGE = "//header//span[contains(@class,'rounded-full')]"
    PROFILE_EMAIL = "//header//p[contains(@class,'text-muted-foreground')]"
    PROFILE_AVATAR = "//header//div[contains(@class,'size-20') or contains(@class,'size-24')]"
    PROFILE_EDIT_BUTTON = "//button[normalize-space(.)='Editar perfil']"

    # Métricas de impacto acumulado
    PROFILE_IMPACT_SECTION = "//section[@aria-labelledby='impacto-title']"
    PROFILE_IMPACT_TITLE = "//*[@id='impacto-title']"
    PROFILE_METRIC_CO2 = "//section[@aria-labelledby='impacto-title']//div[.//p[contains(text(),'CO₂ Evitado')]]"
    PROFILE_METRIC_WATER = "//section[@aria-labelledby='impacto-title']//div[.//p[contains(text(),'Agua Ahorrada')]]"
    PROFILE_METRIC_PLASTIC = (
        "//section[@aria-labelledby='impacto-title']//div[.//p[contains(text(),'Plástico Reciclado')]]"
    )

    # Progreso y nivel
    PROFILE_PROGRESS_SECTION = "//section[@aria-labelledby='progreso-title']"
    PROFILE_PROGRESS_TITLE = "//*[@id='progreso-title']"
    PROFILE_POINTS_TOTAL = (
        "//section[@aria-labelledby='progreso-title']//div[.//p[normalize-space(.)='Puntos Totales']]"
    )
    PROFILE_POINTS_AVAILABLE = (
        "//section[@aria-labelledby='progreso-title']//div[.//p[normalize-space(.)='Disponibles']]"
    )
    PROFILE_STREAK = "//section[@aria-labelledby='progreso-title']//div[.//p[contains(text(),'Racha')]]"
    PROFILE_LEVEL = "//section[@aria-labelledby='progreso-title']//div[.//p[contains(text(),'Nivel')]]"

    # Modal editar perfil (EditProfileDialog)
    PROFILE_EDIT_DIALOG = "//*[@role='dialog'][.//*[normalize-space(.)='Editar perfil']]"
    PROFILE_EDIT_AVATAR_PREVIEW = "//*[@role='dialog']//img[@alt='Previsualización']"
    PROFILE_EDIT_AVATAR_FILE = "//*[@data-testid='profile-avatar-file']"
    PROFILE_EDIT_UPLOAD_BUTTON = (
        "//*[@role='dialog']//button[.//span[normalize-space(.)='Subir foto'] or normalize-space(.)='Subir foto']"
    )
    PROFILE_EDIT_LINK_BUTTON = "//*[@role='dialog']//button[contains(normalize-space(.),'Usar un enlace')]"
    PROFILE_EDIT_AVATAR_URL_INPUT = "//input[@id='profile-avatar-url']"
    PROFILE_EDIT_REMOVE_AVATAR_BUTTON = (
        "//*[@role='dialog']//button[.//span[normalize-space(.)='Quitar'] or normalize-space(.)='Quitar']"
    )
    PROFILE_EDIT_BIO_INPUT = "//textarea[@id='profile-bio']"
    PROFILE_EDIT_SAVE_BUTTON = "//*[@role='dialog']//button[normalize-space(.)='Guardar cambios']"
    PROFILE_EDIT_CANCEL_BUTTON = "//*[@role='dialog']//button[normalize-space(.)='Cancelar']"
    PROFILE_EDIT_SUCCESS_ALERT = (
        "//*[@role='alert'][contains(normalize-space(.), '¡Perfil actualizado correctamente!')]"
    )
    PROFILE_EDIT_ERROR_ALERT = (
        "//*[@role='alert'][not(contains(normalize-space(.), '¡Perfil actualizado correctamente!'))]"
    )

    # Onboarding / Nickname
    ONBOARDING_MODAL = "//*[@role='dialog'][.//*[normalize-space(.)='Completa tu perfil'] or .//*[contains(normalize-space(.), 'Elige tu carrera')]]"
    ONBOARDING_NICKNAME_INPUT = "//input[@id='onboarding-nickname']"
    ONBOARDING_SUBMIT_BUTTON = (
        "//*[@role='dialog']//button[normalize-space(.)='Continuar' or normalize-space(.)='Comenzar']"
    )

    # --- Clanes (pages/Clans/Clans.tsx, components/CreateClanDialog.tsx, ClanFormFields.tsx) ---
    CLANS_CREATE_BUTTON = "//button[normalize-space(.)='Crear clan'][not(ancestor::*[@role='dialog'])]"
    CLANS_SEARCH_INPUT = "//input[@aria-label='Buscar clanes por nombre']"
    CLANS_DIRECTORY_NEXT = (
        "//nav[@aria-label='Paginación de clanes']//button[@aria-label='Página siguiente']"
    )
    CREATE_CLAN_DIALOG = "//*[@role='dialog'][.//*[@data-slot='dialog-title'][normalize-space(.)='Crear clan']]"
    CLAN_NAME_INPUT = "//input[@id='clan-name']"
    CLAN_DESCRIPTION_INPUT = "//textarea[@id='clan-description']"
    CLAN_NAME_FIELD_ERROR = "//input[@id='clan-name']/parent::div//p[@role='alert']"
    CLAN_FORM_ALERT = "//*[@role='dialog']//form/p[@role='alert']"
    CLAN_FORM_SUBMIT = "//*[@role='dialog']//button[@type='submit']"
    CLAN_FORM_CANCEL = "//*[@role='dialog']//button[normalize-space(.)='Cancelar']"
    CLAN_SUCCESS_BANNER = "//*[@role='status'][contains(normalize-space(.), 'Creaste')]"
    CLAN_PROFILE_TITLE = "//main//h1"
    CLAN_PROFILE_DISSOLVE_BUTTON = "//button[normalize-space(.)='Disolver clan'][not(ancestor::*[@role='dialog'])]"
    CLAN_PROFILE_MEMBER_COUNT = "//main//dd[contains(normalize-space(.), 'miembro')]"
    CLAN_PROFILE_INVITE_CODE_BUTTON = "//button[normalize-space(.)='Invitar con código']"
    CLANS_JOIN_CODE_BUTTON = "//button[normalize-space(.)='Tengo una invitación']"
    CLAN_JOIN_BUTTON = "//button[normalize-space(.)='Unirme al clan'][not(ancestor::*[@role='dialog'])]"
    CLAN_REQUEST_JOIN_BUTTON = "//button[normalize-space(.)='Solicitar unirme']"
    CLAN_LEAVE_BUTTON = "//button[normalize-space(.)='Salir del clan'][not(ancestor::*[@role='dialog'])]"
    CLAN_SET_ACTIVE_BUTTON = "//button[normalize-space(.)='Establecer como clan activo']"
    CLAN_ACTIVE_BADGE = "//span[contains(normalize-space(.), 'Es tu clan activo')]"
    CLAN_COPY_LINK_BUTTON = "//button[normalize-space(.)='Copiar enlace de invitación']"
    CLAN_TRANSFER_BUTTON = "//button[normalize-space(.)='Transferir liderazgo'][not(ancestor::*[@role='dialog'])]"
    CLAN_TRANSFER_TRIGGER = "//*[@id='transfer-successor']"
    CLAN_INVITE_CODE_INPUT = "//input[@id='clan-invite-code']"
    CLAN_NOTICE = "//*[@role='status']"
    CLAN_DIALOG_ALERT = "//*[@role='dialog']//p[@role='alert']"
    CLAN_DIRECTORY_ERROR_TITLE = "//h3[normalize-space(.)='No se pudieron cargar los clanes']"
    CLANS_DIRECTORY_RETRY = (
        "//h3[normalize-space(.)='No se pudieron cargar los clanes']"
        "/following::button[normalize-space(.)='Reintentar'][1]"
    )
    CLAN_EMPTY_SEARCH_TITLE = "//h3[normalize-space(.)='Sin resultados']"
    CLAN_NOT_FOUND_TITLE = "//h2[normalize-space(.)='No encontramos este clan']"
    CLAN_REQUEST_SENT_TITLE = "//h2[normalize-space(.)='Solicitud enviada']"
    CLAN_CAMPAIGNS_TITLE = "//h2[@id='clan-campaigns-title']"
    CLAN_CAMPAIGNS_EMPTY_TITLE = "//h3[normalize-space(.)='Sin campañas activas']"
    CLAN_REQUESTS_EMPTY = "//p[normalize-space(.)='No hay solicitudes pendientes.']"
    CLAN_ACCEPT_REQUEST_BUTTON = "//button[starts-with(@aria-label, 'Aceptar solicitud de ')]"
    CLAN_REJECT_REQUEST_BUTTON = "//button[starts-with(@aria-label, 'Rechazar solicitud de ')]"
    # --- Tienda (pages/Store) ---
    STORE_TITLE = "//main//h1[normalize-space(.)='Tienda de canjeables']"
    STORE_BALANCE = "//section[@aria-label='Puntos disponibles para canje']//span[contains(@class,'text-3xl')]"
    STORE_FILTER_GROUP_LABEL = "Filtrar por categoría"  # aria-label del grupo, para click_filter_chip
    STORE_FILTER_GROUP = "//*[@role='group'][@aria-label='Filtrar por categoría']"
    STORE_FILTER_PRESSED_CHIP = "//*[@role='group'][@aria-label='Filtrar por categoría']//button[@aria-pressed='true']"
    STORE_CARD = "//main//*[@data-slot='card'][.//h3]"
    STORE_CARD_NAMES = "//main//*[@data-slot='card']//h3"
    # Relativos a una tarjeta (card.locator(Locs.X)); llevan "xpath=" como los de Dashboard.
    STORE_CARD_CATEGORY = "xpath=.//span[contains(@class,'left-2')]"
    STORE_CARD_REDEEM_BUTTON = "xpath=.//button[starts-with(normalize-space(.),'Canjear')]"
    STORE_CARD_REDEEMED_BUTTON = "xpath=.//button[normalize-space(.)='Canjeado']"
    STORE_CARD_OWNED_BADGE = "xpath=.//span[normalize-space(.)='Obtenido']"
    STORE_LOADING = "//main//*[@role='status'][.//*[contains(@class,'animate-pulse')]]"
    STORE_ERROR_TITLE = "//main//h2[normalize-space(.)='No se pudieron cargar los canjeables']"
    STORE_ERROR_SECTION = "//section[.//h2[normalize-space(.)='No se pudieron cargar los canjeables']]"
    STORE_RETRY_BUTTON = STORE_ERROR_SECTION + "//button[normalize-space(.)='Reintentar']"
    STORE_EMPTY_TITLE = "//main//h2[normalize-space(.)='No hay canjeables disponibles']"
    STORE_NO_MATCH_TEXT = "//main//p[normalize-space(.)='Ningún artículo coincide con la categoría seleccionada.']"
    STORE_CONFIRM_DIALOG = "//*[@role='dialog'][.//*[normalize-space(.)='Confirmar Canje de Artículo']]"
    STORE_CONFIRM_BUTTON = "//*[@role='dialog']//button[normalize-space(.)='Confirmar Canje']"
    STORE_CANCEL_BUTTON = "//*[@role='dialog']//button[normalize-space(.)='Cancelar']"
    STORE_DIALOG_ITEM_NAME = "//*[@role='dialog']//h4"
    STORE_TOAST_TITLE = "//div[contains(@class,'fixed')]//h5"
    STORE_TOAST_DESCRIPTION = "//div[contains(@class,'fixed')]//h5/following-sibling::p"

    # --- Locators parametrizables ---
    @staticmethod
    def clan_privacy_chip_with_text(text: str) -> str:
        return f"//*[@role='group'][@aria-label='Privacidad del clan']//button[normalize-space(.)='{text}']"

    @staticmethod
    def char_counter_with_text(text: str) -> str:
        return f"//p[@aria-hidden='true'][normalize-space(.)='{text}']"

    @staticmethod
    def clan_card_with_name(name: str) -> str:
        return f"//a[contains(@href, '/clans/')][.//h3[normalize-space(.)='{name}']]"

    @staticmethod
    def dialog_button_with_text(text: str) -> str:
        return f"//*[@role='dialog']//button[normalize-space(.)='{text}']"

    @staticmethod
    def member_count_with_text(text: str) -> str:
        return f"//main//dd[normalize-space(.)='{text}']"

    @staticmethod
    def badge_with_text(text: str) -> str:
        # El Badge del frontend no tiene data-slot; es un span/div con un icono y el texto.
        return f"//main//*[self::span or self::div][normalize-space(.)='{text}']"

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

    @staticmethod
    def store_card_with_name(name: str) -> str:
        """Card of the store whose title (h3) is exactly `name`."""
        return f"//main//*[@data-slot='card'][.//h3[normalize-space(.)={_xpath_literal(' '.join(name.split()))}]]"

    @staticmethod
    def store_dialog_value(label: str) -> str:
        """Value of a row of the points breakdown in the confirm dialog (e.g. 'Tus puntos disponibles:')."""
        return f"//*[@role='dialog']//div[span[normalize-space(.)={_xpath_literal(label)}]]/span[2]"

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


def _xpath_literal(value: str) -> str:
    """Quote `value` as an XPath string literal, using concat() when it holds both quote kinds."""
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    return "concat(" + ', "\'", '.join(f"'{part}'" for part in parts) + ")"


Locs = Locators
