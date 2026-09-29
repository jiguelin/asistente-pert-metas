import io
import json
import unittest

from pert_assistant import _user_visible_question_count
from pdf_export import export_pdf
from pert_core import PlanError, audit_plan, summary
from progress import export_progress, import_progress


def sample_plan():
    return {
        "inicio": "2026-10-01", "fin": "2026-10-31",
        "periodos": [{"inicio": "2026-10-01", "fin": "2026-10-31"}],
        "notas": [
            {"id": "T1", "tipo": "T", "texto": "Medir recorrido", "inicio": "2026-10-01",
             "fin": "2026-10-02", "evidencia": "Registro de distancia", "detalle": "Medir una ruta de 5 km"},
            {"id": "M1", "tipo": "M", "texto": "Ruta medida", "inicio": "2026-10-02",
             "fin": "2026-10-02", "evidencia": "Captura del mapa"},
            {"id": "O1", "tipo": "O", "texto": "Lluvia", "inicio": "2026-10-01",
             "fin": "2026-10-31", "evidencia": "Ruta techada"},
            {"id": "H1", "tipo": "H", "texto": "Medir distancias", "inicio": "2026-10-01",
             "fin": "2026-10-01", "evidencia": "Ruta de prueba de 1 km"},
            {"id": "A1", "tipo": "A", "texto": "Entrenador", "inicio": "2026-10-01",
             "fin": "2026-10-31", "evidencia": "Acompaña los domingos"},
            {"id": "MP", "tipo": "MP", "texto": "Cinco km caminados",
             "inicio": "2026-10-31", "fin": "2026-10-31",
             "evidencia": "Recorrido continuo y conversación al terminar"},
        ],
        "sesiones": [{"id": "T1", "fecha": "2026-10-01", "minutos": 20}],
        "capacidad": {"2026-10-01": 45}, "limite_semanal": None,
        "dependencias": [["T1", "M1"], ["M1", "MP"]],
        "dependencias_sesion": [], "dependencias_evento": [],
        "conexiones": [["O1", "T1", "riesgo"], ["A1", "T1", "apoyo"]],
        "finanzas": False, "caja": [], "pendientes": [],
        "materiales": {"papel": [90, 60], "nota": [3.8, 3.8], "meta": [15, 15],
                       "pared": 300},
    }


class ProductTests(unittest.TestCase):
    def test_complete_verified_inventory_and_pdf(self):
        audited = audit_plan(sample_plan())
        self.assertEqual(audited["notas_totales"], 6)
        self.assertEqual(audited["notas_pequenas"], 5)
        self.assertEqual(audited["motor"]["dias_inclusivos"], 31)
        self.assertEqual(audited["motor"]["minutos_totales"], 20)
        self.assertEqual(audited["zona_mp"]["x_inicial"], 69)
        self.assertEqual(audited["columnas"][0]["x_final"], 69)
        self.assertIn("A1 (apoyo)", next(n for n in audited["notas"] if n["id"] == "T1")["predecesores"])
        pdf = export_pdf(audited)
        self.assertTrue(pdf.startswith(b"%PDF-"))
        from pypdf import PdfReader
        all_text = " ".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
        for token in ("T1", "M1", "H1", "O1", "A1", "MP", "Flechas", "2026-10-31"):
            self.assertIn(token, all_text)
        self.assertIn("plazas libres", summary(audited))

    def test_invalid_dates_and_missing_budget_block_final(self):
        plan = sample_plan()
        plan["periodos"][0]["fin"] = "2026-10-30"
        with self.assertRaises(PlanError):
            audit_plan(plan)
        plan = sample_plan()
        plan["capacidad"]["2026-10-01"] = 10
        with self.assertRaises(PlanError):
            audit_plan(plan)

    def test_save_load_rechecks_plan_and_rejects_tampering(self):
        audited = audit_plan(sample_plan())
        msgs = [{"role": "user", "content": "Quiero caminar 5 km"}]
        raw = export_progress(msgs, audited)
        loaded = import_progress(raw)
        self.assertEqual(loaded["final"]["motor"]["dias_inclusivos"], 31)
        forged = json.loads(raw)
        forged["final"]["plan"]["pendientes"] = ["No tengo el papel"]
        with self.assertRaises(PlanError):
            import_progress(json.dumps(forged).encode())
        with self.assertRaises(ValueError):
            import_progress(b"not JSON")

    def test_question_check(self):
        self.assertEqual(_user_visible_question_count("¿Cuál es tu Meta Principal?"), 1)
        self.assertEqual(_user_visible_question_count("¿Cuándo empiezas? ¿Cuándo terminas?"), 2)


if __name__ == "__main__":
    unittest.main()
