# Museu Virtual Pessoal

Aplicação móvel que transforma fotografias pessoais em exposições num museu virtual 3D expansível, com etiquetas sugeridas por IA, exploração em RV/RA e uma pequena exposição física ligada por IoT (gémeo digital).

Projeto de Mestrado em Engenharia Informática — UCs TEI, RVA, DDM e AAP (2026/2027).

## Estrutura

| Pasta | Conteúdo | Estado |
|-------|----------|--------|
| `contracts/` | Contrato v1: arquitetura, JSON da API, tópicos MQTT | feito |
| `backend/` | API FastAPI + PostgreSQL + migrações Alembic | base feita |
| `iot/` | Simulador MQTT do módulo IoT (até haver ESP32) | feito |
| `docs/` | ADRs e documentação técnica | iniciado |
| `DOCUMENTACAO/` | Proposta, artigo e requisitos DDM (.docx) | — |
| `app-android/` | App Kotlin/Jetpack Compose | base feita (navegação + Photo Picker) |
| `museum-unity/` | Museu Unity (3D, RV, RA) | por fazer |
| `blender/` | Modelos .blend e FBX | por fazer |
| `ml/` | Dataset, CNN e MobileNetV2 | por fazer |
| `tests/` | Testes ponta a ponta | por fazer |

Plano de trabalho e progresso: [`museu_virtual_checklist_atualizada.md`](museu_virtual_checklist_atualizada.md).

## Arrancar (Docker)

```sh
cp .env.example .env        # mudar POSTGRES_PASSWORD
docker compose up --build
```
- API: http://localhost:8000/api/v1/health
- Documentação interativa (OpenAPI): http://localhost:8000/docs
- MQTT: `localhost:1883`

Simulador IoT (noutro terminal):
```sh
pip install paho-mqtt==2.1.0
python iot/simulator.py --host localhost
```

## Desenvolvimento do backend sem Docker

```sh
cd backend
python -m venv .venv
.venv/Scripts/activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head              # cria dev.db (SQLite) por omissão
uvicorn app.main:app --reload
python -m pytest -q               # testes
```
Variáveis: `DATABASE_URL` (omissão `sqlite:///./dev.db`), `STORAGE_DIR` (omissão `./storage`), `MAX_UPLOAD_BYTES` (omissão 10 MB), `MQTT_HOST` (vazio = ponte MQTT desligada; no Docker é `mqtt`), `MQTT_PORT` (omissão 1883).

Nova migração depois de mudar `app/models.py`:
```sh
alembic revision --autogenerate -m "descricao"
```

## Versões

Python 3.11 · FastAPI 0.115 · SQLAlchemy 2.0 · Alembic 1.14 · PostgreSQL 16 · Mosquitto 2 · paho-mqtt 2.1
