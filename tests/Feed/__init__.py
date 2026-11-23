"""09 · Feed (Muro social) — /feed

Tests: test_Feed.py  →  actions: src/actions/Feed_actions.py
Casos del test plan (Notion: GreenITESO — Test Plan):

- TC-09-001 Ver las publicaciones del muro
- TC-09-002 Publicar solo texto
- TC-09-003 Publicar con una imagen desde archivo
- TC-09-004 Publicar con una imagen por URL
- TC-09-005 Rechazar un archivo inválido o muy grande
- TC-09-006 Quitar la imagen antes de publicar
- TC-09-007 Editar una publicación propia
- TC-09-008 Eliminar una publicación propia
- TC-09-009 Ocultar editar y eliminar en publicaciones de otros
- TC-09-010 Impedir que otro usuario edite o borre una publicación ajena  [extra: matriz T2-06]
- TC-09-011 Mantener el like al recargar  [extra: matriz T2-07]
- TC-09-012 Filtrar publicaciones por tipo (Todos, Evidencias, Anuncios)  [extra: FeedFilters]
- TC-09-013 Ordenar publicaciones por Populares y volver a Recientes  [extra: FeedFilters]
- TC-09-014 Publicar con filtro activo muestra aviso y 'Ver en Todos' lo muestra  [extra: FeedFilters]
- TC-09-015 Mostrar estados vacío y de error al cargar el muro  [extra: FeedFilters]

Notas de implementación:

- TC-09-001 crea la publicación compartida de A (admin, por API) que usan 001 y 009. Los demás
  tests crean sus propias publicaciones con `unique_name`, y la limpieza las borra al final.
- Las publicaciones con imagen (003, 004, 006) son solo `full`: suben archivos reales a prod.
  La imagen de 003 es un PNG de 1x1 generado en memoria; la de 004 es el favicon del propio frontend.
- La subida va a `/api/v1/uploads/` (frontend y backend coinciden). Borrar una publicación también
  borra su imagen (`feed/images.py`), así que no hace falta limpieza aparte de las imágenes.
- Los kudos (`PostLike`) se borran en cascada con su publicación. Solo TC-09-011 da (y quita) un kudo.
- Validación de archivos en el cliente (`lib/api/upload.ts`): solo tipo y tamaño. 005 comprueba
  además que nada llegue al servidor.
- 007 comprueba '(Editado)', que el frontend muestra solo si `updated_at - created_at > 3 s`.
  Como 002 y 007 están separados por otros tests, siempre se cumple.
- Sin mocks: todo el módulo pega a la API real.
- TC-09-010 y 011 no están en Notion: cubren T2-06 y T2-07 de docs/peer-testing-friday.md.
  El usuario ajeno es `leader` y no `admin`, porque el admin sí puede borrar posts de otros (moderación).
- TC-09-011: S da like a un post de `leader`, recarga, lo quita y recarga. El backend avisa al autor
  una vez ('Nuevo like', sin marcador), así que `leader` se queda con esa notificación; los likes se
  borran en cascada con el post.
"""
