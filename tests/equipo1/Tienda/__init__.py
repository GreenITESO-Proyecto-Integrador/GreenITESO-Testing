"""08 · Tienda — /store (alias /shop)

Tests: test_Tienda.py  →  actions: src/actions/Tienda_actions.py
Módulo del equipo 1, probado por el equipo 3 (EE = 01). Usuario propio: TEST_STORE_EMAIL.
Casos del test plan (Notion: GreenITESO — Test Plan):

- TC-08-001 Mostrar el saldo y el catálogo de canjeables
- TC-08-002 Filtrar por categoría
- TC-08-003 Canjear un artículo con puntos suficientes
- TC-08-004 Bloquear el canje sin puntos suficientes
- TC-08-005 Cancelar un canje
- TC-08-006 Mostrar error y reintentar cuando falla el catálogo
- TC-08-007 Abrir la tienda desde la ruta /shop

Casos agregados por el equipo 3 (T3-07 de docs/peer-testing-friday.md):

- TC-08-008 Rechazar el canje repetido de un artículo que ya se tiene
- TC-08-009 La API rechaza el canje sin saldo suficiente
- TC-08-010 Mostrar el estado vacío cuando no hay canjeables
"""
