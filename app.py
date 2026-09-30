"""Workshop UI. Run: streamlit run app.py"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import hmac
import importlib
from pathlib import Path
from io import BytesIO
from zoneinfo import ZoneInfo

import streamlit as st
from openai import OpenAI, APIError, RateLimitError


st.set_page_config(page_title="Asistente PERT Chart de Metas", page_icon="🟨",
                   layout="centered", initial_sidebar_state="collapsed")


@st.cache_resource
def load_assistant_revision(signature):
    # Streamlit may refresh app.py while retaining imported Python modules.
    # Reload once per source revision, across sessions, before starting a turn.
    import intake
    import motor_pert
    import pert_core
    import contingencies
    import progress
    import pdf_export
    import pert_assistant
    importlib.reload(intake)
    importlib.reload(motor_pert)
    importlib.reload(pert_core)
    importlib.reload(contingencies)
    importlib.reload(progress)
    importlib.reload(pdf_export)
    return importlib.reload(pert_assistant)


_source_root = Path(__file__).resolve().parent
_revision = sha256(b"".join((_source_root / name).read_bytes()
                          for name in ("motor_pert.py", "pert_core.py", "contingencies.py", "intake.py", "pert_assistant.py", "progress.py", "pdf_export.py"))).hexdigest()
_assistant = load_assistant_revision(_revision)
AssistantError = _assistant.AssistantError
respond = _assistant.respond
build_final = _assistant.build_final
final_message = _assistant.final_message
from progress import export_progress, import_progress
from pdf_export import export_pdf


def secret(name: str, default=None):
    try:
        return st.secrets.get(name, default)
    except FileNotFoundError:
        return default


event_password = secret("EVENT_PASSWORD")
api_key = secret("OPENAI_API_KEY")
if not event_password:
    st.error("Falta configurar el acceso del taller. Contacta al organizador.")
    st.stop()

st.title("Tu meta, hecha plan")
st.caption("Asistente PERT Chart de Metas · una pregunta a la vez")
if st.query_params.get("qa") == "1":
    st.caption("__QA_RUN__:" + st.query_params.get("qa_run_id", ""))

if (not st.session_state.get("authenticated") or
        not hmac.compare_digest(st.session_state.get("password_fingerprint", ""),
                                sha256(event_password.encode()).hexdigest())):
    st.session_state.authenticated = False
    with st.form("access"):
        supplied = st.text_input("Clave del taller", type="password")
        submitted = st.form_submit_button("Entrar", use_container_width=True)
    if submitted:
        if hmac.compare_digest(supplied, event_password):
            st.session_state.authenticated = True
            st.session_state.password_fingerprint = sha256(event_password.encode()).hexdigest()
            st.rerun()
        else:
            st.error("Clave incorrecta.")
    st.stop()

if not api_key:
    st.error("El asistente aún no tiene configurada la API. Contacta al organizador.")
    st.stop()

client = OpenAI(api_key=api_key, timeout=180, max_retries=1)
# PERT_MODEL selects the quality-tested model; the prototype OPENAI_MODEL setting
# is intentionally superseded so existing deployments receive the quality fix.
model = secret("PERT_MODEL", "gpt-5.4")
transcription_model = secret("TRANSCRIPTION_MODEL", "gpt-transcribe")
audio_seconds_limit = int(secret("MAX_AUDIO_SECONDS", 90))
st.session_state.setdefault("qa_trace", [])
st.session_state.setdefault("known_facts", {})
st.session_state.setdefault("accepted_goal", None)
st.session_state.setdefault("messages", [])
st.session_state.setdefault("final", None)
st.session_state.setdefault("usage", {"input_tokens": 0, "output_tokens": 0, "audio_seconds": 0.0})

with st.sidebar:
    st.header("Mi avance")
    if st.query_params.get("qa") == "1":
        import json
        st.download_button("Diagnóstico de prueba", json.dumps(st.session_state.qa_trace,ensure_ascii=False),file_name="qa_trace.json",mime="application/json")
    if st.button("Empezar otro PERT", use_container_width=True):
        st.session_state.messages = []
        st.session_state.final = None
        st.session_state.pending_text = None
        st.session_state.last_error = None
        st.session_state.known_facts = {}
        st.session_state.accepted_goal = None
        st.session_state.usage = {"input_tokens": 0, "output_tokens": 0, "audio_seconds": 0.0}
        st.rerun()
    try:
        progress_bytes = export_progress(st.session_state.messages, st.session_state.final,
                                         st.session_state.get('pending_text'))
        st.download_button("Guardar avance", progress_bytes,
                           file_name="mi_pert_avance.json", mime="application/json",
                           use_container_width=True)
    except ValueError:
        st.warning("El avance supera el tamaño permitido.")
    uploaded = st.file_uploader("Retomar un avance guardado", type=["json"],
                                max_upload_size=3)
    if uploaded is not None:
        raw = uploaded.getvalue()
        fingerprint = sha256(raw).hexdigest()
        if st.session_state.get("loaded_fingerprint") != fingerprint:
            try:
                loaded = import_progress(raw)
                st.session_state.messages = loaded["messages"]
                st.session_state.final = loaded["final"]
                st.session_state.pending_text = loaded['pending_text']
                st.session_state.last_error = None
                st.session_state.known_facts = {}
                # Imported files are untrusted. Reconstruct the goal decision
                # from the complete transcript under the current intake rules.
                st.session_state.accepted_goal = None
                st.session_state.loaded_fingerprint = fingerprint
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    st.caption("Guarda el avance antes de cerrar o actualizar la página.")

if not st.session_state.messages:
    st.info("¿Cuál es tu Meta Principal? Puedes escribir o tocar el micrófono y hablar.")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if st.session_state.final:
    try:
        pdf = export_pdf(st.session_state.final)
        st.download_button("Descargar mi PERT completo en PDF", pdf,
                           file_name="mi_pert_chart_de_metas.pdf", mime="application/pdf",
                           type="primary", use_container_width=True)
        st.caption("En tu celular, abre el PDF descargado y usa Compartir para enviarlo por WhatsApp o correo.")
    except Exception:
        st.error("No se pudo generar el PDF. Guarda tu avance y avisa al organizador.")

retry = st.session_state.pop("retry_requested", False)
if st.session_state.get("last_error"):
    st.error(st.session_state.last_error)
if st.session_state.get("pending_text"):
    st.warning("Tu último mensaje quedó pendiente y puedes reenviarlo sin volver a escribirlo.")
    retry = st.button("Reintentar mi mensaje", use_container_width=True) or retry
submitted = st.chat_input("Escribe o habla para responder", accept_audio=True,
                          max_chars=6000, max_upload_size=10)
if retry:
    submitted = st.session_state.pending_text
if submitted is None:
    st.stop()

# A second credential check closes sessions when the shared password rotates.
if not hmac.compare_digest(st.session_state.password_fingerprint,
                           sha256(secret("EVENT_PASSWORD", "").encode()).hexdigest()):
    st.session_state.authenticated = False
    st.rerun()

try:
    text = (submitted if isinstance(submitted, str) else (submitted.text or "")).strip()
    audio = None if isinstance(submitted, str) else submitted.audio
    if audio is not None:
        data = audio.getvalue()
        if len(data) > 10_000_000:
            raise ValueError("El audio excede 10 MB. Graba un mensaje más corto.")
        import wave
        with wave.open(BytesIO(data), "rb") as wav:
            seconds = wav.getnframes() / wav.getframerate()
        if seconds <= 0 or seconds > audio_seconds_limit:
            raise ValueError(f"El audio debe durar como máximo {audio_seconds_limit} segundos.")
        with st.spinner("Transcribiendo tu voz..."):
            result = client.audio.transcriptions.create(
                model=transcription_model, file=("mensaje.wav", data, "audio/wav"))
        spoken = result.text.strip()
        if not spoken:
            raise ValueError("No se entendió el audio. Intenta de nuevo.")
        st.session_state.usage["audio_seconds"] += seconds
        text = (text + "\n" + spoken).strip()
    if not text:
        st.stop()
    st.session_state.pending_text = text
    st.session_state.last_error = None
    st.session_state.final = None
    st.session_state.messages.append({"role": "user", "content": text})
    with st.chat_message("user"):
        st.markdown(text)
    with st.chat_message("assistant"):
        with st.spinner("Preparando tu siguiente paso...", show_time=True):
            _assistant.TRACE.set(st.session_state.qa_trace if st.query_params.get("qa") == "1" else None)
            reply, finalize, usage = respond(client, model, st.session_state.messages,
                                             datetime.now(ZoneInfo("America/Lima")).date().isoformat(),
                                             known_facts=st.session_state.known_facts,
                                             accepted_goal=st.session_state.accepted_goal)
            if usage.get('snapshot'):
                st.session_state.known_facts = usage['snapshot']['facts']
                st.session_state.accepted_goal = usage['snapshot'].get('goal_validation')
            for key in ("input_tokens", "output_tokens"):
                st.session_state.usage[key] += usage.get(key, 0)
            if finalize:
                audit, missing, extra_usage = build_final(
                    client, model, st.session_state.messages,
                    datetime.now(ZoneInfo("America/Lima")).date().isoformat(),
                    ready_snapshot=usage.get('snapshot'))
                for key in ("input_tokens", "output_tokens"):
                    st.session_state.usage[key] += extra_usage.get(key, 0)
                if audit:
                    st.session_state.final = audit
                    reply = final_message(audit)
                elif missing and missing[0] != "No se pudo completar la verificación interna del montaje":
                    reply = missing[0] if missing[0].startswith('¿') else "Para terminar el plan, ¿puedes precisar " + missing[0].rstrip(" .?") + "?"
                else:
                    raise AssistantError("Todavía no pude verificar el montaje completo. Puedes reintentar tu mensaje con el botón de abajo; tu avance se conserva.")
        st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.session_state.pending_text = None
        # Refresh the download bytes after EVERY successful turn, not only final.
        st.rerun()
except (ValueError, AssistantError) as exc:
    st.session_state.last_error = str(exc)
    if st.session_state.messages and st.session_state.messages[-1] == {"role": "user", "content": st.session_state.get("pending_text")}:
        st.session_state.messages.pop()
    st.rerun()
except RateLimitError:
    st.session_state.last_error = "La API no tiene saldo disponible o alcanzó temporalmente su capacidad. El organizador puede recargar y luego puedes reintentar tu mensaje."
    if st.session_state.messages and st.session_state.messages[-1] == {"role": "user", "content": st.session_state.get("pending_text")}:
        st.session_state.messages.pop()
    st.rerun()
except APIError:
    st.session_state.last_error = "No se pudo obtener la respuesta ahora. Reintenta tu mensaje; tu avance anterior sigue disponible."
    if st.session_state.messages and st.session_state.messages[-1] == {"role": "user", "content": st.session_state.get("pending_text")}:
        st.session_state.messages.pop()
    st.rerun()
except Exception:
    st.session_state.last_error = "Ocurrió un problema. Guarda el avance y avisa al organizador."
    if st.session_state.messages and st.session_state.messages[-1] == {"role": "user", "content": st.session_state.get("pending_text")}:
        st.session_state.messages.pop()
    st.rerun()
