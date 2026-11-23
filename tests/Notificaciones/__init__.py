"""10 · Notificaciones — /notifications

Tests: test_Notificaciones.py  →  actions: src/actions/Notificaciones_actions.py
Casos del test plan (Notion: GreenITESO — Test Plan):

- TC-10-001 Listar las notificaciones con el contador de no leídas
- TC-10-002 Marcar una notificación como leída
- TC-10-003 Marcar todas como leídas
- TC-10-004 Eliminar una notificación
- TC-10-005 Recibir una notificación en tiempo real
- TC-10-006 Mostrar el estado vacío
- TC-10-007 Mostrar error cuando falla la carga
- TC-10-008 Celebrar una insignia nueva
- TC-10-009 Impedir que otro usuario lea o modifique una notificación ajena  [extra: matriz T2-03]

Notas:
- Datos reales: TC-10-001 crea 3 notificaciones CAMPAIGN_REJECTED (S propone una campaña marcada y A
  la rechaza por API). Solo las recibe S. Nunca se aprueba una propuesta: notificaría a todos.
- Todas las aserciones se acotan a las notificaciones cuyo mensaje cita el título marcado.
- TC-10-003 marca como leídas TODAS las notificaciones de S (solo cambia el estado de lectura).
- TC-10-005 depende del socket real: el canal es en memoria, así que requiere una sola instancia en prod.
  Va con reintento (flaky, reruns=1).
- TC-10-006, 007 y 008 mockean GET notifications/ (y el socket en 008); no tocan datos.
- Las notificaciones creadas llevan el marcador de la corrida; la limpieza debe marcarlas como borradas.
- TC-10-009 no está en Notion: cubre T2-03 de docs/peer-testing-friday.md. Crea su propia notificación
  (no reusa N1..N3, que 003 deja leídas) y `leader` intenta PATCH/DELETE por API. Se espera 404 y no 403,
  porque el backend filtra por dueño y no revela que la notificación existe. Al final, S marca la suya como
  leída por la misma ruta (200) como control positivo. Igual que 001, deja una propuesta REJECTED más.
"""
