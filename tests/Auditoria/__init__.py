"""07 · Auditoría (solo admin) — /audit

Tests: test_Auditoria.py  →  actions: src/actions/Auditoria_actions.py
Casos del test plan (Notion: GreenITESO — Test Plan):

- TC-07-001 Abrir el panel de revisión
- TC-07-002 Listar las evidencias pendientes con su foto
- TC-07-003 Aprobar una evidencia
- TC-07-004 Pedir el motivo antes de rechazar una evidencia
- TC-07-005 Aprobar una propuesta de campaña
- TC-07-006 Rechazar una propuesta con motivo
- TC-07-007 Abrir la pestaña de propuestas desde la URL
- TC-07-008 Mostrar estados vacíos y de error

El test _000 es el setup: crea con la API 2 evidencias pendientes (una de campaign_leader, que se aprueba, y una
de store, que se rechaza) y 2 propuestas (de campaign_leader). Cada usuario registra una sola evidencia porque el
límite diario es por usuario y por acción, y el catálogo del CI (catalog_draft.json) tiene una sola acción con foto.
Los tests _001 a _008 cubren TC-07-001 a TC-07-008 en orden.
Cuidado en prod: cada corrida gasta el cupo diario de esa acción con foto de campaign_leader y de store, y
TC-07-005 intercepta el POST de aprobación (aprobar una propuesta global invita a todos los usuarios).
Detalle en src/actions/Auditoria_actions.py.
"""
