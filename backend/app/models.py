import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class User(Timestamps, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))


class Photo(Timestamps, Base):
    __tablename__ = "photos"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    memory: Mapped[str | None] = mapped_column(Text)
    taken_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location: Mapped[str | None] = mapped_column(String(200))
    mime_type: Mapped[str] = mapped_column(String(50))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    file_name: Mapped[str] = mapped_column(String(100))  # nome gerado (UUID), nunca o do cliente
    thumb_name: Mapped[str] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer, default=1)

    labels: Mapped[list["Label"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    exhibition_links: Mapped[list["ExhibitionPhoto"]] = relationship(
        back_populates="photo", cascade="all, delete-orphan", lazy="selectin"
    )


class Label(Base):
    __tablename__ = "labels"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    photo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("photos.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(50))
    score: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(10))  # ai | human
    model_version: Mapped[str | None] = mapped_column(String(50))
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


class Exhibition(Timestamps, Base):
    __tablename__ = "exhibitions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)

    photo_links: Mapped[list["ExhibitionPhoto"]] = relationship(
        back_populates="exhibition",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ExhibitionPhoto.position",
    )


class ExhibitionPhoto(Base):
    __tablename__ = "exhibition_photos"
    exhibition_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exhibitions.id", ondelete="CASCADE"), primary_key=True)
    photo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, default=0)

    exhibition: Mapped[Exhibition] = relationship(back_populates="photo_links")
    photo: Mapped[Photo] = relationship(back_populates="exhibition_links")


class Frame(Base):
    """Moldura virtual (slot) numa exposição do museu Unity."""

    __tablename__ = "frames"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    exhibition_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exhibitions.id", ondelete="CASCADE"), index=True)
    slot: Mapped[int] = mapped_column(Integer)
    orientation: Mapped[str] = mapped_column(String(10), default="landscape")  # landscape | portrait | square


class PhysicalFrame(Timestamps, Base):
    """Moldura real da exposição física (gémeo digital); troca de foto registada manualmente."""

    __tablename__ = "physical_frames"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50))
    frame_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("frames.id", ondelete="SET NULL"))
    printed_photo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("photos.id", ondelete="SET NULL"))


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(10))  # sensor | light | fan
    name: Mapped[str] = mapped_column(String(100))
    online: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_state: Mapped[dict | None] = mapped_column(JSON)


class Reading(Base):
    __tablename__ = "readings"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(10))
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Command(Timestamps, Base):
    __tablename__ = "commands"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    desired_state: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(10), default="requested")  # requested|sent|confirmed|failed|timeout
    observed_state: Mapped[dict | None] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
