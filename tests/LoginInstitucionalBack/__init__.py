"""01 · Login institucional (ID01, "Identidad 1"), lado backend — POST /api/v1/auth/login/

Tests: test_LoginInstitucionalBack.py  →  actions: src/actions/LoginInstitucionalBack_actions.py
Complementa a tests/Auth/. Solo corre con AUTH_MODE=mock (usa el proveedor mock del backend).

- 101 Primer login: crea la cuenta (STUDENT), access y refresh, sin password ni microsoft_oid
- 102 Segundo login: misma cuenta, correo normalizado a minúsculas
- 103 Rechazar otros dominios y subdominios (403 DOMAIN_NOT_ALLOWED)
- 104 Peticiones inválidas: 400 con un id_token demasiado largo, 401 con uno inválido
- 105 Datos del directorio: nombres, rol por puesto, no bajar de STAFF sin puesto
- 106 Nunca quitar el rol ADMIN
- 107 Reactivar una cuenta que se desactivó sola

Hallazgos (xfail estricto, fallan mientras exista el problema):

- 151 [alta, DehBarca] El login pisa el rol STAFF que asignó un admin
- 152 [media, DehBarca] "Alumno Asistente de Profesor" queda como STAFF
- 153 [baja, Pardosito] El filtro de dominio acepta "a@gmail.com@iteso.mx"

Los hallazgos 3 (correo único sin distinguir mayúsculas en la BD) y 4 (grupos de Graph cortados
después de 3 páginas) no se pueden reproducir desde la API y quedan documentados, sin test.
"""
