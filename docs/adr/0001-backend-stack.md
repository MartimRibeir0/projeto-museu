# ADR 0001 — Stack do backend e persistência

- **Estado:** proposta (falta validação da equipa — T019)
- **Data:** 2026-11-18

## Contexto
O backend serve a app Android e o Unity (fotografias, exposições, análise IA) e faz a ponte com o módulo IoT por MQTT.
A equipa já usa Python para a IA (TensorFlow/Keras, UC AAP), o prazo é curto (entrega 05/01/2027) e o alojamento é local/portátil.

## Opções
| Opção | Prós | Contras |
|-------|------|---------|
| **FastAPI + PostgreSQL + ficheiros locais** | Mesmo idioma que a IA; OpenAPI automático; PostgreSQL robusto; Docker simples | Exige Docker ou instalação local do PostgreSQL |
| Node/Express + MongoDB | Rápido de prototipar | Segundo idioma; sem esquema relacional para FKs (fotos ↔ exposições ↔ molduras) |
| Firebase | Sem servidor próprio | Dependência externa, MQTT/IoT fica fora, menos controlo de privacidade |

## Decisão
FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL 16; imagens em disco (`STORAGE_DIR`) com nomes UUID; Mosquitto como broker MQTT.
Tudo sobe com `docker compose up`.

## Consequências
- Testes automáticos correm com SQLite (sem Docker).
- Ficheiros não ficam na BD: backup = dump PostgreSQL + pasta `storage/`.
- Inferência no servidor (decisão provisória; comparação com inferência no telemóvel em T145).
