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

    # --- Perfil (pages/Profile) ---
    PROFILE_NAME_TITLE = "//main//h1"

    # --- Clanes (pages/Clans/Clans.tsx, components/CreateClanDialog.tsx, ClanFormFields.tsx) ---
    CLANS_CREATE_BUTTON = "//button[normalize-space(.)='Crear clan'][not(ancestor::*[@role='dialog'])]"
    CLANS_SEARCH_INPUT = "//input[@aria-label='Buscar clanes por nombre']"
    CREATE_CLAN_DIALOG = "//*[@role='dialog'][.//*[@data-slot='dialog-title'][normalize-space(.)='Crear clan']]"
    CLAN_NAME_INPUT = "//input[@id='clan-name']"
    CLAN_DESCRIPTION_INPUT = "//textarea[@id='clan-description']"
    CLAN_NAME_FIELD_ERROR = "//input[@id='clan-name']/parent::div//p[@role='alert']"
    CLAN_FORM_ALERT = "//*[@role='dialog']//form/p[@role='alert']"
    CLAN_FORM_SUBMIT = "//*[@role='dialog']//button[@type='submit']"
    CLAN_FORM_CANCEL = "//*[@role='dialog']//button[normalize-space(.)='Cancelar']"
    CLAN_SUCCESS_BANNER = "//*[@role='status'][contains(normalize-space(.), 'Creaste')]"
    CLAN_PROFILE_TITLE = "//main//h1"
    CLAN_PROFILE_DISSOLVE_BUTTON = "//button[normalize-space(.)='Disolver clan']"
    CLAN_PROFILE_MEMBER_COUNT = "//main//dd[contains(normalize-space(.), 'miembro')]"
    CLAN_PROFILE_INVITE_CODE_BUTTON = "//button[normalize-space(.)='Invitar con código']"

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
    def badge_with_text(text: str) -> str:
        # El Badge del frontend no tiene data-slot; es un span/div con un icono y el texto.
        return f"//main//*[self::span or self::div][normalize-space(.)='{text}']"

    @staticmethod
    def button_with_text(text: str) -> str:
        return f"//button[contains(normalize-space(.), '{text}')]"

    @staticmethod
    def menuitem_with_text(text: str) -> str:
        return f"//*[@role='menuitem'][contains(normalize-space(.), '{text}')]"

    @staticmethod
    def element_with_test_id(test_id: str) -> str:
        return f"[data-testid='{test_id}']"


Locs = Locators
