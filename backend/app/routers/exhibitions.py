import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Exhibition, ExhibitionPhoto, User
from ..schemas import ExhibitionIn, ExhibitionOut, ExhibitionUpdate, PositionIn
from .photos import get_owned as get_owned_photo

router = APIRouter(prefix="/exhibitions", tags=["exhibitions"])


def get_owned(db: Session, exhibition_id: uuid.UUID, user: User) -> Exhibition:
    ex = db.get(Exhibition, exhibition_id)
    if ex is None or ex.owner_id != user.id:
        raise HTTPException(404, "Exposição não encontrada")
    return ex


@router.post("", status_code=201, response_model=ExhibitionOut)
def create(body: ExhibitionIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    ex = Exhibition(owner_id=user.id, **body.model_dump())
    db.add(ex)
    db.commit()
    return ex


@router.get("", response_model=list[ExhibitionOut])
def list_exhibitions(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(Exhibition).where(Exhibition.owner_id == user.id).order_by(Exhibition.created_at)).all()


@router.get("/{exhibition_id}", response_model=ExhibitionOut)
def get_exhibition(exhibition_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return get_owned(db, exhibition_id, user)


@router.patch("/{exhibition_id}", response_model=ExhibitionOut)
def update(
    exhibition_id: uuid.UUID, body: ExhibitionUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    ex = get_owned(db, exhibition_id, user)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(ex, k, v)
    db.commit()
    return ex


@router.delete("/{exhibition_id}", status_code=204)
def delete(exhibition_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    db.delete(get_owned(db, exhibition_id, user))  # só remove associações; fotos ficam na coleção
    db.commit()


@router.put("/{exhibition_id}/photos/{photo_id}", response_model=ExhibitionOut)
def put_photo(
    exhibition_id: uuid.UUID,
    photo_id: uuid.UUID,
    body: PositionIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    ex = get_owned(db, exhibition_id, user)
    get_owned_photo(db, photo_id, user)
    link = db.get(ExhibitionPhoto, (exhibition_id, photo_id))
    if link is None:
        db.add(ExhibitionPhoto(exhibition_id=exhibition_id, photo_id=photo_id, position=body.position))
    else:
        link.position = body.position
    db.commit()
    db.refresh(ex)
    return ex


@router.delete("/{exhibition_id}/photos/{photo_id}", status_code=204)
def remove_photo(
    exhibition_id: uuid.UUID, photo_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    get_owned(db, exhibition_id, user)
    link = db.get(ExhibitionPhoto, (exhibition_id, photo_id))
    if link is None:
        raise HTTPException(404, "Fotografia não está nesta exposição")
    db.delete(link)
    db.commit()
