"""Normaliza los iconos de Tauri 2 para Windows, Linux y macOS.

El ICO original incluía imágenes PNG no RGBA que impiden generar
los paquetes .app de macOS, aunque los PNG independientes fueran válidos.
"""
from pathlib import Path
from PIL import Image

icons = Path(__file__).resolve().parents[1] / 'src-tauri' / 'icons'
names = ['32x32.png', '128x128.png', '128x128@2x.png', 'icon.png']
for name in names:
    path = icons / name
    if path.exists():
        img = Image.open(path).convert('RGBA')
        img.save(path, format='PNG')
        print(name, img.mode, img.size)

source = icons / '128x128@2x.png'
if not source.exists():
    source = icons / '128x128.png'
with Image.open(source) as inp:
    src = inp.convert('RGBA')
    src.save(icons / 'icon.ico', format='ICO',
             sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                    (128, 128), (256, 256)])
    # macOS utiliza preferentemente ICNS, sin reinterpretar el contenedor ICO.
    try:
        src.save(icons / 'icon.icns', format='ICNS')
    except Exception as exc:
        print('Aviso: ICNS no generado:', exc)
print('Icono ICO regenerado con imágenes RGBA.')
