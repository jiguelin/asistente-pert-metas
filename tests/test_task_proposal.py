from copy import deepcopy
import json
import unittest

import task_proposal as compiler
from task_proposal import SCHEMA, prepare_proposal


def facts(minutes=75):
    return {"inicio": "2026-10-01", "fin": "2027-03-31",
            "minutos_semana": json.dumps([minutes] * 7),
            "mini_ids": ["M1", "M2", "M3", "M4", "M5", "M6", "MP"]}


def task(ident="T1", minutes=45):
    return {"id": ident, "titulo": "Entrenar con el método del coach",
            "detalle": "Preparar, practicar y registrar dentro del mismo bloque.",
            "inicio": "2026-10-01", "fin": "2027-03-31", "dias": list(range(7)),
            "minutos": minutes, "fechas": [], "excluir": [], "excepciones": [],
            "habilita": ["M1", "M2", "M3", "M4", "M5", "M6", "MP"],
            "requisitos": [], "orden_sesion": [],
            "pasos": [{"accion": "Preparar", "minutos": 5},
                      {"accion": "Practicar", "minutos": minutes - 10},
                      {"accion": "Registrar y revisar", "minutos": 5}]}


class TaskProposalTests(unittest.TestCase):
    def test_reported_182_day_budget_has_364_sessions_and_no_duplicate_notes(self):
        data = {"tareas": [task("T1", 45), task("T2", 30)]}
        original = deepcopy(data)
        reply, plan = prepare_proposal(data, facts())
        self.assertEqual(data, original)
        self.assertEqual(len(plan["notas"]), 2)
        self.assertEqual(plan["sesiones_totales"], 364)
        self.assertEqual(plan["minutos_totales"], 13650)
        self.assertEqual(plan["maximo_minutos_dia"], 75)
        self.assertEqual(plan["cargas_por_dia"]["2026-10-01"], 75)
        self.assertEqual(plan["cargas_por_dia"]["2027-03-31"], 75)
        self.assertEqual(plan["resumen_sesiones_calculado"][0]["cantidad_sesiones"], 182)
        self.assertEqual(plan["resumen_sesiones_calculado"][1]["minutos_totales"], 5460)
        self.assertEqual(len(plan["recurrencias"]), 2)
        self.assertLess(len(reply.split()), 400)
        self.assertIn("182 sesiones; 8190 min (136 h 30 min)", reply)
        self.assertIn("Carga total: 364 sesiones; 13650 min (227 h 30 min)", reply)
        self.assertEqual(reply.count("¿"), 1)
        self.assertTrue(reply.endswith("¿Aceptas esta propuesta de tareas y horarios?"))

    def test_extra_task_cannot_exceed_daily_conservative_capacity(self):
        data = {"tareas": [task("T1", 45), task("T2", 30), task("T3", 15)]}
        with self.assertRaisesRegex(compiler.PlanError, "Carga diaria 2026-10-01: 90 min; disponible 75"):
            prepare_proposal(data, facts())

    def test_confirmed_capacity_exception_is_respected(self):
        f = facts()
        f["excepciones_tiempo"] = '{"2026-12-25":0}'
        data = {"tareas": [task()]}
        with self.assertRaisesRegex(compiler.PlanError, "Carga diaria 2026-12-25"):
            prepare_proposal(data, f)
        data["tareas"][0]["excluir"] = ["2026-12-25"]
        reply, plan = prepare_proposal(data, f)
        self.assertEqual(plan["sesiones_totales"], 181)
        self.assertIn("sin sesión: 2026-12-25", reply)

    def test_learning_daily_practice_and_point_simulators_have_session_order(self):
        practice, simulator = task("T1", 45), task("T2", 30)
        simulator.update(titulo="Simulacro y corrección", dias=[], fechas=["2026-10-03", "2026-10-10"],
                         orden_sesion=["T1"], habilita=["M1"])
        reply, plan = prepare_proposal({"tareas": [practice, simulator]}, facts())
        self.assertEqual(plan["sesiones_totales"], 184)
        self.assertEqual(plan["dependencias"], [])
        self.assertEqual(plan["dependencias_sesion"], [["T1", "T2"]])
        self.assertEqual(plan["dependencias_evento"], [])
        self.assertIn("fechas puntuales: 2026-10-03, 2026-10-10", reply)
        self.assertIn("En cada fecha de esta tarea, realizar antes: T1", reply)

    def test_session_order_must_have_previous_execution_on_every_successor_date(self):
        first, following = task("T1", 30), task("T2", 30)
        first.update(dias=[], fechas=["2026-10-03"])
        following.update(dias=[], fechas=["2026-10-03", "2026-10-10"], orden_sesion=["T1"])
        with self.assertRaisesRegex(compiler.PlanError, "Falta sesión previa T1→T2: 2026-10-10"):
            prepare_proposal({"tareas": [first, following]}, facts())

    def test_global_dependencies_use_complete_task_spans(self):
        first, following = task("T1", 30), task("T2", 30)
        first.update(fin="2026-10-02")
        following.update(inicio="2026-10-03", requisitos=["T1"])
        reply, plan = prepare_proposal({"tareas": [first, following]}, facts())
        self.assertEqual(plan["dependencias"], [["T1", "T2"]])
        self.assertIn("Requiere terminar antes: T1", reply)
        following["inicio"] = "2026-10-01"
        with self.assertRaisesRegex(compiler.PlanError, "Precedencia global imposible"):
            prepare_proposal({"tareas": [first, following]}, facts())

    def test_exclusions_and_overrides_have_exact_counts_minutes_and_steps(self):
        t = task("T1", 45)
        t.update(fin="2026-10-07", dias=[0, 1, 2, 3, 4], fechas=["2026-10-03"],
                 excluir=["2026-10-02"], excepciones=[
                     {"fecha": "2026-10-05", "minutos": 20, "pasos": [{"accion": "Practicar y registrar", "minutos": 20}]},
                     {"fecha": "2026-10-06", "minutos": 0, "pasos": []},
                     {"fecha": "2026-10-03", "minutos": 15, "pasos": [{"accion": "Repasar y registrar", "minutos": 15}]}])
        reply, plan = prepare_proposal({"tareas": [t]}, facts())
        self.assertEqual([(s["fecha"], s["minutos"]) for s in plan["sesiones"]],
                         [("2026-10-01", 45), ("2026-10-03", 15), ("2026-10-05", 20), ("2026-10-07", 45)])
        self.assertEqual(plan["minutos_totales"], 125)
        self.assertIn("2026-10-05 = 20 min (Practicar y registrar 20 min)", reply)
        self.assertIn("2026-10-06 = 0 min (sin sesión)", reply)

    def test_point_dates_can_be_excluded_and_do_not_invent_weekly_recurrence(self):
        t = task()
        t.update(dias=[], fechas=["2026-10-03", "2026-10-10"], excluir=["2026-10-10"])
        _, plan = prepare_proposal({"tareas": [t]}, facts())
        self.assertEqual(plan["recurrencias"], [])
        self.assertEqual(plan["sesiones"], [{"id": "T1", "fecha": "2026-10-03", "minutos": 45}])

    def test_duplicate_task_or_execution_is_never_silently_consolidated(self):
        cases = [{"tareas": [task(), task()]},
                 {"tareas": [dict(task(), fechas=["2026-10-01"])]},
                 {"tareas": [dict(task(), dias=[], fechas=["2026-10-01"] * 2)]},
                 {"tareas": [dict(task(), dias=[0, 0])]}]
        for data in cases:
            original = deepcopy(data)
            with self.subTest(data=data), self.assertRaises(compiler.PlanError):
                prepare_proposal(data, facts())
            self.assertEqual(data, original)

    def test_unknown_or_self_dependency_and_unknown_milestone_are_rejected(self):
        for update in ({"requisitos": ["T99"]}, {"orden_sesion": ["T99"]},
                       {"requisitos": ["T1"]}, {"habilita": ["M99"]},
                       {"habilita": ["T2"]}, {"habilita": []}):
            with self.subTest(update=update), self.assertRaises(compiler.PlanError):
                prepare_proposal({"tareas": [dict(task(), **update)]}, facts())

    def test_cycles_in_session_order_are_rejected(self):
        first, following = task("T1", 30), task("T2", 30)
        first["orden_sesion"] = ["T2"]
        following["orden_sesion"] = ["T1"]
        with self.assertRaisesRegex(compiler.PlanError, "Ciclo en dependencias"):
            prepare_proposal({"tareas": [first, following]}, facts())

    def test_invalid_values_dates_and_unapproved_fields_are_rejected(self):
        changes = [{"minutos": value} for value in (0, -1, True, float("inf"), float("nan"), 2**2000, [45])]
        changes += [{"inicio": "2026-09-30"}, {"fin": "2027-04-01"}, {"inicio": "20261001"},
                    {"dias": [True]}, {"dias": [7]}, {"dias": [], "fechas": []},
                    {"condicional": True}, {"habilita": ["M1", "M1"]},
                    {"excluir": ["2027-04-01"]}, {"excluir": ["2026-10-01"] * 2},
                    {"excepciones": [{"fecha": "2026-10-01", "minutos": 20, "pasos": [{"accion": "Estudiar", "minutos": 30}]}]},
                    {"pasos": [{"accion": "Entrenar", "minutos": 50}]},
                    {"pasos": [{"accion": "Entrenar", "minutos": True}]},
                    {"excepciones": [{"fecha": "2026-10-01", "minutos": 20}]}]
        for update in changes:
            with self.subTest(update=update), self.assertRaises(compiler.PlanError):
                prepare_proposal({"tareas": [dict(task(), **update)]}, facts())

    def test_capacity_must_be_confirmed_finite_and_not_boolean(self):
        for update in ({"minutos_semana": "[true,75,75,75,75,75,75]"},
                       {"minutos_semana": "[NaN,75,75,75,75,75,75]"},
                       {"minutos_semana": "[75,75]"},
                       {"excepciones_tiempo": '{"2026-10-01":true}'},
                       {"minutos_semana": None}):
            with self.subTest(update=update), self.assertRaises(compiler.PlanError):
                prepare_proposal({"tareas": [task()]}, dict(facts(), **update))
        f = facts()
        del f["minutos_semana"]
        with self.assertRaisesRegex(compiler.PlanError, "Faltan días y minutos"):
            prepare_proposal({"tareas": [task()]}, f)

    def test_ten_year_guard_runs_before_expanding_any_calendar(self):
        f = facts()
        f["fin"] = "2036-10-02"
        t = task()
        t["fin"] = f["fin"]
        with self.assertRaisesRegex(compiler.PlanError, "no puede superar diez años"):
            prepare_proposal({"tareas": [t]}, f)

    def test_generated_text_cannot_add_a_second_question(self):
        for field in ("titulo", "detalle"):
            t = task()
            t[field] = "¿Quieres entrenar?"
            with self.subTest(field=field), self.assertRaisesRegex(compiler.PlanError, "otra pregunta"):
                prepare_proposal({"tareas": [t]}, facts())

    def test_every_schema_field_is_required_and_additional_properties_are_forbidden(self):
        t = SCHEMA["properties"]["tareas"]["items"]
        self.assertFalse(SCHEMA["additionalProperties"])
        self.assertFalse(t["additionalProperties"])
        self.assertEqual(set(t["required"]), set(task()))
        exception = t["properties"]["excepciones"]["items"]
        self.assertEqual(set(exception["required"]), {"fecha", "minutos", "pasos"})
        for key in task():
            item = task()
            del item[key]
            with self.subTest(key=key), self.assertRaises(compiler.PlanError):
                prepare_proposal({"tareas": [item]}, facts())


if __name__ == "__main__":
    unittest.main()
