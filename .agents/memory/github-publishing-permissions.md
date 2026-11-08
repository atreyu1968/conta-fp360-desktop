---
name: Permisos de publicación GitHub
description: Alcances OAuth de GitHub en Replit al publicar código y workflows.
---

Una conexión GitHub puede permitir cambios de código (`repo`) pero no cambios en `.github/workflows` (`workflow`). Volver a autorizarla no garantiza que añada el alcance que falta; una conexión GitHub de control de código puede tener permisos distintos.

**Why:** Un envío de código normal puede funcionar mientras GitHub rechaza el mismo envío por modificar workflows; reintentar la misma conexión no resuelve el alcance ausente.

**How to apply:** Antes de publicar workflows, comprueba los permisos de la conexión. Si falta `workflow`, usa una conexión autorizada que sí lo incluya y actualiza la rama solo después de verificar que el commit nuevo desciende de la punta actual.
