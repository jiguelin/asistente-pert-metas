"""Expand exact weekly rules before the existing PERT audit.

The persisted plan always keeps every real execution. Only the semantic review
receives a lossless compact representation of those executions.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, timedelta
import json
import math
import re

from contingencies import capacity_schedule
from pert_core import PlanError


def _fail(message):
    raise PlanError([message])


def _date(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        _fail(f"Fecha ISO inválida en {label}")
    try:
        return date.fromisoformat(value)
    except ValueError:
        _fail(f"Fecha inválida en {label}")


def _minutes(value, label, allow_zero=False):
    try:
        finite = math.isfinite(value)
    except (TypeError, OverflowError):
        finite = False
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not finite or value < 0 or (not allow_zero and value == 0)):
        _fail(f"Minutos inválidos en {label}")
    return value


def _context(plan):
    start, finish = _date(plan.get('inicio'), 'inicio'), _date(plan.get('fin'), 'fin')
    if start > finish:
        _fail('El fin del calendario es anterior al inicio')
    try:
        ten_years = start.replace(year=start.year + 10)
    except ValueError:
        if start.year > 9989:
            ten_years = date.max
        else:
            ten_years = start.replace(year=start.year + 10, day=28)
    if finish > ten_years:
        _fail('El calendario recurrente no puede superar diez años')
    notes = plan.get('notas')
    if not isinstance(notes, list):
        _fail('Falta el inventario de notas para el calendario')
    by_id = {}
    for note in notes:
        if not isinstance(note, dict) or not isinstance(note.get('id'), str) or not note['id']:
            _fail('Cada nota del calendario necesita un ID válido')
        if note['id'] in by_id:
            _fail('ID de nota duplicado: ' + note['id'])
        by_id[note['id']] = note
    return start, finish, by_id


def _task_span(ident, by_id, start, finish, allow_conditional=False):
    task = by_id.get(ident) if isinstance(ident, str) else None
    if not task or task.get('tipo') != 'T':
        _fail('La sesión requiere una tarea T existente: ' + str(ident))
    if task.get('condicional') and not allow_conditional:
        _fail('Una tarea condicional no puede tener recurrencia: ' + ident)
    a, b = _date(task.get('inicio'), ident), _date(task.get('fin'), ident)
    if not start <= a <= b <= finish:
        _fail('Rango de tarea fuera del plan: ' + ident)
    return a, b


def _expanded_rules(plan):
    """Validate all rules before returning any generated sessions."""
    start, finish, by_id = _context(plan)
    rules = plan.get('recurrencias')
    if not isinstance(rules, list):
        _fail('recurrencias debe ser una lista')
    generated = []
    seen = set()
    required = {'id', 'inicio', 'fin', 'dias', 'minutos'}
    allowed = required | {'excluir', 'excepciones'}
    for rule in rules:
        if not isinstance(rule, dict) or not required <= rule.keys() or rule.keys() - allowed:
            _fail('Regla de recurrencia incompleta o con campos desconocidos')
        ident = rule['id']
        task_start, task_finish = _task_span(ident, by_id, start, finish)
        a, b = _date(rule['inicio'], ident), _date(rule['fin'], ident)
        if not task_start <= a <= b <= task_finish:
            _fail('Recurrencia fuera del rango de su tarea: ' + ident)
        days = rule['dias']
        if (not isinstance(days, list) or not days
                or any(isinstance(x, bool) or not isinstance(x, int) or x not in range(7) for x in days)
                or len(set(days)) != len(days)):
            _fail('Días semanales inválidos en ' + ident)
        minutes = _minutes(rule['minutos'], ident)
        exclusions, overrides = rule.get('excluir', []), rule.get('excepciones', {})
        if not isinstance(exclusions, list) or not isinstance(overrides, dict):
            _fail('Exclusiones o excepciones inválidas en ' + ident)
        excluded = set()
        for value in exclusions:
            day = _date(value, 'exclusión de ' + ident)
            if not a <= day <= b or day.weekday() not in days or value in excluded:
                _fail('Exclusión inexistente o duplicada en ' + ident)
            excluded.add(value)
        for value, replacement in overrides.items():
            day = _date(value, 'excepción de ' + ident)
            if not a <= day <= b or day.weekday() not in days or value in excluded:
                _fail('Excepción fuera del patrón o también excluida en ' + ident)
            _minutes(replacement, 'excepción de ' + ident, allow_zero=True)
        cursor = a
        rule_count = 0
        while cursor <= b:
            key = cursor.isoformat()
            if cursor.weekday() in days and key not in excluded:
                value = overrides.get(key, minutes)
                if value:
                    occurrence = (ident, key)
                    if occurrence in seen:
                        _fail('Ejecución recurrente duplicada: ' + ident + '/' + key)
                    seen.add(occurrence)
                    generated.append({'id': ident, 'fecha': key, 'minutos': value})
                    rule_count += 1
            if cursor == b:
                break
            cursor += timedelta(days=1)
        if not rule_count:
            _fail('La recurrencia no produce ninguna sesión: ' + ident)
    return generated, (start, finish, by_id)


def _validated_sessions(sessions, context):
    if not isinstance(sessions, list):
        _fail('sesiones debe ser una lista')
    start, finish, by_id = context
    seen = set()
    for session in sessions:
        if not isinstance(session, dict):
            _fail('Sesión programada inválida')
        ident = session.get('id')
        a, b = _task_span(ident, by_id, start, finish, allow_conditional=True)
        day = _date(session.get('fecha'), str(ident))
        if not a <= day <= b:
            _fail('Sesión fuera del rango de su tarea: ' + str(ident))
        _minutes(session.get('minutos'), str(ident))
        occurrence = (ident, session['fecha'])
        if occurrence in seen:
            _fail('Ejecución duplicada: ' + ident + '/' + session['fecha'])
        seen.add(occurrence)
    return sessions


def compile_calendar(plan):
    """Mutate a new model draft, expanding rules without dropping any work.

    Legacy expanded plans with no rules remain exactly unchanged. With rules,
    an explicit and a generated occurrence may not share the same ID/date.
    Call once before contingency compilation and the deterministic audit.
    """
    if not isinstance(plan, dict):
        _fail('El calendario no es un objeto JSON')
    if 'recurrencias' not in plan:
        return plan
    generated, context = _expanded_rules(plan)
    explicit = _validated_sessions(plan.get('sesiones'), context)
    combined = explicit + generated
    _validated_sessions(combined, context)
    # Only mutate after all inputs and cross-source collisions have passed.
    plan['sesiones'] = sorted(combined, key=lambda item: (item['fecha'], item['id']))
    return plan


def semantic_calendar_view(plan, facts):
    """Copy the audited plan, replacing expanded rules by their exact meaning.

    Conditional routes and every dependency remain verbatim. Capacity is only
    shortened when the confirmed facts reconstruct the complete mapping.
    """
    view = deepcopy(plan)
    if 'recurrencias' not in plan:
        return view
    generated, context = _expanded_rules(plan)
    sessions = _validated_sessions(plan.get('sesiones'), context)
    actual = {(s['id'], s['fecha']): s for s in sessions}
    generated_keys = set()
    for session in generated:
        key = (session['id'], session['fecha'])
        if key not in actual or actual[key]['minutos'] != session['minutos']:
            _fail('El calendario expandido no coincide con su recurrencia: ' + '/'.join(key))
        generated_keys.add(key)
    view['sesiones'] = [deepcopy(s) for s in sessions if (s['id'], s['fecha']) not in generated_keys]
    groups = defaultdict(list)
    for session in sessions:
        groups[session['id']].append(session)
    summaries = []
    for ident, items in sorted(groups.items()):
        dates = sorted(s['fecha'] for s in items)
        weekdays = Counter(date.fromisoformat(s['fecha']).weekday() for s in items)
        summaries.append({'id': ident, 'cantidad_sesiones': len(items),
                          'minutos_totales': math.fsum(s['minutos'] for s in items),
                          'primera_fecha': dates[0], 'ultima_fecha': dates[-1],
                          'sesiones_por_dia_semana': [weekdays[i] for i in range(7)]})
    view['resumen_sesiones_calculado'] = summaries
    if isinstance(facts, dict) and 'minutos_semana' in facts:
        try:
            confirmed = capacity_schedule(facts)
            if confirmed is not None and confirmed == plan.get('capacidad'):
                capacity = {'inicio': facts['inicio'], 'fin': facts['fin'],
                            'minutos_semana': json.loads(facts['minutos_semana']),
                            'excepciones_tiempo': json.loads(facts.get('excepciones_tiempo', '{}'))}
                if facts.get('cobro_fin_mes') == 'true':
                    capacity['cobro_fin_mes'] = True
                    capacity['minutos_cobro'] = float(facts.get('minutos_cobro', '0'))
                view['capacidad'] = capacity
        except (ValueError, KeyError, TypeError):
            # Never hide a mapping that the confirmed facts cannot reconstruct.
            pass
    return view
