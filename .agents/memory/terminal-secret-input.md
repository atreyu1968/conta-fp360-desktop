---
name: Entrada secreta en CLI
description: Lectura de contraseñas ocultas en herramientas de terminal Ubuntu.
---

Para leer una contraseña en una CLI Ubuntu, acceder a `/dev/tty` con `os.open`,
desactivar `termios.ECHO` durante la lectura y restaurar la configuración en
`finally`. Las aperturas de alto nivel como `open("/dev/tty", "r+")` fallan porque
el terminal no es seekable; los fallbacks de lectura con eco no son seguros para
contraseñas.

**Why:** Las pruebas interactivas mostraron que el terminal del sistema no se puede
abrir como un flujo seekable, así que usar una API de alto nivel puede fallar o
llevar a un fallback que revele lo escrito.

**How to apply:** Usa una pseudo-terminal para probar que la contraseña no aparece
en la salida y que el eco se restaura incluso si la lectura falla o se interrumpe.
