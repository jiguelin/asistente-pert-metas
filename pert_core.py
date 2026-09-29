"""Checks and canonical output for a physical PERT plan.

The model drafts the meaning of a plan; this module refuses to certify a
montage unless the deterministic checker and output inventory agree.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from typing import Any

from motor_pert import verificar


class PlanError(ValueError):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


REQUIRED = {"inicio", "fin", "periodos", "notas", "sesiones", "capacidad",
            "dependencias", "conexiones", "materiales", "pendientes"}


def _assert_schema(plan: dict[str, Any]) -> None:
    errors = []
    missing = REQUIRED - plan.keys()
    if missing:
        errors.append("Faltan campos: " + ", ".join(sorted(missing)))
    if not isinstance(plan.get("notas"), list) or not plan.get("notas"):
        errors.append("Falta el inventario de notas")
    if not isinstance(plan.get("periodos"), list) or not plan.get("periodos"):
        errors.append("Faltan periodos reales")
    if not isinstance(plan.get("sesiones"), list):
        errors.append("Faltan sesiones programadas")
    if not isinstance(plan.get("capacidad"), dict):
        errors.append("Falta capacidad por fecha")
    if not isinstance(plan.get("materiales"), dict):
        errors.append("Faltan medidas confirmadas")
    if errors:
        raise PlanError(errors)


def audit_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Validate, then enrich with a lossless manifest for PDF and UI.

    This does not validate subjective evidence, financial assumptions, or
    semantic suitability of milestones. The model must audit those separately.
    """
    if not isinstance(plan, dict):
        raise PlanError(["El plan no es un objeto JSON"])
    _assert_schema(plan)
    try:
        result = verificar(plan)
    except (TypeError, KeyError, ValueError, IndexError, ZeroDivisionError) as exc:
        raise PlanError([f"Estructura del plan inválida: {type(exc).__name__}"]) from exc
    errors = list(result["errores"])
    if "posiciones" not in result:
        raise PlanError(errors or ["No se pudo asignar posición a las notas"])
    notes = plan["notas"]
    ids = [n.get("id") for n in notes]
    if any(not isinstance(i, str) or not i for i in ids):
        errors.append("Cada nota necesita un ID")
    positions = {x["id"]: x for x in result["posiciones"]}
    if set(positions) != set(ids) or len(result["posiciones"]) != len(notes):
        errors.append("Inventario y posiciones no coinciden")
    if sum(n.get("tipo") == "MP" for n in notes) != 1:
        errors.append("Debe existir una sola Meta Principal")
    if any(n.get("tipo") == "MP" and n.get("fin") != plan["fin"] for n in notes):
        errors.append("Fecha final de MP diferente al límite")
    if any(n.get("tipo") in ("M", "T") and not n.get("texto") for n in notes):
        errors.append("Falta texto en hito o tarea")
    if not 1 <= len(plan["periodos"]):
        errors.append("Faltan periodos")
    if any(not 1 <= k <= 3 for k in (result["periodos_por_papel"] or [])):
        errors.append("Más de tres columnas en un papelógrafo")
    if errors:
        raise PlanError(errors)

    byid = {n["id"]: n for n in notes}
    graph_before: dict[str, set[str]] = defaultdict(set)
    graph_after: dict[str, set[str]] = defaultdict(set)
    edges: list[dict[str, str]] = []
    for previous, following in plan["dependencias"]:
        graph_before[following].add(previous)
        graph_after[previous].add(following)
        edges.append({"desde": previous, "hacia": following, "tipo": "requisito"})
    for previous, following in plan.get("dependencias_sesion", []):
        graph_before[following].add(previous + " (cada sesión)")
        graph_after[previous].add(following + " (cada sesión)")
        edges.append({"desde": previous, "hacia": following, "tipo": "cada sesión"})
    for previous, dx, following, dy in plan.get("dependencias_evento", []):
        label = f"por evento {dx}→{dy}"
        graph_before[following].add(previous + " (" + label + ")")
        graph_after[previous].add(following + " (" + label + ")")
        edges.append({"desde": previous, "hacia": following, "tipo": label})
    for previous, following, label in plan["conexiones"]:
        graph_before[following].add(previous + " (" + label + ")")
        graph_after[previous].add(following + " (" + label + ")")
        edges.append({"desde": previous, "hacia": following, "tipo": label})
    inventory = []
    for n in notes:
        item = dict(n)
        item["posicion"] = positions[n["id"]]
        item["predecesores"] = sorted(graph_before[n["id"]])
        item["sucesores"] = sorted(graph_after[n["id"]])
        item["minutos_totales"] = result["minutos_por_tarea"].get(n["id"])
        inventory.append(item)
    if any(edge["desde"] not in byid or edge["hacia"] not in byid for edge in edges):
        raise PlanError(["Hay flechas con ID inexistente"])

    # Paper boundaries are derived from the same result that yielded positions.
    columns = []
    grouped = result["periodos_por_papel"]
    first_period = 0
    W = float(plan["materiales"]["papel"][0])
    zone = max(18.0, float(plan["materiales"]["meta"][0]) + 3)
    for paper, count in enumerate(grouped, 1):
        available = W - 6 - (zone if paper == len(grouped) else 0)
        width = available / count
        for column in range(count):
            period = plan["periodos"][first_period + column]
            columns.append({"papel": paper, "columna": column + 1,
                            "inicio": period["inicio"], "fin": period["fin"],
                            "x_inicial": round(3 + column * width, 2),
                            "x_final": round(3 + (column + 1) * width, 2)})
        first_period += count
    return {"plan": plan, "motor": result, "notas": inventory, "flechas": edges,
            "columnas": columns,
            "zona_mp": {"papel": len(grouped), "x_inicial": round(W - 3 - zone, 2),
                         "x_final": round(W - 3, 2)},
            "notas_pequenas": len(notes) - 1,
            "notas_totales": len(notes),
            "tipos": dict(Counter(n["tipo"] for n in notes))}


def summary(audit: dict[str, Any]) -> str:
    r = audit["motor"]
    dens = "; ".join(
        f"P{d['papel']} C{d['columna']}: {sum(d['conteo'].values())} notas, "
        f"{d['capacidad_fila'] - d['maximo_usado']} plazas libres en la fila más ocupada"
        for d in r["densidad"]
    )
    return (f"{r['dias_inclusivos']} días inclusivos; {r['minutos_totales']} minutos "
            f"de tareas programadas; {r['papelografos']} papelógrafos; "
            f"{audit['notas_pequenas']} notas pequeñas + 1 MP. {dens}")
