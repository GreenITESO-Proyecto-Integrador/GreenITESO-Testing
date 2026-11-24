"""04 · Campañas — /campaigns

Tests: test_Campanas.py  →  actions: src/actions/Campanas_actions.py
Casos del test plan (Notion: GreenITESO — Test Plan):

- TC-04-001 Listar las campañas y abrir su detalle
- TC-04-002 Filtrar campañas por estado y alcance
- TC-04-003 Unirse a una campaña en promoción
- TC-04-004 Proponer una campaña global
- TC-04-005 Validar los campos obligatorios del formulario de campaña
- TC-04-006 Crear una campaña privada como líder de clan
- TC-04-007 Impedir que alguien que no es líder cree una campaña de clan
- TC-04-008 Crear una campaña global como admin
- TC-04-009 Editar una campaña en promoción y agregarle una misión
- TC-04-010 Bloquear la edición de una campaña que ya salió de promoción
- TC-04-011 Impedir que el admin se una a una campaña
- TC-04-012 Mostrar error y reintentar cuando falla la lista de campañas
- TC-04-013 Iniciar una campaña en promoción
- TC-04-014 Finalizar una campaña activa
- TC-04-015 Cancelar el inicio de una campaña

Notas de ejecución:

- Prerrequisito: el usuario `campaign_leader` (TEST_CAMPAIGN_LEADER_EMAIL) es una cuenta real de
  @iteso.mx con login manual hecho (`--role campaign_leader`) y onboarding completo. Es su propio
  líder porque el backend permite un solo liderazgo por usuario (BR-04).
- Setup en `test_00_04_000_checkSetupCampaigns` (no en `_001`, para que los TC mantengan su número):
  si L ya lidera un clan privado (en prod, am720371 lidera "Mi Clan PM"), se reusa; si no, L crea
  un clan PÚBLICO marcado. S se une si no es miembro y L crea la campaña A (privada, mañana, 1 misión).
  La unión de S a un clan reusado se registra con `register_membership` y la limpieza lo saca al final.
- Orden de dependencias: 009 depende de 006 (edita B), 013 de 006 y 009 (inicia B), 014 de 013 (finaliza B).
- Mocks (solo estos dos; el resto pega al backend real):
  - TC-04-008 intercepta `POST **/api/v1/campaigns/` con un 201 falso y revisa el body
    (scope GLOBAL, sin target_clan, misiones). Así no se crea una campaña global real, que
    notificaría a todos los usuarios.
  - TC-04-012 simula un 500 en el listado `GET **/api/v1/campaigns/?*` y lo restaura antes de reintentar.
- Datos reales que se crean: el clan (solo si L no lideraba uno), la inscripción temporal de S, la campaña A (PRIVATE), la campaña B
  (PRIVATE, editada e iniciada/finalizada), la campaña C (PRIVATE, iniciada por API) y la propuesta
  global de S (queda PENDIENTE; la limpieza la rechaza y solo notifica a S).
- Notificaciones reales: las invitaciones (CAMPAIGN_INVITE) llegan a los miembros del clan. Con un
  clan nuevo es solo S; con el clan reusado también llegan a sus otros miembros (aceptado por el equipo),
  y esas notificaciones no se limpian. Las campañas A/B/C finalizadas quedan en el historial de ese clan.
  Iniciar o finalizar B/C notifica solo a sus participantes (L).
"""
