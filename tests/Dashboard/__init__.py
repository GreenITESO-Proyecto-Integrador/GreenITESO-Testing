"""03 · Dashboard — / (alias /home)

Tests: test_Dashboard.py  →  actions: src/actions/Dashboard_actions.py
Casos del test plan (Notion: GreenITESO — Test Plan):

- TC-03-001 Mostrar las métricas de "Tu impacto"
- TC-03-002 Mostrar la tendencia de las últimas 4 semanas
- TC-03-003 Mostrar el progreso de las misiones activas
- TC-03-004 Filtrar "Mis campañas" por estado y alcance
- TC-03-005 Mostrar los estados vacíos para un usuario nuevo
- TC-03-006 Mostrar el dashboard simple al admin
- TC-03-007 Mostrar error cuando falla la carga de datos

Notas:
- Módulo de solo lectura: no crea datos.
- Datos reales (sin mock): TC-03-001 a TC-03-004 y TC-03-006. Comparan el DOM contra la respuesta
  que la propia UI consumió (capture_json_response), así no dependen de lo que escriben otros módulos.
- Mocks: TC-03-005 (profile/me/ en cero, impact-trend en cero, campañas vacías) y TC-03-007
  (profile/me/ con error 500, luego se restaura y se pulsa 'Reintentar').
- Los TC 003 y 004 se adaptan a la cantidad de campañas de la cuenta de prueba, incluido cero.
"""
