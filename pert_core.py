"""Checks and canonical output for a physical PERT plan.

The model drafts the meaning of a plan; this module refuses to certify a
montage unless the deterministic checker and output inventory agree.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from copy import deepcopy
from typing import Any

from motor_pert import verificar
from contingencies import replacement_errors


class PlanError(ValueError):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


REQUIRED = {"inicio", "fin", "periodos", "notas", "sesiones", "capacidad",
            "dependencias", "conexiones", "materiales", "pendientes"}


def audit_with_scale(plan: dict[str, Any]) -> dict[str, Any]:
    """Coarsen only the physical calendar when the original layout cannot fit."""
    try:
        result = audit_plan(plan)
        if result['motor']['papelografos'] <= plan['materiales'].get('papelografos_disponibles', float('inf')):
            return result
        original = PlanError(['El montaje necesita más papelógrafos que los disponibles'])
    except PlanError as exc:
        original = exc
        if not any('pared' in p or 'No cabe' in p for p in exc.problems):
            raise
    candidate = deepcopy(plan)
    cursor, end = date.fromisoformat(plan['inicio']), date.fromisoformat(plan['fin'])
    periods = []
    while cursor <= end:
        following = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
        finish = min(end, following - timedelta(days=1))
        periods.append({'inicio': cursor.isoformat(), 'fin': finish.isoformat()})
        cursor = finish + timedelta(days=1)
    candidate['periodos'] = periods
    try:
        result = audit_plan(candidate)
        if result['motor']['papelografos'] <= candidate['materiales'].get('papelografos_disponibles', float('inf')):
            return result
    except PlanError:
        pass
    raise original


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
    conditional_ids={n['id'] for n in plan['notas'] if n.get('condicional')}
    groups=plan.get('contingencias',[])
    if conditional_ids!={g.get('id') for g in groups}:
        errors.append('Toda tarea condicional necesita rutas completas')
    if len(groups)!=len({g.get('id') for g in groups}):
        errors.append('Cada tarea condicional debe tener una sola contingencia')
    worst_days=defaultdict(float,result.get('cargas_por_dia',{}))
    worst_weeks=defaultdict(float)
    for day,minutes in result.get('cargas_por_dia',{}).items():
        worst_weeks[date.fromisoformat(day).isocalendar()[:2]]+=minutes
    result['minutos_base']=result.get('minutos_totales',0)
    result['minutos_condicionales_maximos']=0
    for group in groups:
        ident=group.get('id');routes=group.get('rutas',[])
        if ident not in conditional_ids or group.get('max_activaciones')!=1 or not routes:
            errors.append('Contingencia incompleta o no excluyente');continue
        try:
            errors.extend(replacement_errors(plan,group))
        except (TypeError, KeyError, ValueError, IndexError, ZeroDivisionError) as exc:
            errors.append(f'Ruta de {ident}: estructura inválida ({type(exc).__name__})');continue
        max_days=defaultdict(float);max_weeks=defaultdict(float);max_minutes=0
        for route in routes:
            sessions=route.get('sesiones',[])
            if not sessions or any(s.get('id')!=ident for s in sessions):
                errors.append('Sesiones de contingencia inválidas');continue
            scenario=deepcopy(plan)
            for n in scenario['notas']:
                if n['id']==ident:n['condicional']=False
            scenario['sesiones']+=sessions
            scenario['dependencias_evento']=scenario.get('dependencias_evento',[])+route.get('dependencias_evento',[])
            try:
                checked=verificar(scenario)
            except (TypeError, KeyError, ValueError, IndexError, ZeroDivisionError) as exc:
                errors.append(f'Ruta de {ident}: estructura inválida ({type(exc).__name__})');continue
            errors.extend('Ruta de '+ident+': '+e for e in checked['errores'])
            daily=defaultdict(float);weekly=defaultdict(float)
            for s in sessions:
                daily[s['fecha']]+=s['minutos']
                weekly[date.fromisoformat(s['fecha']).isocalendar()[:2]]+=s['minutos']
            for day,minutes in daily.items():max_days[day]=max(max_days[day],minutes)
            for week,minutes in weekly.items():max_weeks[week]=max(max_weeks[week],minutes)
            max_minutes=max(max_minutes,sum(daily.values()))
        for day,minutes in max_days.items():worst_days[day]+=minutes
        for week,minutes in max_weeks.items():worst_weeks[week]+=minutes
        result['minutos_por_tarea'][ident]=max_minutes
        result['minutos_condicionales_maximos']+=max_minutes
    for day,minutes in worst_days.items():
        if minutes>plan['capacidad'].get(day,0):errors.append('Carga conjunta de contingencias excede '+day)
    limit=plan.get('limite_semanal')
    if limit is not None and any(minutes>limit for minutes in worst_weeks.values()):
        errors.append('Carga semanal conjunta de contingencias excedida')
    result['minutos_totales']=result['minutos_base']+result['minutos_condicionales_maximos']
    result['cargas_maximas_por_dia']=dict(sorted(worst_days.items()))
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
        edges.append({"desde": previous, "hacia": following, "tipo": "requisito (si aplica)" if previous in conditional_ids else "requisito"})
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
