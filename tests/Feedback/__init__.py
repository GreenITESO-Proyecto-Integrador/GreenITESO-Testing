"""16 · Feedback — /feedback (buzón de comentarios del estudiante) y /api/v1/feedback/

Tests: test_Feedback.py  →  actions: src/actions/Feedback_actions.py
Módulo agregado fuera de los 14 del test plan (el 15 es Acceso); EE = 00 es provisional hasta el reparto.

Formulario (sin enviar nada)
- TC-16-001 Abrir el buzón: 5 categorías, 5 calificaciones, historial y envío deshabilitado
- TC-16-002 Habilitar el envío solo con asunto de 1-120 y mensaje de 10-1000 caracteres
- TC-16-003 Limpiar el formulario
- TC-16-004 Elegir, cambiar y quitar la calificación
- TC-16-005 Rechazar un adjunto que no es imagen
- TC-16-006 Rechazar una imagen de más de 5 MB

Envío e historial (crean datos que NO se pueden borrar; solo `full`)
- TC-16-007 Enviar un reporte con categoría y calificación; aparece en el historial y en la API
- TC-16-008 Enviar una idea con captura: vista previa, quitar, adjuntar, enviar y abrir la captura
- TC-16-009 Conservar el historial al recargar, con el más reciente primero

API: permisos y validaciones
- TC-16-010 Responder 400 a mensaje corto, asunto en blanco, categoría desconocida y calificación 6
- TC-16-011 Responder 400 a una captura que no es imagen
- TC-16-012 Mostrar a cada usuario solo sus envíos
- TC-16-013 Dar la captura solo al autor y al admin (403, 404 y 401 en los demás casos)
- TC-16-014 Listar y filtrar como admin (categoría y estado); 400 con filtros inválidos
- TC-16-015 Cambiar estado y nota como admin y verlos el estudiante en su historial
- TC-16-016 Mandar a login a quien no tiene sesión; la API responde 401

Estados que las cuentas reales no alcanzan (mocks, no llegan al backend)
- TC-16-017 Error del historial con "Reintentar"
- TC-16-018 Historial vacío
- TC-16-019 Error al enviar: banner y el formulario conserva lo escrito

Límites que condicionan las pruebas: 10 envíos por hora y usuario (`student` usa 2 por corrida y `leader` 5)
y no hay forma de borrar un envío, así que cada uno lleva el marcador de la corrida.
"""
