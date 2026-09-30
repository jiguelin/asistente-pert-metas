import json
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
import unittest

from calendar_compiler import compile_calendar, semantic_calendar_view
from contingencies import capacity_schedule
from pert_core import PlanError, audit_plan


def health_plan():
    return {'inicio': '2026-10-01', 'fin': '2027-03-31',
            'notas': [{'id': ident, 'tipo': 'T', 'inicio': '2026-10-01', 'fin': '2027-03-31'}
                      for ident in ('T1', 'T2')],
            'sesiones': [],
            'recurrencias': [{'id': ident, 'inicio': '2026-10-01', 'fin': '2027-03-31',
                             'dias': list(range(7)), 'minutos': minutes}
                            for ident, minutes in [('T1', 45), ('T2', 30)]],
            'dependencias': [], 'dependencias_sesion': [], 'dependencias_evento': [],
            'conexiones': [], 'contingencias': []}


class CalendarCompilerTests(unittest.TestCase):
    def test_182_days_two_daily_tasks_expand_to_364_executions(self):
        plan = health_plan()
        original_rules = deepcopy(plan['recurrencias'])
        self.assertIs(compile_calendar(plan), plan)
        self.assertEqual(len(plan['sesiones']), 364)
        self.assertEqual(sum(s['minutos'] for s in plan['sesiones']), 182 * 75)
        self.assertEqual(plan['sesiones'][0], {'id': 'T1', 'fecha': '2026-10-01', 'minutos': 45})
        self.assertEqual(plan['sesiones'][-1], {'id': 'T2', 'fecha': '2027-03-31', 'minutos': 30})
        self.assertEqual(plan['recurrencias'], original_rules)
        self.assertEqual(len(plan['notas']), 2)

    def test_excluded_override_and_extra_dates_have_exact_effects(self):
        plan = health_plan()
        plan['recurrencias'] = [dict(id='T1', inicio='2026-10-01', fin='2026-10-07',
                                    dias=[0, 1, 2, 3, 4], minutos=45,
                                    excluir=['2026-10-02'], excepciones={'2026-10-05': 20, '2026-10-06': 0})]
        plan['sesiones'] = [{'id': 'T1', 'fecha': '2026-10-10', 'minutos': 15}]
        compile_calendar(plan)
        self.assertEqual([(s['fecha'], s['minutos']) for s in plan['sesiones']],
                         [('2026-10-01', 45), ('2026-10-05', 20), ('2026-10-07', 45), ('2026-10-10', 15)])
        view = semantic_calendar_view(plan, {})
        self.assertEqual(view['sesiones'], [{'id': 'T1', 'fecha': '2026-10-10', 'minutos': 15}])
        self.assertEqual(view['resumen_sesiones_calculado'][0]['minutos_totales'], 125)
        self.assertEqual(view['resumen_sesiones_calculado'][0]['cantidad_sesiones'], 4)

    def test_semantic_view_is_lossless_nonmutating_and_keeps_routes_and_edges(self):
        plan = compile_calendar(health_plan())
        facts = {'inicio': plan['inicio'], 'fin': plan['fin'], 'minutos_semana': '[90,90,90,90,90,90,90]',
                 'excepciones_tiempo': '{"2026-12-25":75}'}
        plan['capacidad'] = capacity_schedule(facts)
        plan['dependencias_evento'] = [['T1', '2026-10-01', 'T2', '2026-10-01']]
        plan['contingencias'] = [{'id': 'T3', 'rutas': [{'sesiones': [{'id': 'T3', 'fecha': '2027-01-05', 'minutos': 40}]}]}]
        original = deepcopy(plan)
        view = semantic_calendar_view(plan, facts)
        self.assertEqual(plan, original)
        self.assertEqual(view['sesiones'], [])
        self.assertEqual(view['dependencias_evento'], plan['dependencias_evento'])
        self.assertEqual(view['contingencias'], plan['contingencias'])
        self.assertEqual(view['capacidad']['minutos_semana'], [90] * 7)
        self.assertEqual(view['capacidad']['excepciones_tiempo'], {'2026-12-25': 75})
        self.assertEqual(sum(x['cantidad_sesiones'] for x in view['resumen_sesiones_calculado']), 364)
        self.assertEqual(sum(x['minutos_totales'] for x in view['resumen_sesiones_calculado']), 13650)

    def test_capacity_is_preserved_if_facts_do_not_reconstruct_it(self):
        plan = compile_calendar(health_plan())
        plan['capacidad'] = {'2026-10-01': 75}
        for facts in ({}, {'minutos_semana': '[90,90,90,90,90,90,90]'},
                      {'inicio': plan['inicio'], 'fin': plan['fin'], 'minutos_semana': '[90,90,90,90,90,90,90]'}):
            self.assertEqual(semantic_calendar_view(plan, facts)['capacidad'], plan['capacidad'])

    def test_legacy_plans_stay_byte_equivalent_including_duplicate_sessions(self):
        plan = health_plan()
        del plan['recurrencias']
        plan['sesiones'] = [{'id': 'T1', 'fecha': '2026-10-01', 'minutos': 45}] * 2
        original = json.dumps(plan, sort_keys=True)
        compile_calendar(plan)
        self.assertEqual(json.dumps(plan, sort_keys=True), original)
        self.assertEqual(semantic_calendar_view(plan, {}), plan)

    def test_four_previously_valid_complex_plans_keep_their_audits(self):
        fixture_dir = Path(__file__).parent / 'fixtures'
        restored = Path(__file__).resolve().parents[2] / 'qa_results' / 'final_restore'
        found = []
        for case in ('salud', 'finanzas', 'empresa', 'aprendizaje'):
            path = restored / (case + '.json')
            if path.exists():
                found.append(json.loads(path.read_text())['final']['plan'])
        if not found:
            found = [json.loads((fixture_dir / 'empresa_reposicion.json').read_text())['plan']]
        for plan in found:
            with self.subTest(notes=len(plan['notas'])):
                before = audit_plan(deepcopy(plan))
                original = deepcopy(plan)
                compile_calendar(plan)
                self.assertEqual(plan, original)
                self.assertEqual(audit_plan(plan), before)
                # Exercise the new path too: encode one actual repeated task
                # exactly, including any missing weekdays as exclusions.
                by_id = {}
                for session in original['sesiones']:
                    by_id.setdefault(session['id'], []).append(session)
                ident, items = next((ident, items) for ident, items in by_id.items()
                                    if len(items) > 1 and len({s['minutos'] for s in items}) == 1)
                dates = sorted(s['fecha'] for s in items)
                weekdays = sorted({date.fromisoformat(d).weekday() for d in dates})
                cursor, end = date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])
                missing = []
                while cursor <= end:
                    if cursor.weekday() in weekdays and cursor.isoformat() not in dates:
                        missing.append(cursor.isoformat())
                    cursor += timedelta(days=1)
                plan['sesiones'] = [s for s in original['sesiones'] if s['id'] != ident]
                plan['recurrencias'] = [{'id': ident, 'inicio': dates[0], 'fin': dates[-1],
                                        'dias': weekdays, 'minutos': items[0]['minutos'], 'excluir': missing}]
                compile_calendar(plan)
                sort_key = lambda s: (s['id'], s['fecha'], s['minutos'])
                self.assertEqual(sorted(plan['sesiones'], key=sort_key), sorted(original['sesiones'], key=sort_key))
                after = audit_plan(plan)
                self.assertEqual(after['motor'], before['motor'])
                self.assertEqual(after['notas'], before['notas'])
                self.assertEqual(after['flechas'], before['flechas'])

    def test_collisions_rejected_atomically(self):
        for change in ('explicit_generated', 'rules', 'explicit_explicit'):
            plan = health_plan()
            if change == 'explicit_generated':
                plan['sesiones'] = [{'id': 'T1', 'fecha': '2026-10-01', 'minutos': 20}]
            elif change == 'rules':
                plan['recurrencias'].append(deepcopy(plan['recurrencias'][0]))
            else:
                plan['sesiones'] = [{'id': 'T1', 'fecha': '2026-10-01', 'minutos': 20}] * 2
            original = deepcopy(plan)
            with self.subTest(change=change), self.assertRaises(PlanError):
                compile_calendar(plan)
            self.assertEqual(plan, original)

    def test_invalid_rule_values_do_not_get_silently_repaired(self):
        changes = [({'dias': [True]}, 'boolean weekday'), ({'dias': [7]}, 'unknown weekday'),
                   ({'dias': [1, 1]}, 'duplicate weekday'), ({'dias': []}, 'empty weekday'),
                   ({'minutos': True}, 'boolean minutes'), ({'minutos': 0}, 'zero minutes'),
                   ({'minutos': -1}, 'negative minutes'), ({'minutos': float('inf')}, 'infinite minutes'),
                   ({'minutos': float('nan')}, 'NaN minutes'), ({'minutos': [45] * 7}, 'unsupported array'),
                   ({'inicio': '2026-09-30'}, 'before task'), ({'fin': '2027-04-01'}, 'after task'),
                   ({'inicio': '20261001'}, 'noncanonical date'), ({'id': 'M1'}, 'unknown task'),
                   ({'excluir': ['2026-10-01', '2026-10-01']}, 'duplicate exclusion'),
                   ({'excepciones': {'2027-04-01': 30}}, 'outside exception'),
                   ({'excepciones': {'2026-10-01': True}}, 'boolean exception'),
                   ({'excluir': ['2026-10-01'], 'excepciones': {'2026-10-01': 20}}, 'conflicting exception'),
                   ({'otro': 'ignorado'}, 'unknown field')]
        for update, reason in changes:
            plan = health_plan()
            plan['recurrencias'][0].update(update)
            with self.subTest(reason=reason), self.assertRaises(PlanError):
                compile_calendar(plan)

    def test_exceptions_must_be_real_scheduled_dates(self):
        for field in ('excluir', 'excepciones'):
            plan = health_plan()
            plan['recurrencias'][0]['dias'] = [0]
            plan['recurrencias'][0][field] = ['2026-10-01'] if field == 'excluir' else {'2026-10-01': 20}
            with self.subTest(field=field), self.assertRaises(PlanError):
                compile_calendar(plan)

    def test_conditionals_and_more_than_ten_years_are_rejected(self):
        plan = health_plan()
        plan['notas'][0]['condicional'] = True
        with self.assertRaises(PlanError):
            compile_calendar(plan)
        plan = health_plan()
        plan['fin'] = '2036-10-02'
        with self.assertRaises(PlanError):
            compile_calendar(plan)

    def test_semantic_view_cannot_hide_a_missing_or_changed_execution(self):
        for change in ('missing', 'minutes'):
            plan = compile_calendar(health_plan())
            if change == 'missing':
                plan['sesiones'].pop()
            else:
                plan['sesiones'][0]['minutos'] = 44
            with self.subTest(change=change), self.assertRaises(PlanError):
                semantic_calendar_view(plan, {})


if __name__ == '__main__':
    unittest.main()
