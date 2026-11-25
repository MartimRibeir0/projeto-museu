import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import mqtt
from ..db import get_db
from ..deps import current_user
from ..models import Command, Device, Reading, utcnow
from ..schemas import CommandIn, CommandOut, DeviceOut, ReadingOut

router = APIRouter(tags=["devices"], dependencies=[Depends(current_user)])

COMMAND_TTL = timedelta(seconds=30)


def get_device(db: Session, device_id: uuid.UUID) -> Device:
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(404, "Dispositivo não encontrado")
    return device


@router.get("/devices", response_model=list[DeviceOut])
def list_devices(db: Session = Depends(get_db)):
    return db.scalars(select(Device).order_by(Device.name)).all()


@router.get("/devices/{device_id}/readings/latest", response_model=ReadingOut)
def latest_reading(device_id: uuid.UUID, db: Session = Depends(get_db)):
    get_device(db, device_id)
    reading = db.scalars(
        select(Reading).where(Reading.device_id == device_id).order_by(Reading.measured_at.desc()).limit(1)
    ).first()
    if reading is None:
        raise HTTPException(404, "Sem leituras")
    return reading


@router.post("/devices/{device_id}/commands", status_code=202, response_model=CommandOut)
def create_command(device_id: uuid.UUID, body: CommandIn, db: Session = Depends(get_db)):
    device = get_device(db, device_id)
    if device.kind == "sensor":
        raise HTTPException(400, "Sensor não aceita comandos")
    if body.command_id:
        existing = db.get(Command, body.command_id)
        if existing is not None:  # idempotente: mesmo commandId devolve o mesmo comando
            if existing.device_id != device_id:
                raise HTTPException(409, "commandId já usado noutro dispositivo")
            return mqtt.expire_if_needed(db, existing)
    cmd = Command(
        id=body.command_id or uuid.uuid4(),
        device_id=device_id,
        desired_state=body.desired_state,
        expires_at=utcnow() + COMMAND_TTL,
    )
    db.add(cmd)
    db.commit()
    mqtt.publish_command(db, cmd)
    return cmd


@router.get("/commands/{command_id}", response_model=CommandOut)
def get_command(command_id: uuid.UUID, db: Session = Depends(get_db)):
    cmd = db.get(Command, command_id)
    if cmd is None:
        raise HTTPException(404, "Comando não encontrado")
    return mqtt.expire_if_needed(db, cmd)
