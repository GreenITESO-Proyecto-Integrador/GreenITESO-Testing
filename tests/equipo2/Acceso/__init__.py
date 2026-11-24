"""15 · Acceso (Equipo 2: identidad y acceso, probado por el Equipo 1) — API /api/v1/auth/ + rutas por rol

Tests: test_Acceso.py  →  actions: src/actions/Acceso_actions.py
Casos (matriz de peer testing: T1-02, T1-03, T1-04):

401 vs 403
- TC-15-001 Responder 401 con WWW-Authenticate cuando no se manda token
- TC-15-002 Responder 401 token_not_valid con un token malformado o con la firma alterada
- TC-15-003 Responder 403 (no 401) a un estudiante con sesión válida en endpoints de admin
- TC-15-004 Permitir al admin el endpoint de admin (control positivo)
- TC-15-017 Negar al estudiante (403) los datos de los paneles: cola de auditoría, evidencias, buzón de
  feedback e historial de roles y baneos
- TC-15-018 Negar al estudiante (403) las operaciones de admin: cambiar roles, banear/desbanear y
  aprobar/rechazar propuestas (sobre ids aleatorios: aunque el permiso fallara, no cambia nada)

Tokens JWT (ningún caso canjea ni revoca un refresh token real)
- TC-15-005 Rechazar un refresh inválido con 401 y uno ausente con 400
- TC-15-006 Rechazar el logout con un refresh inválido (401)
- TC-15-007 Rechazar un refresh token usado como Bearer (401 token_not_valid)
- TC-15-008 Rechazar un access token en /auth/refresh/ y /auth/logout/ sin invalidarlo
- TC-15-009 Validar los claims del access token (tipo, duración de 60 min y usuario)

Sesión en el frontend
- TC-15-010 Mandar a login y limpiar la sesión cuando la renovación falla
- TC-15-011 Limpiar el sessionStorage al cerrar sesión y no regresar con "atrás"
- TC-15-012 Mandar Authorization: Bearer en las llamadas del frontend al API

Roles y rutas
- TC-15-013 Bloquear /audit, /audit?tab=proposals, /admin/users y /admin/feedback al estudiante
- TC-15-014 Ocultar los links de administración al estudiante
- TC-15-015 Abrir las mismas rutas de administración como admin y ver sus links (control positivo)
- TC-15-019 Ocultar el botón "Panel de Auditoría" de /home al estudiante
- TC-15-016 Rechazar en el API (403) a un estudiante que se pone rol ADMIN en el navegador
"""
