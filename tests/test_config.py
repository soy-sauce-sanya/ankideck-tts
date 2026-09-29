import sys
import types
import unittest

if "aqt" not in sys.modules:
    fake_aqt = types.ModuleType("aqt")
    fake_aqt.mw = None
    sys.modules["aqt"] = fake_aqt

import config


class LocalProviderMigrationTests(unittest.TestCase):
    def test_selected_lmstudio_settings_move_to_local(self):
        tts = config._migrate_local_provider({
            "provider": "lmstudio",
            "base_urls": {"lmstudio": "http://localhost:8880/v1", "ollama": "http://localhost:11434/v1"},
            "models": {"lmstudio": "kokoro", "ollama": ""},
            "voices": {"lmstudio": "af_bella"},
            "exts": {"lmstudio": "wav"},
        })

        self.assertEqual(tts["provider"], "local")
        self.assertEqual(tts["base_urls"]["local"], "http://localhost:8880/v1")
        self.assertEqual(tts["models"]["local"], "kokoro")
        self.assertEqual(tts["voices"]["local"], "af_bella")

    def test_selected_ollama_wins_over_lmstudio(self):
        tts = config._migrate_local_provider({
            "provider": "ollama",
            "models": {"lmstudio": "a", "ollama": "b"},
        })

        self.assertEqual(tts["models"]["local"], "b")

    def test_old_default_urls_are_not_carried_over(self):
        tts = config._migrate_local_provider({
            "provider": "dashscope",
            "base_urls": {"lmstudio": "http://localhost:1234/v1", "ollama": "http://localhost:11434/v1"},
        })

        self.assertEqual(tts["provider"], "dashscope")
        self.assertNotIn("local", tts["base_urls"])

    def test_existing_local_settings_are_kept(self):
        tts = config._migrate_local_provider({
            "provider": "local",
            "models": {"local": "mlx-community/Kokoro-82M-bf16", "lmstudio": "kokoro"},
        })

        self.assertEqual(tts["models"]["local"], "mlx-community/Kokoro-82M-bf16")

    def test_input_is_not_mutated(self):
        original = {"provider": "lmstudio", "models": {"lmstudio": "kokoro"}}

        config._migrate_local_provider(original)

        self.assertEqual(original, {"provider": "lmstudio", "models": {"lmstudio": "kokoro"}})

    def test_legacy_provider_names_still_synthesize_locally(self):
        import tts_provider

        self.assertTrue(tts_provider.is_local_provider("lmstudio"))
        self.assertTrue(tts_provider.is_local_provider("ollama"))
        self.assertEqual(tts_provider.resolve_base_url({}, "ollama"), "http://localhost:8000/v1")


if __name__ == "__main__":
    unittest.main()
