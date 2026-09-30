"""Local PERT gate: same deterministic modules as the workshop app, no API."""
from __future__ import annotations

import argparse
from copy import deepcopy
from decimal import Decimal, DecimalException
from datetime import date
import json
import math
from pathlib import Path
import re
import sys
import unicodedata

from intake import QUESTIONS, calculations, cash_schedule, stage
from contingencies import capacity_schedule, compile_replacement
from pert_core import PlanError, audit_with_scale, summary

SEMANTIC_CHECKS = ('meta_fiel', 'hitos_resultados', 'evidencias_aprobadas',
                   'tareas_sin_duplicados', 'insumos_y_flechas', 'costos_y_recursos',
                   'disponibilidad_fiel', 'sin_pendientes_esenciales')


def _number(value, label, *, positive=False, integer=False):
    """The imported motor assumes finite, genuinely numeric inputs."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise PlanError(['Número inválido: ' + label])
    try:
        number = Decimal(str(value))
        valid = number.is_finite() and math.isfinite(float(number))
        valid = valid and (number > 0 if positive else number >= 0)
        if integer:
            valid = valid and number == number.to_integral_value()
    except (DecimalException, ValueError, OverflowError):
        valid = False
    if not valid:
        raise PlanError(['Número finito ' + ('positivo' if positive else 'no negativo') +
                         ' requerido: ' + label])
    return number


def _finite_tree(value, label='entrada'):
    if isinstance(value, float) and not math.isfinite(value):
        raise PlanError(['Número no finito: ' + label])
    if isinstance(value, dict):
        for key, item in value.items():
            _finite_tree(item, label + '.' + str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _finite_tree(item, label + '[' + str(index) + ']')


def _dimensions(value, label):
    if not isinstance(value, list) or len(value) != 2:
        raise PlanError(['Dos medidas confirmadas requeridas: ' + label])
    return [float(_number(x, label, positive=True)) for x in value]


def _require(facts, names, label):
    missing = [name for name in names if name not in facts or not facts[name].strip()]
    if missing:
        raise PlanError(['Faltan datos confirmados de ' + label + ': ' + ', '.join(missing)])


def _confirmed_calendar(values, facts, label):
    if not isinstance(values, dict):
        raise PlanError([label + ' debe ser un objeto por fecha'])
    for day, value in values.items():
        d = date.fromisoformat(day)
        if not date.fromisoformat(facts['inicio']) <= d <= date.fromisoformat(facts['fin']):
            raise PlanError([label + ' fuera del plan: ' + day])
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise PlanError(['Minutos numéricos requeridos: ' + label + '.' + day])
        _number(value, label + '.' + day)
    return deepcopy(values)


def _cash_rows(rows, facts):
    if not isinstance(rows, list) or not rows:
        raise PlanError(['Falta flujo de caja completo y confirmado'])
    previous = None
    for row in rows:
        if not isinstance(row, dict):
            raise PlanError(['Fila de caja inválida'])
        day = date.fromisoformat(row['fecha'])
        if not date.fromisoformat(facts['inicio']) <= day <= date.fromisoformat(facts['fin']) or (previous and day <= previous):
            raise PlanError(['Fechas de caja fuera del plan o sin orden estricto'])
        previous = day
        for name in ['saldo', 'reserva', 'libre']:
            if not isinstance(row.get(name), (int, float)) or isinstance(row.get(name), bool):
                raise PlanError(['Importe numérico requerido: caja.' + name])
            _number(row[name], 'caja.' + name)
    return deepcopy(rows)


def _plan_types(plan):
    """Reject malformed inventories before contingency compilation accesses them."""
    _finite_tree(plan, 'plan')
    for name in ['notas', 'sesiones', 'periodos', 'dependencias', 'conexiones', 'pendientes']:
        if not isinstance(plan.get(name), list):
            raise PlanError(['Lista requerida: ' + name])
    if not isinstance(plan.get('materiales'), dict) or not isinstance(plan.get('capacidad'), dict):
        raise PlanError(['Materiales y capacidad deben ser objetos'])
    for note in plan['notas']:
        if not isinstance(note, dict) or any(not isinstance(note.get(k), str) or not note[k]
                                             for k in ['id', 'tipo', 'inicio', 'fin']):
            raise PlanError(['Nota con estructura inválida'])
        for name in ['condicional', 'principal']:
            if name in note and not isinstance(note[name], bool):
                raise PlanError(['Indicador booleano requerido: ' + name])
    for session in plan['sesiones']:
        if not isinstance(session, dict) or not isinstance(session.get('id'), str) or not isinstance(session.get('fecha'), str):
            raise PlanError(['Sesión con estructura inválida'])
        if not isinstance(session.get('minutos'), (int, float)) or isinstance(session.get('minutos'), bool):
            raise PlanError(['Minutos numéricos requeridos'])
        _number(session['minutos'], 'sesiones.minutos', positive=True)
    for day, minutes in plan['capacidad'].items():
        date.fromisoformat(day)
        if not isinstance(minutes, (int, float)) or isinstance(minutes, bool):
            raise PlanError(['Capacidad numérica requerida: ' + day])
        _number(minutes, 'capacidad.' + day)
    if plan.get('limite_semanal') is not None:
        _number(plan['limite_semanal'], 'limite_semanal')
    if 'finanzas' in plan and not isinstance(plan['finanzas'], bool):
        raise PlanError(['Indicador booleano requerido: finanzas'])
    for row in plan.get('caja', []):
        if not isinstance(row, dict):
            raise PlanError(['Fila de caja inválida'])
        date.fromisoformat(row['fecha'])
        for name in ['saldo', 'reserva', 'libre']:
            if not isinstance(row.get(name), (int, float)) or isinstance(row.get(name), bool):
                raise PlanError(['Importe numérico requerido: caja.' + name])
            _number(row[name], 'caja.' + name)


def snapshot(data):
    if not isinstance(data, dict):
        raise PlanError(['La entrada debe ser un objeto JSON'])
    _finite_tree(data)
    state = data.get('estado', data)
    if not isinstance(state, dict) or not isinstance(state.get('facts', {}), dict):
        raise PlanError(['Estado de entrevista inválido'])
    if any(not isinstance(v, str) for v in state.get('facts', {}).values()):
        raise PlanError(['Los hechos deben usar valores de texto según el esquema de intake'])
    if not isinstance(state.get('meta_verificable', False), bool):
        raise PlanError(['meta_verificable debe ser un booleano'])
    if state.get('ambiguedad_esencial') is not None and not isinstance(state['ambiguedad_esencial'], str):
        raise PlanError(['ambiguedad_esencial debe ser texto o null'])
    return {'facts': state.get('facts', {}),
            'meta_verificable': state.get('meta_verificable', False),
            'ambiguedad_esencial': state.get('ambiguedad_esencial'),
            'capacidad_confirmada': state.get('capacidad_confirmada'),
            'caja_confirmada': state.get('caja_confirmada')}


def next_step(data):
    state = snapshot(data)
    current = stage(state)
    question = QUESTIONS.get(current)
    if current == 'criterio':
        term = state.get('ambiguedad_esencial')
        question = ('Para poder comprobar la meta, ¿qué característica concreta '
                    f'debe cumplirse cuando dices «{term}»?' if term else
                    '¿Qué resultado concreto te permitirá comprobar que lograste tu meta?')
    return {'etapa': current, 'pregunta': question,
            'calculos': calculations(state['facts']) if current not in ['meta', 'criterio', 'inicio', 'fin'] else ''}


def validate(data):
    state = snapshot(data)
    current = stage(state)
    if current != 'final':
        raise PlanError(['Etapa pendiente: ' + current])
    checks = data.get('revision_semantica', {})
    if not isinstance(checks, dict) or any(checks.get(k) is not True for k in SEMANTIC_CHECKS):
        raise PlanError(['Completa la revisión semántica interna antes de certificar el montaje'])
    if not isinstance(data.get('plan'), dict):
        raise PlanError(['Falta el plan completo'])
    plan = deepcopy(data['plan'])
    _plan_types(plan)
    facts = state['facts']
    if 'tipo' in facts and facts['tipo'] not in ['otro', 'ahorro', 'empresa']:
        raise PlanError(['Tipo de meta inválido'])
    if 'tipo' not in facts and (any(k in facts for k in ['saldo', 'capital', 'unidades', 'objetivo']) or plan.get('economia') or plan.get('finanzas')):
        raise PlanError(['Falta confirmar si la meta requiere ahorro o ganancia empresarial'])
    # Do not overwrite a fabricated limit/dimension before checking fidelity.
    if plan.get('inicio') != facts['inicio'] or plan.get('fin') != facts['fin']:
        raise PlanError(['Las fechas principales difieren de las declaradas'])
    for target, source in [('papel', 'papel'), ('nota', 'nota'), ('meta', 'meta_nota')]:
        if _dimensions(plan['materiales'][target], target) != _dimensions(json.loads(facts[source]), source):
            raise PlanError(['Medidas distintas: ' + target])
    if _number(plan['materiales']['pared'], 'materiales.pared', positive=True) != _number(facts['pared'], 'pared', positive=True):
        raise PlanError(['Ancho de pared diferente al confirmado'])
    plan['materiales']['papelografos_disponibles'] = int(_number(facts['papeles'], 'papeles', positive=True, integer=True))
    plan['contexto'] = {'situacion_actual': facts.get('situacion', ''),
                        'obstaculo_principal': facts.get('principal', '')}
    currencies = set(re.findall(r'S/|US\$|\$|€|£|\b(?:PEN|USD|EUR|GBP)\b',
                               '\n'.join(m['content'] for m in data.get('messages', []) if m['role'] == 'user')))
    canonical = {'PEN': 'S/', 'USD': 'US$', 'EUR': '€', 'GBP': '£'}
    currencies = {canonical.get(unit, unit) for unit in currencies}
    if len(currencies) == 1:
        plan['moneda'] = currencies.pop()
    for name in ['saldo', 'capital', 'ingreso', 'gasto', 'reserva', 'objetivo', 'unidades',
                 'precio', 'costo', 'empaque', 'publicidad', 'otros_costos', 'reposicion',
                 'reposicion_caja', 'reposicion_empaque', 'reposicion_envio', 'minutos_cobro']:
        if name in facts:
            _number(facts[name], name, integer=name == 'unidades')
    for name in ['cobro_fin_mes', 'gastos_inicio_pagados', 'inventario_disponible',
                 'primer_envio_cliente', 'entrega_lun_vie', 'recogida_sabados']:
        if name in facts and facts[name] not in ['true', 'false']:
            raise PlanError(['Hecho booleano inválido: ' + name])
    if facts.get('tipo') == 'ahorro':
        _require(facts, ['saldo', 'reserva', 'objetivo'], 'ahorro')
    cash = cash_schedule(facts)
    if facts.get('tipo') == 'ahorro' and cash is None:
        # An irregular, accepted dated flow need not invent month-end paydays.
        cash = _cash_rows(state.get('caja_confirmada'), facts)
        if (cash[0]['fecha'] != facts['inicio'] or cash[-1]['fecha'] != facts['fin'] or
                Decimal(str(cash[0]['saldo'])) != Decimal(facts['saldo']) or
                Decimal(str(cash[-1]['reserva'])) != Decimal(facts['reserva'])):
            raise PlanError(['El flujo de ahorro difiere del saldo inicial, reserva final o fechas confirmadas'])
    if cash is not None:
        plan['finanzas'], plan['caja'] = True, cash
        if facts.get('objetivo') and Decimal(str(cash[-1]['libre'])) < Decimal(facts['objetivo']):
            raise PlanError(['El dinero libre final no alcanza la meta'])
    if 'minutos_semana' in facts:
        weekdays = json.loads(facts['minutos_semana'])
        if not isinstance(weekdays, list) or len(weekdays) != 7:
            raise PlanError(['La disponibilidad requiere siete valores de minutos'])
        for value in weekdays:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise PlanError(['Minutos de disponibilidad numéricos requeridos'])
            _number(value, 'minutos_semana')
        _confirmed_calendar(json.loads(facts.get('excepciones_tiempo', '{}')), facts, 'excepciones_tiempo')
        plan['capacidad'] = capacity_schedule(facts)
    elif state.get('capacidad_confirmada') is not None:
        # Exact dates/minutes may themselves be newly accepted intake facts.
        plan['capacidad'] = _confirmed_calendar(state['capacidad_confirmada'], facts, 'capacidad_confirmada')
    else:
        raise PlanError(['Falta disponibilidad confirmada: minutos_semana o capacidad_confirmada por fecha'])
    clean = lambda text: ''.join(c for c in unicodedata.normalize('NFKD', str(text).lower()) if not unicodedata.combining(c))
    replacements = [n for n in plan['notas'] if n['tipo'] == 'T' and
                    (n.get('workflow') == 'reposicion' or 'reposici' in clean(n.get('texto', '')))]
    if facts.get('tipo') == 'empresa' and replacements:
        _require(facts, ['entrega_habiles', 'reposicion_habiles', 'entrega_lun_vie', 'recogida_sabados'], 'courier y reposición')
        if facts['entrega_lun_vie'] != 'true':
            raise PlanError(['La reposición local requiere el calendario de entrega de lunes a viernes'])
        for name in ['entrega_habiles', 'reposicion_habiles']:
            if _number(facts[name], name, positive=True, integer=True) > 30:
                raise PlanError(['Plazo hábil fuera del rango admitido: ' + name])
        if 'reposicion' not in facts:
            _require(facts, ['reposicion_caja', 'reposicion_empaque', 'reposicion_envio'], 'costo completo de reposición')
        replacement_ids = {n['id'] for n in replacements}
        for group in plan.get('contingencias', []):
            if group.get('id') in replacement_ids and (type(group.get('max_activaciones')) is not int or group['max_activaciones'] != 1):
                raise PlanError(['La reposición automática solo cubre una incidencia; no puede reducir las incidencias declaradas'])
        others = [g for g in plan.get('contingencias', []) if g.get('id') not in replacement_ids]
        compile_replacement(plan, facts)
        plan['contingencias'] = others + plan.get('contingencias', [])
    if facts.get('tipo') == 'empresa':
        _require(facts, ['unidades', 'precio', 'costo', 'empaque', 'publicidad', 'capital',
                         'inventario_disponible', 'otros_costos', 'primer_envio_cliente', 'objetivo'], 'economía empresarial')
        plan.pop('economia', None)
    if (facts.get('tipo') == 'empresa'
            and all(k in facts for k in ['unidades', 'precio', 'costo', 'empaque', 'publicidad', 'capital'])
            and facts.get('inventario_disponible') == 'true'
            and facts.get('otros_costos') == '0' and facts.get('primer_envio_cliente') == 'true'):
        units = Decimal(facts['unidades'])
        income = units * Decimal(facts['precio'])
        stock = units * Decimal(facts['costo'])
        packs = units * Decimal(facts['empaque'])
        ads = Decimal(facts['publicidad'])
        replacement = Decimal(facts.get('reposicion', '0')) or sum(
            (Decimal(facts.get(k, '0')) for k in ['reposicion_caja', 'reposicion_empaque', 'reposicion_envio']), Decimal(0))
        maximum = packs + ads + replacement
        plan['economia'] = {k: float(v) for k, v in {
            'ingreso_previsto': income, 'costo_inventario': stock, 'empaques_normales': packs,
            'publicidad': ads, 'costo_una_reposicion': replacement,
            'utilidad_sin_reposicion': income-stock-packs-ads,
            'utilidad_con_una_reposicion': income-stock-packs-ads-replacement,
            'capital_disponible': Decimal(facts['capital']), 'costos_pendientes_maximos': maximum}.items()}
        if Decimal(facts['capital']) >= maximum:
            plan['finanzas'], plan['caja'] = False, []
        else:
            plan['finanzas'] = True
            if not plan.get('caja'):
                raise PlanError(['El capital inicial no cubre los costos pendientes; falta un flujo de caja fechado y aprobado'])
            first = plan['caja'][0]
            if first['fecha'] != plan['inicio'] or Decimal(str(first['saldo'])) != Decimal(facts['capital']):
                raise PlanError(['El flujo empresarial debe comenzar con el capital inicial confirmado'])
        if facts.get('objetivo') and income-stock-packs-ads-replacement < Decimal(facts['objetivo']):
            raise PlanError(['La ganancia con la contingencia prevista no alcanza la meta'])
    elif facts.get('tipo') == 'empresa':
        plan['finanzas'] = True
        if not plan.get('caja'):
            raise PlanError(['Las condiciones empresariales requieren un flujo de caja completo y aprobado'])
    if plan.get('finanzas') and plan.get('caja'):
        plan['caja'] = _cash_rows(plan['caja'], facts)
    principal = facts.get('principal', '').strip().lower()
    if principal and principal not in ['ninguno', 'ningún obstáculo', 'no tengo obstáculos']:
        if sum(n.get('tipo') == 'O' and n.get('principal') is True for n in plan['notas']) != 1:
            raise PlanError(['Marca exactamente un obstáculo principal declarado'])
    audit = audit_with_scale(plan)
    if audit['motor']['papelografos'] > int(facts['papeles']):
        raise PlanError(['Se necesitan más papelógrafos que los disponibles'])
    _finite_tree(audit, 'audit')
    return audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('accion', choices=['paso', 'validar', 'exportar'])
    parser.add_argument('entrada', type=Path)
    parser.add_argument('--pdf', type=Path)
    parser.add_argument('--json', dest='json_path', type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.entrada.read_text(encoding='utf-8'))
        if args.accion == 'paso':
            result = {'ok': True, **next_step(data)}
        else:
            audit = validate(data)
            result = {'ok': True, 'resumen': summary(audit), 'audit': audit}
            if args.accion == 'exportar':
                if args.pdf is None:
                    raise PlanError(['Falta destino PDF'])
                from pdf_export import export_pdf
                pdf = export_pdf(audit)
                args.pdf.parent.mkdir(parents=True, exist_ok=True)
                args.pdf.write_bytes(pdf)
                result['pdf_path'] = str(args.pdf.resolve())
                if args.json_path:
                    args.json_path.parent.mkdir(parents=True, exist_ok=True)
                    args.json_path.write_text(json.dumps({**data, 'plan': audit['plan'], 'audit': audit}, ensure_ascii=False, indent=2), encoding='utf-8')
                    result['json_path'] = str(args.json_path.resolve())
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, DecimalException, OverflowError) as exc:
        errors = exc.problems if isinstance(exc, PlanError) else [str(exc)]
        print(json.dumps({'ok': False, 'errores': errors}, ensure_ascii=False))
        return 2
    except (ImportError, OSError) as exc:
        print(json.dumps({'ok': False, 'bloqueo_tecnico': type(exc).__name__}, ensure_ascii=False))
        return 3


if __name__ == '__main__':
    sys.exit(main())
