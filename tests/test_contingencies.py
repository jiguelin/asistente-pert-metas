"""Offline regressions for one optional replacement and its real calendar."""
import json
import unittest
from copy import deepcopy
from datetime import date
from pathlib import Path

from contingencies import business_day, capacity_schedule, compile_replacement
from motor_pert import verificar
from pert_core import PlanError, audit_plan


def company_case():
    # The fictional case travels with the tests; no conversation or API needed.
    fixture_path = Path(__file__).resolve().parent / "fixtures/empresa_reposicion.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    plan, facts = fixture["plan"], fixture["facts"]
    plan["capacidad"] = capacity_schedule(facts)
    compile_replacement(plan, facts)
    return plan, facts


class ContingencyTests(unittest.TestCase):
    def test_real_case_has_one_note_and_four_exclusive_routes(self):
        plan, _ = company_case()
        audited = audit_plan(plan)
        motor = audited["motor"]
        self.assertEqual(len([n for n in plan["notas"] if n["id"] == "T10"]), 1)
        self.assertFalse(any(s["id"] == "T10" for s in plan["sesiones"]))
        group, = plan["contingencias"]
        self.assertEqual(group["max_activaciones"], 1)
        self.assertEqual(len(group["rutas"]), 4)
        self.assertEqual({r["activacion"]["fecha"] for r in group["rutas"]},
                         {s["fecha"] for s in plan["sesiones"] if s["id"] == "T8"})
        self.assertEqual(motor["minutos_base"], 765)
        self.assertEqual(motor["minutos_condicionales_maximos"], 40)
        self.assertEqual(motor["minutos_totales"], 805)
        self.assertEqual(motor["minutos_por_tarea"]["T10"], 40)
        self.assertEqual(motor["papelografos"], 3)

    def test_each_route_respects_capacity_and_real_courier_dates(self):
        plan, _ = company_case()
        for route in plan["contingencias"][0]["rutas"]:
            with self.subTest(activation=route["activacion"]["fecha"]):
                self.assertEqual(sum(s["minutos"] for s in route["sesiones"]), 40)
                order = date.fromisoformat(route["pedido"])
                arrival = date.fromisoformat(route["llegada_reemplazo"])
                check = date.fromisoformat(route["revision_reemplazo"])
                send = date.fromisoformat(route["reenvio"])
                delivery = date.fromisoformat(route["entrega_reemplazo"])
                confirm = date.fromisoformat(route["confirmacion"])
                self.assertLess(order.weekday(), 5)
                self.assertEqual(arrival, business_day(order, 1))
                self.assertGreaterEqual(check, arrival)
                self.assertLess(send.weekday(), 6)
                self.assertGreaterEqual(send, check)
                self.assertEqual(delivery, business_day(send, 2))
                self.assertGreaterEqual(confirm, delivery)
                self.assertLessEqual(confirm, date(2026, 11, 13))
                scenario = deepcopy(plan)
                next(n for n in scenario["notas"] if n["id"] == "T10")["condicional"] = False
                scenario["sesiones"] += route["sesiones"]
                scenario["dependencias_evento"] += route["dependencias_evento"]
                self.assertEqual(verificar(scenario)["errores"], [])
        latest = plan["contingencias"][0]["rutas"][-1]
        self.assertEqual((latest["pedido"], latest["reenvio"], latest["confirmacion"]),
                         ("2026-11-10", "2026-11-11", "2026-11-13"))

    def test_recompilation_preserves_normal_work_and_routes(self):
        plan, facts = company_case()
        original = deepcopy(plan)
        compile_replacement(plan, facts)
        self.assertEqual(plan, original)

    def test_no_damage_keeps_base_work_only(self):
        plan, _ = company_case()
        result = verificar(plan)
        self.assertTrue(result["ok"])
        self.assertEqual(result["minutos_totales"], 765)
        self.assertNotIn("T10", result["minutos_por_tarea"])

    def test_conditional_task_cannot_also_be_mandatory(self):
        plan, _ = company_case()
        plan["sesiones"].append({"id": "T10", "fecha": "2026-11-13", "minutos": 1})
        with self.assertRaises(PlanError):
            audit_plan(plan)

    def test_duplicate_groups_are_rejected(self):
        plan, _ = company_case()
        group = plan["contingencias"][0]
        duplicate = deepcopy(group)
        group["rutas"] = group["rutas"][:1]
        duplicate["rutas"] = duplicate["rutas"][1:2]
        plan["contingencias"].append(duplicate)
        with self.assertRaises(PlanError):
            audit_plan(plan)

    def test_missing_or_duplicate_activation_is_rejected(self):
        for change in ("missing", "duplicate", "fake"):
            plan, _ = company_case()
            routes = plan["contingencias"][0]["rutas"]
            if change == "missing":
                routes.pop()
            elif change == "duplicate":
                routes.append(deepcopy(routes[0]))
            else:
                routes[0]["activacion"]["fecha"] = "2026-10-13"
            with self.subTest(change=change), self.assertRaises(PlanError):
                audit_plan(plan)

    def test_route_cannot_omit_approved_work_or_event_edges(self):
        for change in ("minutes", "edges"):
            plan, _ = company_case()
            route = plan["contingencias"][0]["rutas"][0]
            if change == "minutes":
                route["sesiones"][0]["minutos"] -= 1
            else:
                route["dependencias_evento"] = []
            with self.subTest(change=change), self.assertRaises(PlanError):
                audit_plan(plan)

    def test_invalid_route_date_is_reported_as_plan_error(self):
        plan, _ = company_case()
        plan["contingencias"][0]["rutas"][0]["sesiones"][0]["fecha"] = "2026-02-30"
        with self.assertRaises(PlanError):
            audit_plan(plan)

    def test_stage_dates_and_connected_delivery_deadline_are_rechecked(self):
        for change in ("transit", "pickup", "deadline"):
            plan, _ = company_case()
            route = plan["contingencias"][0]["rutas"][-1]
            if change == "transit":
                route["llegada_reemplazo"] = "2026-11-10"
            elif change == "pickup":
                route["reenvio"] = "2026-11-08"
            else:
                route["confirmacion"] = "2026-11-14"
                route["sesiones"][-1]["fecha"] = "2026-11-14"
                route["dependencias_evento"][-1][-1] = "2026-11-14"
                next(n for n in plan["notas"] if n["id"] == "T10")["fin"] = "2026-11-14"
            with self.subTest(change=change), self.assertRaises(PlanError):
                audit_plan(plan)

    def test_recorded_courier_rules_are_rechecked(self):
        for field, value in (("reposicion_habiles", 2), ("entrega_habiles", 3),
                             ("recogida_sabados", False)):
            plan, _ = company_case()
            plan["contingencias"][0]["calendario"][field] = value
            with self.subTest(field=field), self.assertRaises(PlanError):
                audit_plan(plan)

    def test_courier_without_saturday_pickup_uses_weekdays(self):
        plan, facts = company_case()
        facts["recogida_sabados"] = "false"
        compile_replacement(plan, facts)
        for route in plan["contingencias"][0]["rutas"]:
            self.assertLess(date.fromisoformat(route["reenvio"]).weekday(), 5)
        audit_plan(plan)

    def test_capacity_exception_moves_replacement_without_overbooking(self):
        plan, facts = company_case()
        facts["excepciones_tiempo"] = '{"2026-10-15":0}'
        plan["capacidad"] = capacity_schedule(facts)
        compile_replacement(plan, facts)
        route = plan["contingencias"][0]["rutas"][0]
        self.assertEqual(route["pedido"], "2026-10-16")
        self.assertEqual(route["llegada_reemplazo"], "2026-10-19")
        self.assertFalse(any(s["fecha"] == "2026-10-15" for s in route["sesiones"]))
        audit_plan(plan)

    def test_no_space_before_delivery_deadline_blocks_compilation(self):
        plan, facts = company_case()
        plan["capacidad"].update({day: 0 for day in plan["capacidad"] if day >= "2026-11-11"})
        with self.assertRaisesRegex(ValueError, "No hay tiempo"):
            compile_replacement(plan, facts)


if __name__ == "__main__":
    unittest.main()
