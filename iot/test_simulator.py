from datetime import datetime, timedelta, timezone

from simulator import Actuator


def iso(dt):
    return dt.isoformat().replace("+00:00", "Z")


def test_apply_and_dedup():
    a = Actuator("light")
    future = iso(datetime.now(timezone.utc) + timedelta(seconds=30))
    ack = a.handle({"commandId": "c1", "desiredState": {"on": True}, "expiresAt": future})
    assert ack["result"] == "applied" and a.state == {"on": True}
    a.state = {"on": False}  # estado mudou por outro comando
    assert a.handle({"commandId": "c1", "desiredState": {"on": True}}) == ack  # repetido não atua
    assert a.state == {"on": False}


def test_expired_and_invalid():
    a = Actuator("fan")
    past = iso(datetime.now(timezone.utc) - timedelta(seconds=1))
    assert a.handle({"commandId": "c1", "desiredState": {"on": True}, "expiresAt": past})["result"] == "expired"
    assert a.handle({"commandId": "c2", "desiredState": {"on": "yes"}})["result"] == "rejected"
    assert a.handle({"desiredState": {"on": True}})["result"] == "rejected"
    assert a.state == {"on": False}


def test_seen_is_bounded():
    a = Actuator("light", max_seen=2)
    for i in range(3):
        a.handle({"commandId": f"c{i}", "desiredState": {"on": bool(i % 2)}})
    assert list(a._seen) == ["c1", "c2"]
