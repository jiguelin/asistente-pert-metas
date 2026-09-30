"""Interrupted final verification resumes completed work without API access."""
import copy
import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pert_assistant as assistant
from pert_core import PlanError
from test_product import sample_plan


def response(plan):
    return SimpleNamespace(output_text=json.dumps(plan, ensure_ascii=False), usage=None)


def ready_snapshot():
    return {
        'facts': {
            'meta': 'Caminar 5 km', 'inicio': '2026-10-01', 'fin': '2026-10-31',
            'situacion': 'Camino 2 km', 'obstaculos': 'Lluvia', 'principal': 'Lluvia',
            'habilidades': 'Medir distancias', 'apoyos': 'Entrenador',
            'disponibilidad': '45 minutos por bloque',
            'mini_aprobadas': 'true', 'tareas_aprobadas': 'true',
            'papel': '[90,60]', 'nota': '[3.8,3.8]', 'meta_nota': '[15,15]',
            'papeles': '3', 'pared': '300',
        },
        'meta_verificable': True, 'ambiguedad_esencial': None,
    }


MESSAGES = [{'role': 'user', 'content': 'Acepto el cronograma completo.'}]


class FinalCheckpointTests(unittest.TestCase):
    def test_review_timeout_keeps_completed_draft_and_retry_reuses_it(self):
        state = {}
        token = assistant.FINAL_WORK.set(state)
        draft = response(sample_plan())
        try:
            with patch.object(assistant, '_create', return_value=draft) as create, \
                    patch.object(assistant, 'review', side_effect=[
                        assistant.AssistantError('Se agotó el tiempo de revisión'),
                        {'ok': True, 'problems': []},
                    ]) as review:
                with self.assertRaises(assistant.AssistantError):
                    assistant.build_final(None, 'test', MESSAGES, '2026-09-30',
                                          ready_snapshot=ready_snapshot())
                self.assertEqual(state['draft'], draft.output_text)
                self.assertIn('fingerprint', state)
                self.assertEqual(create.call_count, 1)
                audit, missing, _ = assistant.build_final(
                    None, 'test', MESSAGES, '2026-09-30', ready_snapshot=ready_snapshot())
                self.assertIsNotNone(audit)
                self.assertEqual(missing, [])
                self.assertEqual(create.call_count, 1)
                self.assertEqual(review.call_count, 2)
                self.assertEqual(state, {})
        finally:
            assistant.FINAL_WORK.reset(token)

    def test_invalid_draft_repair_survives_deadline_and_is_used_on_retry(self):
        invalid = sample_plan()
        invalid['capacidad']['2026-10-01'] = 10
        invalid_response = response(invalid)
        audit_plan = assistant.audit_with_scale
        problems = []
        state = {}
        token = assistant.FINAL_WORK.set(state)

        def expire_after_invalid_audit(plan):
            try:
                return audit_plan(plan)
            except PlanError as exc:
                problems.extend(exc.problems)
                assistant.TURN_DEADLINE.set(time.monotonic())
                raise

        try:
            with patch.object(assistant, '_create', return_value=invalid_response) as first_create, \
                    patch.object(assistant, 'audit_with_scale', side_effect=expire_after_invalid_audit), \
                    patch.object(assistant, 'review') as first_review:
                with self.assertRaises(assistant.AssistantError):
                    assistant.build_final(None, 'test', MESSAGES, '2026-09-30',
                                          ready_snapshot=ready_snapshot())
            self.assertEqual(first_create.call_count, 1)
            first_review.assert_not_called()
            self.assertTrue(problems)
            self.assertNotIn('draft', state)
            self.assertIn(invalid_response.output_text, state['repair'])
            for problem in problems:
                self.assertIn(problem, state['repair'])
            with patch.object(assistant, '_create', return_value=response(sample_plan())) as retry_create, \
                    patch.object(assistant, 'review', return_value={'ok': True, 'problems': []}):
                audit, missing, _ = assistant.build_final(
                    None, 'test', MESSAGES, '2026-09-30', ready_snapshot=ready_snapshot())
            self.assertIsNotNone(audit)
            self.assertEqual(missing, [])
            self.assertEqual(retry_create.call_count, 1)
            instructions = retry_create.call_args.kwargs['instructions']
            self.assertIn(invalid_response.output_text, instructions)
            for problem in problems:
                self.assertIn(problem, instructions)
            self.assertEqual(state, {})
        finally:
            assistant.FINAL_WORK.reset(token)

    def test_model_history_or_fact_changes_discard_stale_checkpoint(self):
        for changed in ['model', 'messages', 'facts']:
            with self.subTest(changed=changed):
                state = {}
                token = assistant.FINAL_WORK.set(state)
                facts = ready_snapshot()
                messages = copy.deepcopy(MESSAGES)
                model = 'test'
                try:
                    with patch.object(assistant, '_create', return_value=response(sample_plan())), \
                            patch.object(assistant, 'review', side_effect=assistant.AssistantError('interrupted')):
                        with self.assertRaises(assistant.AssistantError):
                            assistant.build_final(None, model, messages, '2026-09-30',
                                                  ready_snapshot=facts)
                    old_fingerprint = state['fingerprint']
                    state['repair'] = 'STALE REPAIR FROM PREVIOUS CONVERSATION'
                    if changed == 'model':
                        model = 'another-model'
                    elif changed == 'messages':
                        messages.append({'role': 'user', 'content': 'También acepto el apoyo del entrenador.'})
                    else:
                        facts['facts']['situacion'] = 'Ahora camino 3 km'
                    generated_plan = sample_plan()
                    generated_plan['notas'][0]['detalle'] = 'Nueva propuesta para esta conversación'

                    def regenerate(_client, **kwargs):
                        self.assertNotEqual(state['fingerprint'], old_fingerprint)
                        self.assertNotIn('draft', state)
                        self.assertNotIn('repair', state)
                        self.assertNotIn('STALE REPAIR', kwargs['instructions'])
                        return response(generated_plan)

                    with patch.object(assistant, '_create', side_effect=regenerate) as create, \
                            patch.object(assistant, 'review', return_value={'ok': True, 'problems': []}):
                        audit, missing, _ = assistant.build_final(
                            None, model, messages, '2026-09-30', ready_snapshot=facts)
                    self.assertEqual(create.call_count, 1)
                    self.assertEqual(missing, [])
                    self.assertEqual(audit['plan']['notas'][0]['detalle'], generated_plan['notas'][0]['detalle'])
                    self.assertEqual(state, {})
                finally:
                    assistant.FINAL_WORK.reset(token)

    def test_final_deadline_is_120_seconds_and_restores_outer_context(self):
        outer = time.monotonic() + 300
        token = assistant.TURN_DEADLINE.set(outer)
        remaining = []
        expected = ({'plan': {}}, [], {'input_tokens': 0, 'output_tokens': 0})

        def finish(*_, **__):
            remaining.append(assistant.TURN_DEADLINE.get() - time.monotonic())
            return expected

        try:
            with patch.object(assistant, '_build_final', side_effect=finish):
                self.assertEqual(assistant.build_final(None, 'test', MESSAGES, '2026-09-30'), expected)
            self.assertGreater(remaining[0], 119)
            self.assertLessEqual(remaining[0], 120)
            self.assertEqual(assistant.TURN_DEADLINE.get(), outer)
            with patch.object(assistant, '_build_final', side_effect=assistant.AssistantError('expired')):
                with self.assertRaises(assistant.AssistantError):
                    assistant.build_final(None, 'test', MESSAGES, '2026-09-30')
            self.assertEqual(assistant.TURN_DEADLINE.get(), outer)
        finally:
            assistant.TURN_DEADLINE.reset(token)


if __name__ == '__main__':
    unittest.main()
