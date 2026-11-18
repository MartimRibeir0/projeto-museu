import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, storage
from ..db import get_db
from ..deps import current_user
from ..models import ExhibitionPhoto, Label, Photo, User
from ..schemas import PhotoOut, PhotoUpdate

router = APIRouter(prefix="/photos", tags=["photos"])


def to_out(p: Photo) -> PhotoOut:
    base = f"{config.API_PREFIX}/photos/{p.id}"
    return PhotoOut.model_validate(
        {
            **{c: getattr(p, c) for c in (
                "id", "title", "description", "memory", "taken_at", "location", "width", "height",
                "mime_type", "version", "created_at", "updated_at",
            )},
            "labels": p.labels,
            "exhibition_ids": [link.exhibition_id for link in p.exhibition_links],
            "file_url": f"{base}/file",
            "thumbnail_url": f"{base}/thumbnail",
        }
    )


def get_owned(db: Session, photo_id: uuid.UUID, user: User) -> Photo:
    photo = db.get(Photo, photo_id)
    if photo is None or photo.owner_id != user.id:
        raise HTTPException(404, "Fotografia não encontrada")
    return photo


@router.post("", status_code=201, response_model=PhotoOut)
async def upload(file: UploadFile, db: Session = Depends(get_db), user: User = Depends(current_user)):
    data = await file.read(config.MAX_UPLOAD_BYTES + 1)
    photo = Photo(owner_id=user.id, **storage.save_image(data))
    db.add(photo)
    db.commit()
    return to_out(photo)


@router.get("", response_model=list[PhotoOut])
def list_photos(
    exhibition_id: uuid.UUID | None = None,
    label: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    q = select(Photo).where(Photo.owner_id == user.id).order_by(Photo.created_at.desc())
    if exhibition_id:
        q = q.join(ExhibitionPhoto).where(ExhibitionPhoto.exhibition_id == exhibition_id)
    if label:
        q = q.where(Photo.labels.any((Label.name == label) & Label.confirmed))
    return [to_out(p) for p in db.scalars(q)]


@router.get("/{photo_id}", response_model=PhotoOut)
def get_photo(photo_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return to_out(get_owned(db, photo_id, user))


@router.patch("/{photo_id}", response_model=PhotoOut)
def update_photo(
    photo_id: uuid.UUID, body: PhotoUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    photo = get_owned(db, photo_id, user)
    fields = body.model_dump(exclude_unset=True)
    labels = fields.pop("labels", None)
    for k, v in fields.items():
        setattr(photo, k, v)
    if labels is not None:
        photo.labels = [Label(**lbl) for lbl in labels]
    photo.version += 1
    db.commit()
    db.refresh(photo)
    return to_out(photo)


@router.delete("/{photo_id}", status_code=204)
def delete_photo(photo_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    photo = get_owned(db, photo_id, user)
    files = (photo.file_name, photo.thumb_name)
    db.delete(photo)
    db.commit()
    storage.delete_files(*files)  # depois do commit: se a BD falhar, os ficheiros ficam


@router.get("/{photo_id}/file")
def get_file(photo_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    photo = get_owned(db, photo_id, user)
    return FileResponse(storage.path_of("originals", photo.file_name), media_type=photo.mime_type)


@router.get("/{photo_id}/thumbnail")
def get_thumbnail(photo_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    photo = get_owned(db, photo_id, user)
    return FileResponse(storage.path_of("thumbs", photo.thumb_name), media_type="image/jpeg")
