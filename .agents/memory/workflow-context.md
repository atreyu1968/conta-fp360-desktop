---
name: Directorio de los servicios gestionados
description: Precaución al ejecutar código importado fuera de la carpeta del artefacto.
---

Los comandos de un servicio gestionado se ejecutan desde el directorio del
artefacto. No asumir que una ruta relativa se resuelve desde la raíz del proyecto.

**Why:** Los comandos pnpm con filtros funcionaban desde ambos directorios y
ocultaban esta diferencia; al servir el PHP original, las rutas relativas
apuntaban a una carpeta inexistente.

**How to apply:** Al cambiar la tecnología de un servicio o conectar código
importado que mantiene su estructura original, resolver sus rutas desde el
directorio real del servicio antes de iniciarlo. No crear un segundo workflow
para suplir la ruta de un servicio ya registrado.
