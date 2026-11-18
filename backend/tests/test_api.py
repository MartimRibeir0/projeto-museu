import io
import os
import tempfile
import uuid

tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/test.db"
os.environ["STORAGE_DIR"] = f"{tmp}/storage"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Device  # noqa: E402

API = "/api/v1"
client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def png(w=800, h=600) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "blue").save(buf, "PNG")
    return buf.getvalue()


def upload(data=None, name="a.png", ctype="image/png"):
    return client.post(f"{API}/photos", files={"file": (name, data or png(), ctype)})


def test_health():
    assert client.get(f"{API}/health").json() == {"status": "ok"}


def test_upload_and_files():
    r = upload()
    assert r.status_code == 201, r.text
    p = r.json()
    assert (p["width"], p["height"], p["mimeType"], p["version"]) == (800, 600, "image/png", 1)
    assert p["createdAt"].endswith("Z")
    thumb = client.get(p["thumbnailUrl"])
    assert thumb.status_code == 200
    assert max(Image.open(io.BytesIO(thumb.content)).size) == 400
    assert client.get(p["fileUrl"]).content == png()


def test_upload_rejects_non_image_even_with_image_content_type():
    assert upload(b"not an image", ctype="image/jpeg").status_code == 415


def test_upload_ignores_client_filename():
    p = upload(name="../../evil.png").json()
    assert client.get(p["fileUrl"]).status_code == 200
    assert not os.path.exists(os.path.join(tmp, "evil.png"))


def test_upload_too_big(monkeypatch):
    from app import config

    monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 10)
    assert upload().status_code == 413


def test_patch_labels_and_version():
    pid = upload().json()["id"]
    r = client.patch(
        f"{API}/photos/{pid}",
        json={
            "title": "Praia",
            "memory": "Férias",
            "labels": [
                {"name": "praia", "score": 0.9, "source": "ai", "modelVersion": "m1"},
                {"name": "familia", "source": "human", "confirmed": True},
            ],
        },
    )
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["title"] == "Praia" and p["version"] == 2
    assert {lbl["name"]: lbl["confirmed"] for lbl in p["labels"]} == {"praia": False, "familia": True}
    # filtro por etiqueta só usa categorias confirmadas
    assert len(client.get(f"{API}/photos", params={"label": "familia"}).json()) == 1
    assert client.get(f"{API}/photos", params={"label": "praia"}).json() == []


def test_delete_photo_removes_files():
    before = {d: set(os.listdir(f"{tmp}/storage/{d}")) for d in ("originals", "thumbs")}
    p = upload().json()
    assert client.delete(f"{API}/photos/{p['id']}").status_code == 204
    assert client.get(f"{API}/photos/{p['id']}").status_code == 404
    assert {d: set(os.listdir(f"{tmp}/storage/{d}")) for d in before} == before


def test_exhibition_flow():
    ex = client.post(f"{API}/exhibitions", json={"name": "Verão"}).json()
    a, b = upload().json()["id"], upload().json()["id"]
    client.put(f"{API}/exhibitions/{ex['id']}/photos/{a}", json={"position": 1})
    r = client.put(f"{API}/exhibitions/{ex['id']}/photos/{b}", json={"position": 0})
    assert [x["photoId"] for x in r.json()["photos"]] == [b, a]
    assert client.get(f"{API}/photos/{a}").json()["exhibitionIds"] == [ex["id"]]
    assert len(client.get(f"{API}/photos", params={"exhibitionId": ex["id"]}).json()) == 2

    assert client.patch(f"{API}/exhibitions/{ex['id']}", json={"name": "Verão 26"}).json()["name"] == "Verão 26"
    assert client.delete(f"{API}/exhibitions/{ex['id']}/photos/{a}").status_code == 204
    assert client.delete(f"{API}/exhibitions/{ex['id']}").status_code == 204
    assert client.get(f"{API}/photos/{b}").status_code == 200  # fotos ficam na coleção


def test_not_found_and_validation():
    missing = uuid.uuid4()
    assert client.get(f"{API}/photos/{missing}").status_code == 404
    assert client.get(f"{API}/exhibitions/not-a-uuid").status_code == 422
    assert client.post(f"{API}/exhibitions", json={"name": ""}).status_code == 422


def test_commands_idempotent():
    with SessionLocal() as db:
        light, sensor = Device(kind="light", name="Luz"), Device(kind="sensor", name="Temp")
        db.add_all([light, sensor])
        db.commit()
        light_id, sensor_id = str(light.id), str(sensor.id)

    assert len(client.get(f"{API}/devices").json()) == 2
    cid = str(uuid.uuid4())
    body = {"desiredState": {"on": True}, "commandId": cid}
    r1 = client.post(f"{API}/devices/{light_id}/commands", json=body)
    r2 = client.post(f"{API}/devices/{light_id}/commands", json=body)
    assert r1.status_code == r2.status_code == 202
    assert r1.json() == r2.json() and r1.json()["status"] == "requested"
    assert client.get(f"{API}/commands/{cid}").json()["id"] == cid
    assert client.post(f"{API}/devices/{sensor_id}/commands", json=body).status_code == 400
    assert client.get(f"{API}/devices/{sensor_id}/readings/latest").status_code == 404
