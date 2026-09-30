"""Compile a compact task proposal before showing it to the student.

The model supplies activities and their meaning. Python owns every calendar,
budget total and dependency shown in the proposal; semantic review still owns
the suitability of the tasks for the accepted milestones.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import date, timedelta
import math
import re

from calendar_compiler import compile_calendar
from contingencies import capacity_schedule
from pert_core import PlanError


_TASK_FIELDS = {
    "id", "titulo", "detalle", "inicio", "fin", "dias", "minutos",
    "fechas", "excluir", "excepciones", "habilita", "requisitos",
    "orden_sesion", "pasos",
}

SCHEMA = {
    "type": "object",
    "properties": {
        "tareas": {
            "type": "array", "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "pattern": r"^T[1-9][0-9]*$"},
                    "titulo": {"type": "string"},
                    "detalle": {"type": "string"},
                    "inicio": {"type": "string"},
                    "fin": {"type": "string"},
                    "dias": {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 6}},
                    "minutos": {"type": "number", "exclusiveMinimum": 0},
                    "fechas": {"type": "array", "items": {"type": "string"}},
                    "excluir": {"type": "array", "items": {"type": "string"}},
                    "excepciones": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "fecha": {"type": "string"}, "minutos": {"type": "number", "minimum": 0},
                                "pasos": {"type": "array", "items": {
                                    "type": "object", "properties": {
                                        "accion": {"type": "string"}, "minutos": {"type": "number", "exclusiveMinimum": 0}},
                                    "required": ["accion", "minutos"], "additionalProperties": False}},
                            },
                            "required": ["fecha", "minutos", "pasos"], "additionalProperties": False,
                        },
                    },
                    "habilita": {"type": "array", "items": {"type": "string", "pattern": r"^M(?:[1-9][0-9]*|P)$"}},
                    "requisitos": {"type": "array", "description": "IDs de otras tareas T que deben terminar antes del comienzo. [] si no hay.", "items": {"type": "string", "pattern": r"^T[1-9][0-9]*$"}},
                    "orden_sesion": {"type": "array", "description": "IDs de OTRAS tareas T previas en cada fecha, NO acciones/pasos ni el ID propio. [] si no hay.", "items": {"type": "string", "pattern": r"^T[1-9][0-9]*$"}},
                    "pasos": {
                        "type": "array", "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {"accion": {"type": "string"}, "minutos": {"type": "number", "exclusiveMinimum": 0}},
                            "required": ["accion", "minutos"], "additionalProperties": False,
                        },
                    },
                },
                "required": sorted(_TASK_FIELDS), "additionalProperties": False,
            },
        },
    },
    "required": ["tareas"], "additionalProperties": False,
}

_WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def _fail(message):
    raise PlanError([message])


def _date(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        _fail("Fecha ISO inválida en " + label)
    try:
        return date.fromisoformat(value)
    except ValueError:
        _fail("Fecha inválida en " + label)


def _minutes(value, label, allow_zero=False):
    try:
        finite = math.isfinite(value)
    except (TypeError, OverflowError):
        finite = False
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not finite or value < 0 or (value == 0 and not allow_zero)):
        _fail("Minutos inválidos en " + label)
    return value


def _list(value, label):
    if not isinstance(value, list):
        _fail(label + " debe ser una lista")
    return value


def _ids(value, label):
    values = _list(value, label)
    if any(not isinstance(x, str) or not x for x in values) or len(set(values)) != len(values):
        _fail("IDs vacíos o duplicados en " + label)
    return values


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        _fail("Falta texto en " + label)
    if "?" in value or "¿" in value:
        _fail("La propuesta de tareas no puede introducir otra pregunta en " + label)
    return value.strip()


def _steps(steps, minutes, ident):
    steps = _list(steps, "pasos de " + ident)
    if not steps and minutes:
        _fail("Faltan pasos dentro del tiempo de " + ident)
    for step in steps:
        if not isinstance(step, dict) or set(step) != {"accion", "minutos"}:
            _fail("Paso incompleto o con campos desconocidos en " + ident)
        step["accion"] = _text(step["accion"], "paso de " + ident)
        _minutes(step["minutos"], "paso de " + ident)
    try:
        step_minutes = math.fsum(step["minutos"] for step in steps)
    except OverflowError:
        _fail("Suma de pasos inválida en " + ident)
    if not math.isclose(step_minutes, minutes, rel_tol=0, abs_tol=1e-6):
        _fail("Los pasos no suman los minutos de la sesión de " + ident)
    return steps


def _capacity(facts):
    try:
        result = capacity_schedule(facts)
    except (TypeError, ValueError, KeyError, OverflowError) as exc:
        _fail("Disponibilidad confirmada inválida: " + str(exc))
    if result is None:
        _fail("Faltan días y minutos de disponibilidad confirmados")
    for day, minutes in result.items():
        _minutes(minutes, "disponibilidad de " + day, allow_zero=True)
    return result


def _has_cycle(edges):
    graph = defaultdict(list)
    for previous, following in edges:
        graph[previous].append(following)
    active, done = set(), set()

    def visit(node):
        if node in active:
            return True
        if node in done:
            return False
        active.add(node)
        if any(visit(following) for following in graph[node]):
            return True
        active.remove(node)
        done.add(node)
        return False

    return any(visit(node) for node in list(graph))


def _number(value):
    return f"{value:g}"


def _duration(minutes):
    if float(minutes).is_integer():
        hours, rest = divmod(int(minutes), 60)
        if hours:
            return f"{hours} h" + (f" {rest} min" if rest else "")
    return _number(minutes) + " min"


def _schedule_text(task):
    parts = []
    if task["dias"]:
        days = ("todos los días" if sorted(task["dias"]) == list(range(7))
                else ", ".join(_WEEKDAYS[x] for x in sorted(task["dias"])))
        parts.append(days)
    if task["fechas"]:
        parts.append("fechas puntuales: " + ", ".join(sorted(task["fechas"])))
    parts.append(_number(task["minutos"]) + " min por sesión estándar")
    if task["excluir"]:
        parts.append("sin sesión: " + ", ".join(sorted(task["excluir"])))
    if task["excepciones"]:
        parts.append("duración excepcional: " + "; ".join(
            item["fecha"] + " = " + _number(item["minutos"]) + " min"
            + (" (" + ", ".join(step["accion"] + " " + _number(step["minutos"]) + " min"
                                for step in item["pasos"]) + ")" if item["pasos"] else " (sin sesión)")
            for item in sorted(task["excepciones"], key=lambda item: item["fecha"])))
    return "; ".join(parts)


def prepare_proposal(data, facts):
    """Validate and return (faithful Spanish reply, expanded calendar snapshot).

    ``facts`` uses the intake's ISO dates and JSON weekly capacity. An optional
    ``mini_ids`` list constrains contributions to the actually accepted goals.
    Exclusions and duration exceptions must reference a real scheduled date;
    point dates may supplement a pattern, but may never duplicate its dates.
    Nothing mutates the input and no invalid draft is partially returned.
    """
    if not isinstance(data, dict) or set(data) != {"tareas"}:
        _fail("La propuesta debe contener únicamente tareas")
    if not isinstance(facts, dict):
        _fail("Faltan los hechos confirmados")
    start, finish = _date(facts.get("inicio"), "inicio"), _date(facts.get("fin"), "fin")
    if start > finish:
        _fail("El fin del plan es anterior al inicio")
    try:
        latest = start.replace(year=start.year + 10)
    except ValueError:
        latest = date.max if start.year > 9989 else start.replace(year=start.year + 10, day=28)
    if finish > latest:
        _fail("El calendario recurrente no puede superar diez años")
    tasks = _list(data["tareas"], "tareas")
    if not tasks:
        _fail("Falta la propuesta de tareas")
    tasks = deepcopy(tasks)
    by_id = {}
    for task in tasks:
        if not isinstance(task, dict) or set(task) != _TASK_FIELDS:
            _fail("Tarea incompleta o con campos desconocidos")
        ident = task["id"]
        if not isinstance(ident, str) or not re.fullmatch(r"T[1-9]\d*", ident):
            _fail("ID de tarea inválido: " + str(ident))
        if ident in by_id:
            _fail("ID de tarea duplicado: " + ident)
        by_id[ident] = task
    known_minis = facts.get("mini_ids")
    if known_minis is not None:
        known_minis = set(_ids(known_minis, "mini_ids"))
    plan = {"inicio": start.isoformat(), "fin": finish.isoformat(), "notas": [],
            "recurrencias": [], "sesiones": [], "dependencias": [],
            "dependencias_sesion": [], "dependencias_evento": [], "conexiones": []}

    for task in tasks:
        ident = task["id"]
        task["titulo"] = _text(task["titulo"], ident)
        task["detalle"] = _text(task["detalle"], "detalle de " + ident)
        a, b = _date(task["inicio"], ident), _date(task["fin"], ident)
        if not start <= a <= b <= finish:
            _fail("Rango de tarea fuera del plan: " + ident)
        minutes = _minutes(task["minutos"], ident)
        steps = _steps(task["pasos"], minutes, ident)
        days = _list(task["dias"], "dias de " + ident)
        if (any(isinstance(day, bool) or not isinstance(day, int) or day not in range(7) for day in days)
                or len(set(days)) != len(days)):
            _fail("Días semanales inválidos en " + ident)
        pattern = set()
        cursor = a
        while cursor <= b:
            if cursor.weekday() in days:
                pattern.add(cursor.isoformat())
            if cursor == b:
                break
            cursor += timedelta(days=1)
        explicit = set()
        for value in _list(task["fechas"], "fechas de " + ident):
            day = _date(value, ident)
            if not a <= day <= b:
                _fail("Fecha puntual fuera del rango de " + ident)
            if value in explicit or value in pattern:
                _fail("Ejecución duplicada en " + ident + "/" + value)
            explicit.add(value)
        nominal = pattern | explicit
        excluded = set()
        for value in _list(task["excluir"], "excluir de " + ident):
            _date(value, "exclusión de " + ident)
            if value not in nominal or value in excluded:
                _fail("Exclusión inexistente o duplicada en " + ident)
            excluded.add(value)
        overrides = {}
        for item in _list(task["excepciones"], "excepciones de " + ident):
            if not isinstance(item, dict) or set(item) != {"fecha", "minutos", "pasos"}:
                _fail("Excepción incompleta o con campos desconocidos en " + ident)
            value = item["fecha"]
            _date(value, "excepción de " + ident)
            if value not in nominal or value in excluded or value in overrides:
                _fail("Excepción fuera del calendario, duplicada o excluida en " + ident)
            overrides[value] = _minutes(item["minutos"], "excepción de " + ident, allow_zero=True)
            _steps(item["pasos"], item["minutos"], "excepción de " + ident + "/" + value)
        for label in ("requisitos", "orden_sesion"):
            for previous in _ids(task[label], label + " de " + ident):
                if previous not in by_id or previous == ident:
                    _fail(label+" de "+ident+": "+previous+" no es ID de otra tarea existente. Las acciones de la misma tarea van en pasos; usa [] si no depende de otra T.")
                edge = [previous, ident]
                plan["dependencias" if label == "requisitos" else "dependencias_sesion"].append(edge)
        milestones = _ids(task["habilita"], "habilita de " + ident)
        if not milestones:
            _fail("La tarea no indica qué meta habilita: " + ident)
        for milestone in milestones:
            if (not re.fullmatch(r"M[1-9]\d*|MP", milestone)
                    or (known_minis is not None and milestone not in known_minis)):
                _fail("Meta habilitada inexistente: " + milestone)
            plan["conexiones"].append([ident, milestone, "contribucion"])
        plan["notas"].append({"id": ident, "tipo": "T", "texto": task["titulo"],
                              "detalle": task["detalle"], "inicio": task["inicio"], "fin": task["fin"],
                              "pasos": deepcopy(steps), "frecuencia": _schedule_text(task)})
        if days:
            plan["recurrencias"].append({"id": ident, "inicio": task["inicio"], "fin": task["fin"],
                                        "dias": sorted(days), "minutos": minutes,
                                        "excluir": sorted(excluded & pattern),
                                        "excepciones": {key: value for key, value in overrides.items() if key in pattern}})
        for day in sorted(explicit - excluded):
            value = overrides.get(day, minutes)
            if value:
                plan["sesiones"].append({"id": ident, "fecha": day, "minutos": value})

    compile_calendar(plan)
    plan["capacidad"] = _capacity(facts)
    dates_by_task, daily, totals, counts = defaultdict(set), defaultdict(list), defaultdict(list), defaultdict(int)
    for session in plan["sesiones"]:
        ident, day = session["id"], session["fecha"]
        dates_by_task[ident].add(day)
        daily[day].append(session["minutos"])
        totals[ident].append(session["minutos"])
        counts[ident] += 1
    for ident in by_id:
        if not counts[ident]:
            _fail("La tarea no produce ninguna sesión: " + ident)
    try:
        loads = {day: math.fsum(values) for day, values in sorted(daily.items())}
        task_totals = {ident: math.fsum(values) for ident, values in totals.items()}
        total = math.fsum(task_totals.values())
    except OverflowError:
        _fail("Suma de minutos inválida")
    for day, load in loads.items():
        if load > plan["capacidad"].get(day, 0):
            _fail(f"Carga diaria {day}: {_number(load)} min; disponible {_number(plan['capacidad'].get(day, 0))}")
    for previous, following in plan["dependencias"]:
        if _date(by_id[previous]["fin"], previous) > _date(by_id[following]["inicio"], following):
            _fail("Precedencia global imposible: " + previous + "→" + following)
    for previous, following in plan["dependencias_sesion"]:
        missing = dates_by_task[following] - dates_by_task[previous]
        if missing:
            _fail("Falta sesión previa " + previous + "→" + following + ": " + ", ".join(sorted(missing)))
    if _has_cycle(plan["dependencias"] + plan["dependencias_sesion"]):
        _fail("Ciclo en dependencias de las tareas")
    plan["resumen_sesiones_calculado"] = [
        {"id": task["id"], "cantidad_sesiones": counts[task["id"]],
         "minutos_totales": task_totals[task["id"]],
         "primera_fecha": min(dates_by_task[task["id"]]), "ultima_fecha": max(dates_by_task[task["id"]])}
        for task in tasks]
    plan["cargas_por_dia"] = loads
    plan["minutos_totales"] = total
    plan["sesiones_totales"] = len(plan["sesiones"])
    plan["maximo_minutos_dia"] = max(loads.values())
    lines = ["Te propongo estas tareas; sus tiempos incluyen preparación, trabajo y registro según el reparto indicado:"]
    for task in tasks:
        ident = task["id"]
        lines.extend(["", f"**{ident} — {task['titulo']}**", task["detalle"],
                      f"{task['inicio']} a {task['fin']}: {_schedule_text(task)}.",
                      "Reparto de la sesión estándar: " + "; ".join(
                          step["accion"] + " (" + _number(step["minutos"]) + " min)" for step in task["pasos"]) + ".",
                      f"{counts[ident]} sesiones; {_number(task_totals[ident])} min ({_duration(task_totals[ident])}) en total.",
                      "Habilita: " + ", ".join(task["habilita"]) + "."])
        if task["requisitos"]:
            lines.append("Requiere terminar antes: " + ", ".join(task["requisitos"]) + ".")
        if task["orden_sesion"]:
            lines.append("En cada fecha de esta tarea, realizar antes: " + ", ".join(task["orden_sesion"]) + ".")
        if not task["requisitos"] and not task["orden_sesion"]:
            lines.append("Sin dependencia previa; puede avanzar en paralelo.")
    lines.extend(["", f"Carga total: {len(plan['sesiones'])} sesiones; {_number(total)} min ({_duration(total)}).",
                  f"Carga máxima en un día: {_number(plan['maximo_minutos_dia'])} min, dentro de tu disponibilidad confirmada.",
                  "", "¿Aceptas esta propuesta de tareas y horarios?"])
    return "\n".join(lines), plan
