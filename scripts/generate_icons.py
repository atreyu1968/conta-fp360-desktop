#!/usr/bin/env python3
"""Generate the official CONTA FP360 desktop icons from the owner's supplied logo."""
import base64
from pathlib import Path
from PIL import Image
from io import BytesIO

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "branding" / "conta-fp360.png.base64"
image = Image.open(BytesIO(base64.b64decode(source.read_text(encoding="ascii").strip()))).convert("RGBA")
icons = ROOT / "src-tauri" / "icons"
icons.mkdir(parents=True, exist_ok=True)
for size in (32, 128, 256):
    image.resize((size, size), Image.Resampling.LANCZOS).save(icons / f"{size}x{size}.png")
image.resize((256, 256), Image.Resampling.LANCZOS).save(icons / "128x128@2x.png")
image.resize((256, 256), Image.Resampling.LANCZOS).save(
    icons / "icon.ico", format="ICO",
    sizes=[(16,16), (24,24), (32,32), (48,48), (64,64), (128,128), (256,256)])
for edition in ("studio", "aula"):
    destination = ROOT / "web" / edition / "favicon.png"
    image.save(destination)
print("Iconos oficiales generados para Studio, Aula e instaladores.")
