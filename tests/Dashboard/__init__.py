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
- TC-03-008 Recuperarse de un error al cargar la tendencia
- TC-03-009 Recuperarse de errores al cargar campañas y misiones
- TC-03-010 Abrir el detalle de una campaña participante
- TC-03-011 Mantener las métricas reales después de recargar
- TC-03-012 Mostrar el dashboard sin desbordamiento horizontal en móvil

Notas:
- Módulo de solo lectura: no crea datos.
- Datos reales (sin mock): TC-03-001 a TC-03-004 y TC-03-006. Comparan el DOM contra la respuesta
  que la propia UI consumió (capture_json_response), así no dependen de lo que escriben otros módulos.
- Datos reales adicionales: TC-03-010 y TC-03-011.
- Mocks: TC-03-005 (perfil, tendencia y campañas vacías), TC-03-007 (profile/me/ con error 500),
  TC-03-008 (impact-trend con error 500) y TC-03-009 (lista de campañas participante con error 500).
- Los mocks TC-03-007 a TC-03-009 se restauran antes de pulsar 'Reintentar'.
- Los TC 003 y 004 se adaptan a la cantidad de campañas de la cuenta de prueba, incluido cero.
"""
