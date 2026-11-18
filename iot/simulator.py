"""Simulador do módulo IoT (substitui o ESP32 até haver hardware) — contrato em contracts/v1.md §4.

Uso: python iot/simulator.py --host localhost --interval 5
Publica temperatura simulada e estado (retido, com LWT offline) da luz e da ventoinha,
e aplica comandos `setDesiredState` com ack, deduplicação por commandId e expiração.
"""

import argparse
import json
import logging
import random
from collections import OrderedDict
from datetime import datetime, timezone

PREFIX = "museu/v1"
log = logging.getLogger("iot-sim")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class Actuator:
    """Luz ou ventoinha: estado observado + memória dos últimos commandId."""

    def __init__(self, device_id: str, max_seen: int = 100):
        self.device_id = device_id
        self.state = {"on": False}
        self._seen: OrderedDict[str, dict] = OrderedDict()
        self._max_seen = max_seen

    def handle(self, payload: dict, now: datetime | None = None) -> dict:
        """Devolve o ack. Repetidos devolvem o ack original sem voltar a atuar."""
        cid = payload.get("commandId")
        if not cid:
            return {"commandId": None, "result": "rejected", "observedState": self.state, "ts": now_iso()}
        if cid in self._seen:
            return self._seen[cid]

        now = now or datetime.now(timezone.utc)
        desired = payload.get("desiredState") or {}
        expires = payload.get("expiresAt")
        if expires and parse_iso(expires) < now:
            result = "expired"
        elif not isinstance(desired.get("on"), bool):
            result = "rejected"
        else:
            self.state = {"on": desired["on"]}  # no ESP32: escrever GPIO e ler de volta
            result = "applied"

        ack = {"commandId": cid, "result": result, "observedState": dict(self.state), "ts": now_iso()}
        self._seen[cid] = ack
        if len(self._seen) > self._max_seen:
            self._seen.popitem(last=False)
        return ack


def run(host: str, port: int, interval: float, sensor_id: str, light_id: str, fan_id: str) -> None:
    import paho.mqtt.client as mqtt

    actuators = {light_id: Actuator(light_id), fan_id: Actuator(fan_id)}
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="museu-iot-sim")
    # LWT só cobre um tópico por ligação; usa-se o do sensor como disponibilidade do módulo.
    client.will_set(f"{PREFIX}/status/{sensor_id}", json.dumps({"online": False}), qos=1, retain=True)

    def publish_status(device_id: str, observed: dict | None) -> None:
        body = {"online": True, "observedState": observed, "ts": now_iso()}
        client.publish(f"{PREFIX}/status/{device_id}", json.dumps(body), qos=1, retain=True)

    def on_connect(c, _userdata, _flags, reason, _props):
        log.info("ligado ao broker %s:%s (%s)", host, port, reason)
        publish_status(sensor_id, None)
        for dev_id, act in actuators.items():
            c.subscribe(f"{PREFIX}/commands/{dev_id}", qos=1)
            publish_status(dev_id, act.state)

    def on_message(c, _userdata, msg):
        dev_id = msg.topic.rsplit("/", 1)[-1]
        try:
            payload = json.loads(msg.payload)
        except ValueError:
            log.warning("payload inválido em %s", msg.topic)
            return
        ack = actuators[dev_id].handle(payload)
        log.info("comando %s -> %s %s", payload.get("commandId"), ack["result"], ack["observedState"])
        c.publish(f"{PREFIX}/ack/{dev_id}", json.dumps(ack), qos=1)
        publish_status(dev_id, actuators[dev_id].state)

    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect(host, port, keepalive=30)
    client.loop_start()

    import time

    temp = 21.0
    try:
        while True:
            temp = round(min(30.0, max(15.0, temp + random.uniform(-0.3, 0.3))), 1)
            reading = {"value": temp, "unit": "C", "measuredAt": now_iso()}
            client.publish(f"{PREFIX}/readings/{sensor_id}", json.dumps(reading), qos=1)
            log.info("leitura %s", reading)
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        client.publish(f"{PREFIX}/status/{sensor_id}", json.dumps({"online": False}), qos=1, retain=True)
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--sensor-id", default="00000000-0000-4000-8000-0000000000a1")
    ap.add_argument("--light-id", default="00000000-0000-4000-8000-0000000000a2")
    ap.add_argument("--fan-id", default="00000000-0000-4000-8000-0000000000a3")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    run(a.host, a.port, a.interval, a.sensor_id, a.light_id, a.fan_id)
