"""Põe uma pasta de fotografias na app como coleção: app/src/main/assets/colecoes/<nome>/.

Uso (na raiz do repositório):
    python app-android/tools/importar_colecao.py <pasta> [nome]      # nome por omissão: o da pasta
    python app-android/tools/importar_colecao.py --teste

Cada fotografia fica endireitada pela rotação EXIF (o telemóvel grava as verticais deitadas e marca a rotação no
EXIF, que o Unity ignora), em RGB, com o lado maior <= 1280 px e em JPEG, com o nome foto_NN.jpg pela ordem do nome
original. Requer Pillow.
"""

import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

ASSETS = Path(__file__).resolve().parent.parent / "app" / "src" / "main" / "assets" / "colecoes"
MAX_PX = 1280
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic"}


def importar(src: Path, dst: Path) -> int:
    fotos = sorted(p for p in src.iterdir() if p.suffix.lower() in EXTS)
    if not fotos:
        sys.exit(f"{src}: sem fotografias")
    if dst.exists():
        shutil.rmtree(dst)  # substitui a coleção: fotografias apagadas na pasta saem também da app
    dst.mkdir(parents=True)
    n = 0
    for p in fotos:
        try:
            with Image.open(p) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                im.thumbnail((MAX_PX, MAX_PX))
                n += 1
                im.save(dst / f"foto_{n:02d}.jpg", quality=85)  # sem EXIF: a rotação já está nos píxeis
        except OSError as e:
            print(f"ignorada {p.name}: {e}")
    return n


def teste():
    """Fotografia 400x300 marcada com rotação de 90° (Orientation=6) tem de sair 300x400 (vertical)."""
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp, "src"), Path(tmp, "dst")
        src.mkdir()
        exif = Image.Exif()
        exif[0x0112] = 6
        Image.new("RGB", (400, 300), "red").save(src / "a.jpg", exif=exif)
        Image.new("RGB", (3000, 1000), "blue").save(src / "b.png")
        (src / "c.jpg").write_bytes(b"estragada")
        assert importar(src, dst) == 2
        with Image.open(dst / "foto_01.jpg") as a, Image.open(dst / "foto_02.jpg") as b:
            assert a.size == (300, 400), a.size
            assert b.size == (1280, 427), b.size
            assert not a.getexif().get(0x0112)
    print("ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--teste"]:
        teste()
    elif len(sys.argv) in (2, 3):
        src = Path(sys.argv[1])
        nome = sys.argv[2] if len(sys.argv) == 3 else src.name
        print(f"{importar(src, ASSETS / nome)} fotografias em {ASSETS / nome}")
    else:
        sys.exit(__doc__)
