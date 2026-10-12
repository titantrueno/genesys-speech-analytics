"""Captura de solo lectura de las conversaciones de referencia de FE011 como fixtures del Genesys falso.

Uso (desde la raíz, con GENESYS_* en el .env):  backend/.venv/bin/python scripts/capture_genesys_fixtures.py

Por cada conversación guarda en `backend/tests/fixtures/genesys/<tipo>-<id corto>/`: `details.json` (detalle de
analítica), `sta.json`, `transcripts.json` (documento por comunicación del cliente; `null` si responde 404) y, en chat,
`messages.json` y `messages_bulk.json`. En `catalog.json`, los nombres de colas, usuarios, wrap-ups y divisiones.

Saneado: sin `organizationId`, con el identificador de la organización sustituido y sin URL firmadas. Se conservan ANI y
`externalTag` (decisión del usuario para este desarrollo, ver la spec de FE011). Las URL de descarga nunca se guardan.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.envfile import read_env  # noqa: E402
from ingestion.genesys.client import GenesysClient, GenesysNotFound  # noqa: E402

OUT = ROOT / "backend" / "tests" / "fixtures" / "genesys"
PLACEHOLDER_ORG = "00000000-0000-4000-8000-000000000000"

# Tipos de conversación observados el 2026-10-12 (spec de FE011, «Tipos de conversación observados»).
REFERENCES = {
    "voz_contenida_bot": "37dcbccf-2d89-424e-bc9e-9e53d8494a9a",
    "voz_bot_agente": "7b94988a-807b-4a59-8767-ed445ba9f12b",
    "voz_agente_parcial": "687f2225-6f3b-4446-bfd3-f5d2b3416814",
    "voz_sin_transcripcion": "87a83caa-e647-4dea-9aee-762b6808b080",
    "chat_agente": "8d29170a-20f1-4421-8150-0075a8dd27d5",
    "chat_bot_agente": "f7e79502-c16d-4b7a-9fd6-a9b2ae145bd6",
    "chat_bot_agente_corto": "90116482-f12f-466f-a7ba-2c7c96a975c3",
    "chat_no_entregado": "9e3ec75a-11c8-4df7-9002-339916be2827",
    "chat_no_entregado_mixto": "d74fc0d8-4ac1-47da-9a8c-d91ce49dfda2",
    "chat_reconexion": "c870bc58-1f9d-4c89-a7d7-a86b2b32625a",
}
CUSTOMER_PURPOSES = {"customer", "external"}
TRANSCRIBED_MEDIA = {"voice", "message", "chat"}
_SIGNED_URL = re.compile(r"https?://[^\s\"']*(?:X-Amz-|Signature=|Expires=)[^\s\"']*")


def sanitize(value, org_id: str):
    if isinstance(value, dict):
        return {k: sanitize(v, org_id) for k, v in value.items() if k != "organizationId"}
    if isinstance(value, list):
        return [sanitize(v, org_id) for v in value]
    if isinstance(value, str):
        return _SIGNED_URL.sub("[URL firmada]", value.replace(org_id, PLACEHOLDER_ORG))
    return value


def capture(client: GenesysClient, conversation_id: str) -> dict:
    details = client.get(f"/api/v2/analytics/conversations/{conversation_id}/details")
    files = {"details.json": details,
             "sta.json": client.get(f"/api/v2/speechandtextanalytics/conversations/{conversation_id}")}
    transcripts, is_message = {}, False
    for participant in details["participants"]:
        for session in participant.get("sessions", []):
            is_message |= session.get("mediaType") == "message"
            if participant.get("purpose") in CUSTOMER_PURPOSES and session.get("mediaType") in TRANSCRIBED_MEDIA:
                path = (f"/api/v2/speechandtextanalytics/conversations/{conversation_id}/communications/"
                        f"{session['sessionId']}/transcripturl")
                try:
                    transcripts[session["sessionId"]] = client.get_signed(client.get(path)["url"])
                except GenesysNotFound:
                    transcripts[session["sessionId"]] = None
    files["transcripts.json"] = transcripts
    if is_message:
        messages = client.get(f"/api/v2/conversations/messages/{conversation_id}")
        ids = [m["messageId"] for p in messages.get("participants", []) for m in p.get("messages", [])]
        bulk = client.post(f"/api/v2/conversations/messages/{conversation_id}/messages/bulk", json=ids)
        files["messages.json"], files["messages_bulk.json"] = messages, bulk.get("entities", [])
    return files


def referenced_ids(details: dict) -> dict[str, set[str]]:
    found = {"queues": set(), "users": set(), "wrapups": set(), "divisions": set(details.get("divisionIds", []))}
    for participant in details["participants"]:
        if participant.get("userId"):
            found["users"].add(participant["userId"])
        for session in participant.get("sessions", []):
            for segment in session.get("segments", []):
                if segment.get("queueId"):
                    found["queues"].add(segment["queueId"])
                if segment.get("wrapUpCode"):
                    found["wrapups"].add(segment["wrapUpCode"])
    return found


CATALOG_PATHS = {"queues": "/api/v2/routing/queues/{}", "users": "/api/v2/users/{}",
                 "wrapups": "/api/v2/routing/wrapupcodes/{}", "divisions": "/api/v2/authorization/divisions/{}"}


def main() -> None:
    env = read_env(["GENESYS_CLIENT_ID", "GENESYS_CLIENT_SECRET", "GENESYS_REGION"])
    client = GenesysClient(env["GENESYS_CLIENT_ID"], env["GENESYS_CLIENT_SECRET"], env["GENESYS_REGION"])
    organization = client.get("/api/v2/organizations/me")
    org_id = organization["id"]
    catalog = {"organization": {"id": PLACEHOLDER_ORG, "name": organization["name"]},
               "queues": {}, "users": {}, "wrapups": {}, "divisions": {}}
    OUT.mkdir(parents=True, exist_ok=True)
    for kind, conversation_id in REFERENCES.items():
        folder = OUT / f"{kind}-{conversation_id[:8]}"
        folder.mkdir(exist_ok=True)
        files = capture(client, conversation_id)
        for name, content in files.items():
            (folder / name).write_text(json.dumps(sanitize(content, org_id), ensure_ascii=False, indent=1) + "\n")
        for group, ids in referenced_ids(files["details.json"]).items():
            for entity_id in ids - catalog[group].keys():
                catalog[group][entity_id] = client.get(CATALOG_PATHS[group].format(entity_id))["name"]
        print(f"{folder.name}: {', '.join(sorted(files))}")
    (OUT / "catalog.json").write_text(json.dumps(sanitize(catalog, org_id), ensure_ascii=False, indent=1,
                                                 sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
