"""Goal clarification must not erase a student's already completed intake."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from intake import normalize, stage
from pert_assistant import respond
from progress import export_progress, import_progress


GOAL = "Pesar 70 kilos con músculos marcados, abdomen marcado y alta energía"
CRITERION = "Pesar 70 kg, con músculos y abdomen marcados, y alta energía"
ACCEPTED = {"meta": GOAL, "criterio": CRITERION}
USERS = [
    GOAL + " para el 30 de marzo de 2027.",
    "El 1 de octubre de 2026.",
    "Estoy pilas, con energía y feliz.",
    "Actualmente peso 66.5 kilos y tomo cinco cafés al día.",
    "El obstáculo principal es la constancia.",
    "Tengo dos horas diarias o una hora y media diaria.",
]


def known_facts():
    return {
        "meta": GOAL,
        "criterio": CRITERION,
        "inicio": "2026-10-01",
        "fin": "2027-03-30",
        "situacion": "Peso 66.5 kg y tomo cinco cafés al día.",
        "obstaculos": "Falta de tiempo, constancia y dieta en eventos.",
        "principal": "Constancia",
        "habilidades": "Disciplina, administrar el tiempo y decir no.",
        "apoyos": "Mi equipo y mis coaches.",
        "disponibilidad": "90 a 120 minutos diarios",
        "minutos_semana": "[90,90,90,90,90,90,90]",
    }


def payload(term="feliz", verified=False, changed=False, change_quote=None, facts=None):
    return {
        "meta_verificable": verified,
        "ambiguedad_esencial": term,
        "meta_cambiada": changed,
        "cambio_meta_cita": change_quote,
        "hechos": facts or [],
    }


def fact(field, value, quote, index=0):
    return {"campo": field, "valor": value, "usuario": index, "cita": quote}


def response(data):
    return SimpleNamespace(output_text=json.dumps(data, ensure_ascii=False), usage=None)


class GoalContinuityTests(unittest.TestCase):
    def test_accepted_health_goal_survives_reclassified_emotional_preference(self):
        snapshot = normalize(payload(), USERS, known_facts(), accepted_goal=ACCEPTED)
        self.assertTrue(snapshot["meta_verificable"])
        self.assertIsNone(snapshot["ambiguedad_esencial"])
        self.assertEqual(snapshot["goal_validation"], ACCEPTED)
        self.assertEqual(snapshot["facts"]["criterio"], CRITERION)
        self.assertEqual(stage(snapshot), "mini")

    def test_weight_update_is_situation_not_new_goal(self):
        users = USERS + ["Ahora peso 67 kilos, pero mi meta sigue siendo 70 kilos."]
        new = payload(facts=[fact("situacion", "Peso actual 67 kg", users[-1], len(users)-1)])
        snapshot = normalize(new, users, known_facts(), accepted_goal=ACCEPTED)
        self.assertEqual(snapshot["facts"]["meta"], GOAL)
        self.assertEqual(snapshot["facts"]["situacion"], "Peso actual 67 kg")
        self.assertEqual(stage(snapshot), "mini")

    def test_extractor_rewording_cannot_replace_accepted_criterion(self):
        new = payload(facts=[
            fact("meta", "Sentirme feliz", USERS[2], 2),
            fact("criterio", "Sentirme feliz todo el tiempo", USERS[2], 2),
        ])
        snapshot = normalize(new, USERS, known_facts(), accepted_goal=ACCEPTED)
        self.assertEqual(snapshot["facts"]["meta"], GOAL)
        self.assertEqual(snapshot["facts"]["criterio"], CRITERION)
        self.assertEqual(snapshot["goal_validation"], ACCEPTED)
        self.assertEqual(stage(snapshot), "mini")

    def test_unaccepted_report_clarification_stays_essential(self):
        users = ["Quiero crear un reporte profesional.", "Bien presentado."]
        new = payload(term="Bien presentado", facts=[
            fact("meta", "Crear un reporte profesional", users[0])])
        snapshot = normalize(new, users, accepted_goal=None)
        self.assertFalse(snapshot["meta_verificable"])
        self.assertIsNone(snapshot["goal_validation"])
        self.assertEqual(stage(snapshot), "criterio")

    def test_explicit_new_goal_reopens_criteria_and_removes_old_approvals(self):
        change = "Ya no quiero pesar 70 kilos; ahora quiero aprender Excel profesional."
        users = USERS + [change]
        old = known_facts()
        old.update(mini_aprobadas="true", tareas_aprobadas="true")
        new = payload(term="profesional", changed=True, change_quote=change, facts=[
            fact("meta", "Aprender Excel profesional", change, len(users)-1),
            fact("criterio", "Usar Excel de manera profesional", change, len(users)-1),
        ])
        snapshot = normalize(new, users, old, accepted_goal=ACCEPTED)
        self.assertFalse(snapshot["meta_verificable"])
        self.assertIsNone(snapshot["goal_validation"])
        self.assertEqual(snapshot["facts"]["meta"], "Aprender Excel profesional")
        self.assertNotEqual(snapshot["facts"].get("mini_aprobadas"), "true")
        self.assertNotEqual(snapshot["facts"].get("tareas_aprobadas"), "true")
        self.assertEqual(stage(snapshot), "criterio")

    def test_change_quote_from_old_user_cannot_reopen_accepted_goal(self):
        old_change = "Ahora quiero aprender Excel profesional."
        users = [old_change] + USERS
        new = payload(term="profesional", changed=True, change_quote=old_change, facts=[
            fact("meta", "Aprender Excel profesional", old_change),
        ])
        snapshot = normalize(new, users, known_facts(), accepted_goal=ACCEPTED)
        self.assertTrue(snapshot["meta_verificable"])
        self.assertIsNone(snapshot["ambiguedad_esencial"])
        self.assertEqual(snapshot["facts"]["meta"], GOAL)
        self.assertEqual(stage(snapshot), "mini")

    def test_change_without_source_quote_cannot_reopen_accepted_goal(self):
        new = payload(changed=True, change_quote="Cambio inexistente")
        snapshot = normalize(new, USERS, known_facts(), accepted_goal=ACCEPTED)
        self.assertEqual(snapshot["goal_validation"], ACCEPTED)
        self.assertEqual(stage(snapshot), "mini")

    def test_first_observable_goal_asks_start_not_energy(self):
        user = GOAL + " para el 30 de marzo de 2027."
        extracted = payload(term=None, verified=True, facts=[
            fact("meta", GOAL, GOAL),
            fact("criterio", CRITERION, GOAL),
            fact("fin", "2027-03-30", "30 de marzo de 2027"),
        ])
        with patch("pert_assistant._create", return_value=response(extracted)) as create:
            reply, finalize, usage = respond(None, "test", [{"role": "user", "content": user}], "2026-09-29")
        self.assertEqual(reply, "¿En qué fecha quieres empezar, con día, mes y año?")
        self.assertFalse(finalize)
        self.assertIsNotNone(usage["snapshot"]["goal_validation"])
        self.assertEqual(create.call_count, 1)

    def test_completed_intake_proposes_mini_goals_despite_spurious_feliz(self):
        messages = [{"role": "user", "content": text} for text in USERS]
        proposed = "M1: rutina acordada y registrada. ¿Aceptas esta propuesta de mini metas?"
        with patch("pert_assistant._create", side_effect=[
            response(payload()), response({"reply": proposed, "finalize": False}),
        ]) as create, patch("pert_assistant.review", return_value={"ok": True, "problems": []}) as review:
            reply, finalize, usage = respond(None, "test", messages, "2026-09-29",
                                            known_facts=known_facts(), accepted_goal=ACCEPTED)
        self.assertEqual(reply, proposed)
        self.assertFalse(finalize)
        self.assertEqual(stage(usage["snapshot"]), "mini")
        self.assertEqual(create.call_count, 2)
        self.assertEqual(review.call_args.args[5], "mini")

    def test_essential_report_term_gets_one_question_in_respond(self):
        messages = [{"role": "user", "content": "Quiero crear un reporte profesional."},
                    {"role": "assistant", "content": "¿Qué significa profesional?"},
                    {"role": "user", "content": "Bien presentado."}]
        extracted = payload(term="Bien presentado", facts=[
            fact("meta", "Crear un reporte profesional", messages[0]["content"])])
        with patch("pert_assistant._create", return_value=response(extracted)) as create:
            reply, finalize, usage = respond(None, "test", messages, "2026-09-29")
        self.assertIn("«Bien presentado»", reply)
        self.assertEqual(reply.count("¿"), 1)
        self.assertEqual(reply.count("?"), 1)
        self.assertFalse(finalize)
        self.assertEqual(stage(usage["snapshot"]), "criterio")
        self.assertEqual(create.call_count, 1)

    def test_vague_report_answer_receives_concrete_proposal_not_another_definition(self):
        messages = [
            {"role": "user", "content": "Quiero crear un reporte profesional."},
            {"role": "assistant", "content": "Para poder comprobar la meta, ¿qué característica concreta debe cumplirse cuando dices «profesional»?"},
            {"role": "user", "content": "Bien presentado."},
        ]
        extracted = payload(term="Bien presentado", facts=[
            fact("meta", "Crear un reporte profesional", messages[0]["content"])])
        proposal = ("Propongo comprobar que el reporte tenga título, columnas identificadas "
                    "y una tabla legible sin texto cortado. ¿Aceptas esta comprobación?")
        with patch("pert_assistant._create", side_effect=[
            response(extracted), response({"reply": proposal, "finalize": False}),
        ]) as create, patch("pert_assistant.review", return_value={"ok": True, "problems": []}) as review:
            reply, finalize, usage = respond(None, "test", messages, "2026-09-29")
        self.assertEqual(reply, proposal)
        self.assertEqual(reply.count("¿"), 1)
        self.assertFalse(finalize)
        self.assertEqual(stage(usage["snapshot"]), "criterio")
        self.assertIsNone(usage["snapshot"]["goal_validation"])
        self.assertEqual(create.call_count, 2)
        self.assertEqual(review.call_args.args[5], "criterio")

    def test_cold_resume_reextracts_history_without_trusting_saved_goal_certificate(self):
        messages = [{"role": "user", "content": GOAL + " para el 30 de marzo de 2027."},
                    {"role": "assistant", "content": "¿En qué fecha quieres empezar, con día, mes y año?"}]
        saved = json.loads(export_progress(messages, None))
        # User-uploaded files are untrusted. A forged verification decision is
        # ignored; a cold session reextracts meaning from its conversation.
        saved["accepted_goal"] = {"meta": "Una meta distinta", "criterio": "Sin comprobar"}
        loaded = import_progress(json.dumps(saved).encode())
        self.assertNotIn("accepted_goal", loaded)
        self.assertNotIn("known_facts", loaded)
        loaded["messages"].append({"role": "user", "content": "El 1 de octubre de 2026."})
        extracted = payload(term=None, verified=True, facts=[
            fact("meta", GOAL, GOAL),
            fact("criterio", CRITERION, GOAL),
            fact("fin", "2027-03-30", "30 de marzo de 2027"),
            fact("inicio", "2026-10-01", "1 de octubre de 2026", 1),
        ])
        with patch("pert_assistant._create", return_value=response(extracted)) as create:
            reply, finalize, usage = respond(None, "test", loaded["messages"], "2026-09-29")
        self.assertIn("¿Cuál es tu situación actual respecto a esta meta?", reply)
        self.assertNotIn("energía»", reply)
        self.assertFalse(finalize)
        self.assertEqual(usage["snapshot"]["goal_validation"], ACCEPTED)
        self.assertEqual(stage(usage["snapshot"]), "situacion")
        self.assertEqual(create.call_count, 1)


if __name__ == "__main__":
    unittest.main()
