"""Ponte MQTT do servidor (contracts/v1.md §4): guarda leituras, estado e acks; publica comandos.

Desligada se MQTT_HOST estiver vazio (testes, desenvolvimento sem broker).
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session

from . import config
from .db import SessionLocal
from .models import Command, Device, Reading, utcnow

PREFIX = "museu/v1"
log = logging.getLogger("museu.mqtt")

# IDs fixos do simulador (iot/simulator.py) e do futuro ESP32.
DEMO_DEVICES = [
    (uuid.UUID("00000000-0000-4000-8000-0000000000a1"), "sensor", "Temperatura da exposição"),
    (uuid.UUID("00000000-0000-4000-8000-0000000000a2"), "light", "Luz da exposição"),
    (uuid.UUID("00000000-0000-4000-8000-0000000000a3"), "fan", "Ventoinha da exposição"),
]

_client = None


def _aware(dt: datetime) -> datetime:
    # SQLite devolve datetimes sem tz; tudo é guardado em UTC.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _parse_ts(value) -> datetime:
    if isinstance(value, str):
        try:
            return _aware(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            pass
    return utcnow()


def seed_devices(db: Session) -> None:
    for dev_id, kind, name in DEMO_DEVICES:
        if db.get(Device, dev_id) is None:
            db.add(Device(id=dev_id, kind=kind, name=name))
    db.commit()


def expire_if_needed(db: Session, cmd: Command) -> Command:
    """Sem ack até expiresAt -> timeout. Avaliado ao ler, sem tarefa em segundo plano."""
    if cmd.status in ("requested", "sent") and _aware(cmd.expires_at) < utcnow():
        cmd.status = "timeout"
        db.commit()
    return cmd


def handle_message(db: Session, topic: str, payload: bytes) -> None:
    """Aplica uma mensagem IoT -> servidor. Payloads inválidos são ignorados (vêm da rede)."""
    parts = topic.split("/")
    if len(parts) != 4 or "/".join(parts[:2]) != PREFIX:
        return
    kind = parts[2]
    try:
        device_id = uuid.UUID(parts[3])
        data = json.loads(payload)
    except ValueError:
        log.warning("mensagem inválida em %s", topic)
        return
    if not isinstance(data, dict):
        return
    device = db.get(Device, device_id)
    if device is None:
        log.warning("dispositivo desconhecido %s", device_id)
        return

    if kind == "readings":
        value = data.get("value")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return
        measured_at = _parse_ts(data.get("measuredAt"))
        db.add(Reading(device_id=device_id, value=float(value), unit=str(data.get("unit", ""))[:10], measured_at=measured_at))
        device.online, device.last_seen = True, measured_at
    elif kind == "status":
        device.online = bool(data.get("online"))
        if device.online:
            device.last_seen = _parse_ts(data.get("ts"))
        if isinstance(data.get("observedState"), dict):
            device.observed_state = data["observedState"]
    elif kind == "ack":
        try:
            cmd = db.get(Command, uuid.UUID(str(data.get("commandId"))))
        except ValueError:
            return
        if cmd is None or cmd.device_id != device_id or cmd.status in ("confirmed", "failed"):
            return
        observed = data.get("observedState")
        cmd.observed_state = observed if isinstance(observed, dict) else None
        result = data.get("result")
        if result == "applied":
            # confirmação física: o estado lido tem de bater com o pedido.
            ok = isinstance(observed, dict) and all(observed.get(k) == v for k, v in cmd.desired_state.items())
            cmd.status = "confirmed" if ok else "failed"
        elif result == "expired":
            cmd.status = "timeout"
        else:
            cmd.status = "failed"
        if isinstance(observed, dict):
            device.observed_state = observed
    else:
        return
    db.commit()


def publish_command(db: Session, cmd: Command) -> None:
    """Publica o comando e passa requested -> sent se o broker o aceitou."""
    if _client is None:
        return
    body = {
        "commandId": str(cmd.id),
        "desiredState": cmd.desired_state,
        "expiresAt": _aware(cmd.expires_at).isoformat().replace("+00:00", "Z"),
    }
    info = _client.publish(f"{PREFIX}/commands/{cmd.device_id}", json.dumps(body), qos=1)
    if info.rc != 0:
        log.warning("publicação falhou (rc=%s) para %s", info.rc, cmd.id)
        return
    # condicional: o ack pode chegar antes deste commit.
    db.execute(update(Command).where(Command.id == cmd.id, Command.status == "requested").values(status="sent"))
    db.commit()
    db.refresh(cmd)


def start() -> None:
    global _client
    if not config.MQTT_HOST:
        log.info("MQTT desligado (MQTT_HOST vazio)")
        return
    import paho.mqtt.client as mqtt

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="museu-backend")

    def on_connect(c, _userdata, _flags, reason, _props):
        log.info("ligado ao broker %s:%s (%s)", config.MQTT_HOST, config.MQTT_PORT, reason)
        for t in ("readings", "status", "ack"):
            c.subscribe(f"{PREFIX}/{t}/+", qos=1)

    def on_message(_c, _userdata, msg):
        try:
            with SessionLocal() as db:
                handle_message(db, msg.topic, msg.payload)
        except Exception:  # não deixar uma mensagem matar a thread do paho
            log.exception("erro a processar %s", msg.topic)

    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect_async(config.MQTT_HOST, config.MQTT_PORT, keepalive=30)
    client.loop_start()
    _client = client


def stop() -> None:
    global _client
    if _client is not None:
        _client.loop_stop()
        _client.disconnect()
        _client = None
