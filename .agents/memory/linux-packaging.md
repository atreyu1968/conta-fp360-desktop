---
name: Paquetes Linux Tauri en Replit
description: Diferencia entre compilar paquetes Linux en NixOS de Replit y generar instaladores compatibles con Ubuntu.
---

Compilar una app Tauri dentro del entorno Nix de Replit puede producir un paquete `.deb` con intérprete y bibliotecas bajo `/nix/store`; no debe presentarse como instalador Ubuntu listo para distribuir. El empaquetado AppImage también puede fallar en este entorno aunque las herramientas de escritorio estén instaladas.

**Why:** La compilación local enlazó el ejecutable contra glibc y bibliotecas GTK/WebKit de Nix, y la herramienta AppImage no terminó el bundle. El éxito de Cargo y la creación del `.deb` no demuestran compatibilidad en Ubuntu.

**How to apply:** Para releases Linux, compilar en el runner Ubuntu definido por CI y verificar el paquete allí. Informar por separado de compilación en CI y pruebas en un equipo Ubuntu real.
