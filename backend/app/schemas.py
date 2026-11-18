import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer
from pydantic.alias_generators import to_camel


def _iso_utc(dt: datetime) -> str:
    # SQLite devolve datetimes sem tz; tudo é guardado em UTC.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


UtcDatetime = Annotated[datetime, PlainSerializer(_iso_utc, return_type=str)]


class Schema(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class LabelIn(Schema):
    name: str = Field(min_length=1, max_length=50)
    score: float | None = Field(default=None, ge=0, le=1)
    source: Literal["ai", "human"] = "human"
    model_version: str | None = None
    confirmed: bool = False


class LabelOut(LabelIn):
    pass


class PhotoUpdate(Schema):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = None
    memory: str | None = None
    taken_at: datetime | None = None
    location: str | None = Field(default=None, max_length=200)
    labels: list[LabelIn] | None = None


class PhotoOut(Schema):
    id: uuid.UUID
    title: str | None
    description: str | None
    memory: str | None
    taken_at: UtcDatetime | None
    location: str | None
    width: int
    height: int
    mime_type: str
    file_url: str
    thumbnail_url: str
    labels: list[LabelOut]
    exhibition_ids: list[uuid.UUID]
    version: int
    created_at: UtcDatetime
    updated_at: UtcDatetime


class ExhibitionIn(Schema):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class ExhibitionUpdate(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None


class ExhibitionPhotoOut(Schema):
    photo_id: uuid.UUID
    position: int


class ExhibitionOut(Schema):
    id: uuid.UUID
    name: str
    description: str | None
    photos: list[ExhibitionPhotoOut] = Field(validation_alias="photo_links")
    created_at: UtcDatetime
    updated_at: UtcDatetime


class PositionIn(Schema):
    position: int = Field(ge=0)


class DeviceOut(Schema):
    id: uuid.UUID
    kind: str
    name: str
    online: bool
    last_seen: UtcDatetime | None
    observed_state: dict | None


class ReadingOut(Schema):
    value: float
    unit: str
    measured_at: UtcDatetime


class CommandIn(Schema):
    desired_state: dict
    command_id: uuid.UUID | None = None


class CommandOut(Schema):
    id: uuid.UUID
    device_id: uuid.UUID
    desired_state: dict
    status: str
    observed_state: dict | None
    created_at: UtcDatetime
    updated_at: UtcDatetime
    expires_at: UtcDatetime
