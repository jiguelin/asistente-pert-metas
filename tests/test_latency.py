"""Fast turn controls and cancellation, exercised without an API connection."""
import json
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pert_assistant as assistant
from intake import calculations


def response(data):
    return SimpleNamespace(output_text=json.dumps(data, ensure_ascii=False), usage=None)


def snapshot(*, accepted_mini=True, confirmed_days=False):
    facts = {
        'meta': 'Caminar 5 km', 'inicio': '2026-10-01', 'fin': '2026-10-31',
        'situacion': 'Camino 2 km', 'obstaculos': 'Falta de constancia',
        'principal': 'Constancia', 'habilidades': 'Organizar mi tiempo',
        'apoyos': 'Un amigo', 'disponibilidad': '45 minutos por bloque',
    }
    if accepted_mini:
        facts['mini_aprobadas'] = 'true'
    if confirmed_days:
        facts['minutos_semana'] = '[45,0,45,0,45,0,0]'
    return {'facts': facts, 'meta_verificable': True, 'ambiguedad_esencial': None}


class FakeStream:
    """A synchronous stream that can stall until close interrupts its wait."""
    def __init__(self, wait_at=None):
        self.wait_at = wait_at
        self.closed = threading.Event()
        self.exited = threading.Event()
        self.active = False
        self.close_count = 0
        self.interrupted = False
        self.result = response({'reply': 'Propuesta completa', 'finalize': False})

    def __enter__(self):
        self.active = True
        return self

    def __exit__(self, *_):
        self.active = False
        self.exited.set()

    def _wait_for_close(self):
        if not self.closed.wait(1):
            raise AssertionError('The active stream was not interrupted')
        self.interrupted = True

    def __iter__(self):
        if self.wait_at == 'iteration':
            self._wait_for_close()
        return iter(())

    def get_final_response(self):
        if self.wait_at == 'final_response':
            self._wait_for_close()
        if self.interrupted:
            raise RuntimeError("Didn't receive a `response.completed` event.")
        return self.result

    def close(self):
        self.close_count += 1
        self.closed.set()


class FakeClient:
    def __init__(self, stream):
        self.stream_result = stream
        self.options = []
        self.calls = []
        self.responses = SimpleNamespace(stream=self._stream)

    def with_options(self, **kwargs):
        self.options.append(kwargs)
        return self

    def _stream(self, **kwargs):
        self.calls.append(kwargs)
        return self.stream_result


class LatencyTests(unittest.TestCase):
    def test_teaching_phases_use_core_instructions_and_final_uses_full_guide(self):
        core = (assistant.ROOT / 'resources/INSTRUCTIONS_APP.txt').read_text(encoding='utf-8')
        guide = (assistant.ROOT / 'resources/GUIA_OPERATIVA_PERT_FISICO.txt').read_text(encoding='utf-8')
        for phase in ['criterio', 'habilidades', 'mini', 'tareas']:
            with self.subTest(phase=phase):
                instructions = assistant._instructions(phase)
                self.assertIn(core, instructions)
                self.assertNotIn(guide, instructions)
        self.assertIn(guide, assistant._instructions('final'))
        self.assertEqual(assistant._instructions(), assistant._instructions('final'))

    def test_compact_calculations_keep_duration_counts_and_finances(self):
        facts = {
            'inicio': '2026-10-01', 'fin': '2026-12-31', 'tipo': 'ahorro',
            'saldo': '1500', 'ingreso': '2200', 'gasto': '1200',
            'reserva': '1200', 'objetivo': '4000',
            'gastos_inicio_pagados': 'true', 'cobro_fin_mes': 'true',
        }
        full = calculations(facts)
        compact = calculations(facts, include_calendar=False)
        self.assertEqual(compact.splitlines(), [
            line for line in full.splitlines()
            if not line.startswith('Fechas y días reales:')
        ])
        for value in ['92 días inclusivos', 'jueves: 14', 'domingo: 13',
                      'libre 4500', 'brecha 0', 'CAJA CALCULADA:']:
            self.assertIn(value, compact)
        self.assertNotIn('2026-10-04 domingo', compact)

    def test_missing_confirmed_days_asks_once_before_drafting_tasks(self):
        current = snapshot()
        progress = []
        token = assistant.PROGRESS.set(progress.append)
        try:
            with patch.object(assistant, 'extract_intake', return_value=current), \
                    patch.object(assistant, '_create') as create, \
                    patch.object(assistant, 'review') as review:
                reply, finalize, usage = assistant.respond(
                    None, 'test', [{'role': 'user', 'content': 'Acepto las mini metas.'}],
                    '2026-09-30')
        finally:
            assistant.PROGRESS.reset(token)
        self.assertIn('Qué días de la semana', reply)
        self.assertEqual(reply.count('¿'), 1)
        self.assertEqual(reply.count('?'), 1)
        self.assertFalse(finalize)
        self.assertIs(usage['snapshot'], current)
        create.assert_not_called()
        review.assert_not_called()
        self.assertEqual(progress, ['Leyendo tu respuesta…'])

    def test_confirmed_days_generate_and_review_tasks_with_progress(self):
        current = snapshot(confirmed_days=True)
        proposed = 'T1: caminar lunes, miércoles y viernes. ¿Aceptas las tareas?'
        progress = []
        token = assistant.PROGRESS.set(progress.append)
        try:
            with patch.object(assistant, 'extract_intake', return_value=current), \
                    patch.object(assistant, '_create', return_value=response(
                        {'reply': proposed, 'finalize': False})) as create, \
                    patch.object(assistant, 'review', return_value={
                        'ok': True, 'problems': []}) as review:
                reply, finalize, _ = assistant.respond(
                    None, 'test', [{'role': 'user', 'content': 'Lunes, miércoles y viernes.'}],
                    '2026-09-30')
        finally:
            assistant.PROGRESS.reset(token)
        self.assertEqual(reply, proposed)
        self.assertFalse(finalize)
        self.assertEqual(create.call_count, 1)
        self.assertEqual(review.call_args.args[5], 'tareas')
        self.assertIn('2026-10-04 domingo', review.call_args.args[4])
        self.assertIn(current['facts']['minutos_semana'], create.call_args.kwargs['instructions'])
        self.assertEqual(progress, [
            'Leyendo tu respuesta…', 'Preparando tus tareas y horarios…',
            'Revisando la propuesta antes de mostrártela…',
        ])

    def test_mini_draft_uses_compact_calendar_and_progress(self):
        current = snapshot(accepted_mini=False, confirmed_days=True)
        proposed = 'M1: recorrido de 3 km comprobado. ¿Aceptas las mini metas?'
        progress = []
        token = assistant.PROGRESS.set(progress.append)
        try:
            with patch.object(assistant, 'extract_intake', return_value=current), \
                    patch.object(assistant, '_create', return_value=response(
                        {'reply': proposed, 'finalize': False})) as create, \
                    patch.object(assistant, 'review', return_value={
                        'ok': True, 'problems': []}):
                reply, _, _ = assistant.respond(None, 'test', [
                    {'role': 'user', 'content': 'Tengo 45 minutos.'}], '2026-09-30')
        finally:
            assistant.PROGRESS.reset(token)
        instructions = create.call_args.kwargs['instructions']
        self.assertEqual(reply, proposed)
        self.assertIn('31 días inclusivos', instructions)
        self.assertIn('Cantidad de días reales:', instructions)
        self.assertNotIn('Fechas y días reales:', instructions)
        self.assertNotIn('GUÍA OPERATIVA:', instructions)
        self.assertEqual(progress, [
            'Leyendo tu respuesta…', 'Preparando tus mini metas…',
            'Revisando la propuesta antes de mostrártela…',
        ])

    def test_deadline_interrupts_active_stream_synchronously_without_restart(self):
        for wait_at in ['iteration', 'final_response']:
            with self.subTest(wait_at=wait_at):
                stream = FakeStream(wait_at)
                client = FakeClient(stream)
                started = time.monotonic()
                token = assistant.TURN_DEADLINE.set(started + 0.03)
                try:
                    with self.assertRaises(assistant.AssistantError):
                        assistant._create(client, model='test')
                finally:
                    assistant.TURN_DEADLINE.reset(token)
                elapsed = time.monotonic() - started
                self.assertLess(elapsed, 0.5)
                self.assertTrue(stream.closed.is_set())
                self.assertTrue(stream.exited.is_set())
                self.assertFalse(stream.active)
                self.assertEqual(stream.close_count, 1)
                self.assertEqual(len(client.calls), 1)
                self.assertEqual(len(client.options), 1)
                self.assertGreater(client.options[0]['timeout'], 0)
                self.assertLessEqual(client.options[0]['timeout'], 0.03)
                self.assertEqual(client.options[0]['max_retries'], 0)

    def test_expired_deadline_never_invokes_client(self):
        client = FakeClient(FakeStream())
        token = assistant.TURN_DEADLINE.set(time.monotonic())
        try:
            with self.assertRaises(assistant.AssistantError):
                assistant._create(client, model='test')
        finally:
            assistant.TURN_DEADLINE.reset(token)
        self.assertEqual(client.options, [])
        self.assertEqual(client.calls, [])

    def test_success_cancels_stream_close_timer(self):
        stream = FakeStream()
        client = FakeClient(stream)
        token = assistant.TURN_DEADLINE.set(time.monotonic() + 0.03)
        try:
            result = assistant._create(client, model='test')
        finally:
            assistant.TURN_DEADLINE.reset(token)
        self.assertIs(result, stream.result)
        self.assertTrue(stream.exited.is_set())
        self.assertFalse(stream.closed.wait(0.06), 'An expired timer closed a completed stream')

    def test_long_deadline_limits_sdk_timeout_to_thirty_seconds(self):
        client = FakeClient(FakeStream())
        token = assistant.TURN_DEADLINE.set(time.monotonic() + 45)
        try:
            assistant._create(client, model='test')
        finally:
            assistant.TURN_DEADLINE.reset(token)
        self.assertEqual(client.options, [{'timeout': 30, 'max_retries': 0}])

    def test_respond_sets_ninety_second_deadline_and_restores_outer_context(self):
        outer = time.monotonic() + 200
        token = assistant.TURN_DEADLINE.set(outer)
        observed = []

        def wrapped(*_):
            observed.append(assistant.TURN_DEADLINE.get() - time.monotonic())
            return ('respuesta', False, {})

        try:
            with patch.object(assistant, '_respond', side_effect=wrapped):
                result = assistant.respond(None, 'test', [], '2026-09-30')
            self.assertEqual(result, ('respuesta', False, {}))
            self.assertGreater(observed[0], 89)
            self.assertLessEqual(observed[0], 90)
            self.assertEqual(assistant.TURN_DEADLINE.get(), outer)
            with patch.object(assistant, '_respond', side_effect=assistant.AssistantError('expired')):
                with self.assertRaises(assistant.AssistantError):
                    assistant.respond(None, 'test', [], '2026-09-30')
            self.assertEqual(assistant.TURN_DEADLINE.get(), outer)
        finally:
            assistant.TURN_DEADLINE.reset(token)

    def test_three_rejected_drafts_stop_without_publishing(self):
        current = snapshot(accepted_mini=False, confirmed_days=True)
        progress = []
        token = assistant.PROGRESS.set(progress.append)
        try:
            with patch.object(assistant, 'extract_intake', return_value=current), \
                    patch.object(assistant, '_create', return_value=response({
                        'reply': 'Borrador pendiente. ¿Lo aceptas?', 'finalize': False})) as create, \
                    patch.object(assistant, 'review', return_value={
                        'ok': False, 'problems': ['Fechas incorrectas']}) as review:
                with self.assertRaises(assistant.AssistantError):
                    assistant.respond(None, 'test', [
                        {'role': 'user', 'content': 'Tengo 45 minutos.'}], '2026-09-30')
        finally:
            assistant.PROGRESS.reset(token)
        self.assertEqual(create.call_count, 3)
        self.assertEqual(review.call_count, 3)
        self.assertEqual(progress.count('Ajustando la propuesta después de revisarla…'), 2)
        self.assertEqual(progress.count('Revisando la propuesta antes de mostrártela…'), 3)

    def test_expiry_during_review_prevents_another_draft(self):
        current = snapshot(accepted_mini=False, confirmed_days=True)

        def reject_after_expiry(*_):
            assistant.TURN_DEADLINE.set(time.monotonic())
            return {'ok': False, 'problems': ['Debe ajustarse']}

        outer = assistant.TURN_DEADLINE.get()
        with patch.object(assistant, 'extract_intake', return_value=current), \
                patch.object(assistant, '_create', return_value=response({
                    'reply': 'Borrador pendiente. ¿Lo aceptas?', 'finalize': False})) as create, \
                patch.object(assistant, 'review', side_effect=reject_after_expiry):
            with self.assertRaises(assistant.AssistantError):
                assistant.respond(None, 'test', [
                    {'role': 'user', 'content': 'Tengo 45 minutos.'}], '2026-09-30')
        self.assertEqual(create.call_count, 1)
        self.assertEqual(assistant.TURN_DEADLINE.get(), outer)


if __name__ == '__main__':
    unittest.main()
