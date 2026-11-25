import json
import uuid
from datetime import timedelta

import test_api  # noqa: F401  (configura DATABASE_URL/STORAGE_DIR antes de importar app)
from test_api import API, client, fresh_db  # noqa: F401

from app import mqtt
from app.db import SessionLocal
from app.models import Command, Device, utcnow

SENSOR, LIGHT, _FAN = (d[0] for d in mqtt.DEMO_DEVICES)


class FakeClient:
    def __init__(self, rc=0):
        self.rc, self.sent = rc, []

    def publish(self, topic, payload, qos):
        self.sent.append((topic, json.loads(payload)))
        return type("Info", (), {"rc": self.rc})()


def msg(kind, dev, body):
    with SessionLocal() as db:
        mqtt.handle_message(db, f"{mqtt.PREFIX}/{kind}/{dev}", json.dumps(body).encode())


def seed():
    with SessionLocal() as db:
        mqtt.seed_devices(db)
        mqtt.seed_devices(db)  # idempotente


def test_readings_and_status_persisted():
    seed()
    msg("readings", SENSOR, {"value": 21.4, "unit": "C", "measuredAt": "2026-11-22T14:05:00Z"})
    r = client.get(f"{API}/devices/{SENSOR}/readings/latest").json()
    assert r == {"value": 21.4, "unit": "C", "measuredAt": "2026-11-22T14:05:00Z"}

    msg("status", LIGHT, {"online": True, "observedState": {"on": False}, "ts": "2026-11-22T14:06:00Z"})
    light = next(d for d in client.get(f"{API}/devices").json() if d["id"] == str(LIGHT))
    assert light["online"] and light["observedState"] == {"on": False}
    msg("status", LIGHT, {"online": False})  # LWT
    light = next(d for d in client.get(f"{API}/devices").json() if d["id"] == str(LIGHT))
    assert not light["online"] and light["observedState"] == {"on": False}


def test_bad_messages_ignored():
    seed()
    with SessionLocal() as db:
        mqtt.handle_message(db, f"{mqtt.PREFIX}/readings/{SENSOR}", b"not json")
        mqtt.handle_message(db, f"{mqtt.PREFIX}/readings/not-a-uuid", b"{}")
        mqtt.handle_message(db, f"{mqtt.PREFIX}/readings/{uuid.uuid4()}", b'{"value": 1}')
    msg("readings", SENSOR, {"value": "hot"})
    msg("ack", LIGHT, {"commandId": "x"})
    assert client.get(f"{API}/devices/{SENSOR}/readings/latest").status_code == 404


def test_command_lifecycle(monkeypatch):
    seed()
    fake = FakeClient()
    monkeypatch.setattr(mqtt, "_client", fake)
    c = client.post(f"{API}/devices/{LIGHT}/commands", json={"desiredState": {"on": True}}).json()
    assert c["status"] == "sent"
    topic, body = fake.sent[0]
    assert topic == f"museu/v1/commands/{LIGHT}" and body["commandId"] == c["id"] and body["expiresAt"].endswith("Z")

    msg("ack", LIGHT, {"commandId": c["id"], "result": "applied", "observedState": {"on": True}})
    c = client.get(f"{API}/commands/{c['id']}").json()
    assert c["status"] == "confirmed" and c["observedState"] == {"on": True}
    light = next(d for d in client.get(f"{API}/devices").json() if d["id"] == str(LIGHT))
    assert light["observedState"] == {"on": True}


def test_applied_but_wrong_observed_state_fails(monkeypatch):
    seed()
    monkeypatch.setattr(mqtt, "_client", FakeClient())
    c = client.post(f"{API}/devices/{LIGHT}/commands", json={"desiredState": {"on": True}}).json()
    msg("ack", LIGHT, {"commandId": c["id"], "result": "applied", "observedState": {"on": False}})
    assert client.get(f"{API}/commands/{c['id']}").json()["status"] == "failed"


def test_broker_down_stays_requested_then_times_out(monkeypatch):
    seed()
    monkeypatch.setattr(mqtt, "_client", FakeClient(rc=4))
    c = client.post(f"{API}/devices/{LIGHT}/commands", json={"desiredState": {"on": True}}).json()
    assert c["status"] == "requested"
    with SessionLocal() as db:
        db.get(Command, uuid.UUID(c["id"])).expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.get(f"{API}/commands/{c['id']}").json()["status"] == "timeout"


def test_ack_from_other_device_ignored(monkeypatch):
    seed()
    monkeypatch.setattr(mqtt, "_client", FakeClient())
    c = client.post(f"{API}/devices/{LIGHT}/commands", json={"desiredState": {"on": True}}).json()
    msg("ack", _FAN, {"commandId": c["id"], "result": "applied", "observedState": {"on": True}})
    assert client.get(f"{API}/commands/{c['id']}").json()["status"] == "sent"
    with SessionLocal() as db:
        assert db.get(Device, _FAN).observed_state is None
