"""Small, versioned, untrusted file format for saving progress locally."""
from __future__ import annotations

import json
from typing import Any

VERSION = 1
MAX_BYTES = 3_000_000


def export_progress(messages: list[dict], final: dict | None, pending_text: str | None = None) -> bytes:
    data = {"schema_version": VERSION, "messages": messages, "final": final,
            "pending_text": pending_text}
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(raw) > MAX_BYTES:
        raise ValueError("Avance demasiado grande")
    return raw


def import_progress(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_BYTES:
        raise ValueError("Archivo demasiado grande")
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Archivo de avance ilegible") from exc
    if not isinstance(data, dict) or data.get("schema_version") != VERSION:
        raise ValueError("Versión de avance no compatible")
    msgs = data.get("messages")
    if not isinstance(msgs, list):
        raise ValueError("Historial inválido")
    for msg in msgs:
        if (not isinstance(msg, dict) or msg.get("role") not in ("user", "assistant")
                or not isinstance(msg.get("content"), str) or len(msg["content"]) > 12000):
            raise ValueError("Mensaje inválido en el avance")
    final = data.get("final")
    if final is not None:
        from pert_core import audit_plan
        if not isinstance(final, dict) or "plan" not in final:
            raise ValueError("Plan inválido en el avance")
        # Never trust a saved ok flag or old coordinates.
        final = audit_plan(final["plan"])
    pending = data.get('pending_text')
    if pending is not None and (not isinstance(pending, str) or len(pending) > 12000):
        raise ValueError('Mensaje pendiente inválido')
    return {"messages": msgs, "final": final, "pending_text": pending}
