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

Notas:
- Datos reales: TC-10-001 crea 3 notificaciones CAMPAIGN_REJECTED (S propone una campaña marcada y A
  la rechaza por API). Solo las recibe S. Nunca se aprueba una propuesta: notificaría a todos.
- Todas las aserciones se acotan a las notificaciones cuyo mensaje cita el título marcado.
- TC-10-003 marca como leídas TODAS las notificaciones de S (solo cambia el estado de lectura).
- TC-10-005 depende del socket real: el canal es en memoria, así que requiere una sola instancia en prod.
  Va con reintento (flaky, reruns=1).
- TC-10-006, 007 y 008 mockean GET notifications/ (y el socket en 008); no tocan datos.
- Las notificaciones creadas llevan el marcador de la corrida; la limpieza debe marcarlas como borradas.
"""
