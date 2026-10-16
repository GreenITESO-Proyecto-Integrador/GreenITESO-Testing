"""Locators reutilizables (XPath/CSS) para la UI de GreenITESO.

- Locators fijos: constantes en MAYÚSCULAS dentro de la clase.
- Locators parametrizables: @staticmethod que reciben el texto/atributo y regresan el selector.
"""


class Locators:
    """Collection of XPath/CSS helpers for the GreenITESO UI."""

    # --- Locators fijos (llenar conforme se conozca la UI) ---
    # LOGIN_BUTTON = "//button[@type='submit']"

    # --- Locators parametrizables ---
    @staticmethod
    def button_with_text(text: str) -> str:
        return f"//button[contains(normalize-space(.), '{text}')]"

    @staticmethod
    def element_with_test_id(test_id: str) -> str:
        return f"[data-testid='{test_id}']"


Locs = Locators
