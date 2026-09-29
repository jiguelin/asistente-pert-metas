import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


APP = str(Path(__file__).resolve().parents[1] / "app.py")


class UiTests(unittest.TestCase):
    def test_access_gate_without_credentials(self):
        at = AppTest.from_file(APP)
        at.secrets["EVENT_PASSWORD"] = "metas"
        at.secrets["OPENAI_API_KEY"] = "test-key-not-used"
        at.run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state.authenticated, False)
        self.assertEqual(len(at.chat_input), 0)

    def test_wrong_password_does_not_open_chat(self):
        at = AppTest.from_file(APP)
        at.secrets["EVENT_PASSWORD"] = "metas"
        at.secrets["OPENAI_API_KEY"] = "test-key-not-used"
        at.run()
        at.text_input[0].input("otra").run()
        at.button[0].click().run()
        self.assertEqual(len(at.chat_input), 0)
        self.assertTrue(any("Clave incorrecta" in e.value for e in at.error))

    def test_valid_password_then_rotation_closes_existing_session(self):
        at = AppTest.from_file(APP)
        at.secrets["EVENT_PASSWORD"] = "metas"
        at.secrets["OPENAI_API_KEY"] = "test-key-not-used"
        at.run()
        at.text_input[0].input("metas").run()
        at.button[0].click().run()
        self.assertFalse(at.exception)
        self.assertEqual(len(at.chat_input), 1)
        at.secrets["EVENT_PASSWORD"] = "nuevo-codigo"
        at.run()
        self.assertFalse(at.exception)
        self.assertEqual(len(at.chat_input), 0)

    def test_first_user_turn_one_question_with_mocked_api(self):
        at = AppTest.from_file(APP)
        at.secrets["EVENT_PASSWORD"] = "metas"
        at.secrets["OPENAI_API_KEY"] = "test-key-not-used"
        at.run()
        at.text_input[0].input("metas").run()
        at.button[0].click().run()
        fake = SimpleNamespace(
            output_text='{"reply":"¿Qué significa estar en forma para ti?","finalize":false}',
            usage=SimpleNamespace(input_tokens=100, output_tokens=20))
        with patch("assistant_engine._create", return_value=fake):
            at.chat_input[0].set_value("Quiero estar en forma").run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state.messages[-1]["content"],
                         "¿Qué significa estar en forma para ti?")

    def test_failed_api_turn_can_be_retried_without_duplicate_message(self):
        at = AppTest.from_file(APP)
        at.secrets["EVENT_PASSWORD"] = "metas"
        at.secrets["OPENAI_API_KEY"] = "test-key-not-used"
        at.run()
        at.text_input[0].input("metas").run()
        at.button[0].click().run()
        with patch("assistant_engine._create", side_effect=RuntimeError("simulated")):
            at.chat_input[0].set_value("Quiero aprender inglés").run()
        self.assertFalse(at.session_state.messages)
        self.assertEqual(at.session_state.pending_text, "Quiero aprender inglés")
        at.run()
        fake = SimpleNamespace(
            output_text='{"reply":"¿Cómo demostrarás que aprendiste inglés?","finalize":false}',
            usage=SimpleNamespace(input_tokens=100, output_tokens=20))
        with patch("assistant_engine._create", return_value=fake):
            next(b for b in at.button if b.label == "Reintentar mi mensaje").click().run()
        self.assertEqual([m["role"] for m in at.session_state.messages], ["user", "assistant"])
        self.assertIsNone(at.session_state.pending_text)


if __name__ == "__main__":
    unittest.main()
