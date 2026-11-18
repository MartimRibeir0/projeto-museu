"""Armazenamento de imagens em disco: nomes gerados (UUID), sem caminhos vindos do cliente."""

import io
import uuid
from pathlib import Path

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

from . import config

ALLOWED = {"JPEG": ("image/jpeg", "jpg"), "PNG": ("image/png", "png"), "WEBP": ("image/webp", "webp")}


def _dir(kind: str) -> Path:
    d = config.STORAGE_DIR / kind
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_image(data: bytes) -> dict:
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Imagem excede o tamanho máximo")
    try:
        # Formato validado pelo conteúdo, não pelo Content-Type do cliente.
        img = Image.open(io.BytesIO(data))
        img.verify()
        img = Image.open(io.BytesIO(data))
    except (UnidentifiedImageError, OSError):
        raise HTTPException(415, "Ficheiro não é uma imagem válida")
    if img.format not in ALLOWED:
        raise HTTPException(415, "Formato não suportado (JPEG, PNG ou WEBP)")

    mime, ext = ALLOWED[img.format]
    key = uuid.uuid4().hex
    file_name, thumb_name = f"{key}.{ext}", f"{key}.jpg"
    (_dir("originals") / file_name).write_bytes(data)

    img = ImageOps.exif_transpose(img)  # roda conforme EXIF; a miniatura sai sem metadados
    width, height = img.size
    thumb = img.convert("RGB")
    thumb.thumbnail((config.THUMB_SIZE, config.THUMB_SIZE))
    thumb.save(_dir("thumbs") / thumb_name, "JPEG", quality=85)
    return {"mime_type": mime, "width": width, "height": height, "file_name": file_name, "thumb_name": thumb_name}


def path_of(kind: str, name: str) -> Path:
    return _dir(kind) / Path(name).name


def delete_files(file_name: str, thumb_name: str) -> None:
    path_of("originals", file_name).unlink(missing_ok=True)
    path_of("thumbs", thumb_name).unlink(missing_ok=True)
