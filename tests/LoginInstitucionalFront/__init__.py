"""01 · Login institucional (ID01, "Identidad 1"), lado frontend — /login

Tests: test_LoginInstitucionalFront.py  →  actions: src/actions/LoginInstitucionalFront_actions.py
Complementa a tests/Auth/ (que ya revisa título, botón, aviso y /profile → /login).
La ida a Microsoft se intercepta y se cancela: no necesita cuenta real.

- 201 /login sin campos de correo/contraseña, sin errores y sin llamar al backend al abrir
- 202 Redirect a Microsoft: client_id, regreso a /login del mismo origen, sin client_secret
- 203 Redirect a Microsoft: response_type=code, PKCE S256 y permiso User.Read
- 204 Sin sesión, /clans y /admin/users mandan a /login

Los hallazgos del front (errores del login en inglés, 429 sin explicar, código DOMAIN_NOT_ALLOWED
perdido, "Malformed login response") necesitan completar el regreso de Microsoft, así que quedan
documentados y sin test automatizado en este repo.
"""
