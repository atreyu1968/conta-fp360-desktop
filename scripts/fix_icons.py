"""Convierte los iconos PNG a RGBA sin alterar su diseño."""
from pathlib import Path
from PIL import Image
icons=Path(__file__).resolve().parents[1]/'src-tauri/icons'
for name in ['32x32.png','128x128.png','128x128@2x.png','icon.png']:
    path=icons/name
    img=Image.open(path).convert('RGBA')
    img.save(path,format='PNG')
    print(name,img.mode,img.size)
