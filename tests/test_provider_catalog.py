import unittest
from unittest.mock import patch

import provider_catalog


class ProviderCatalogTests(unittest.TestCase):
    @patch("provider_catalog._get_json")
    def test_openai_keeps_only_tts_models(self, get_json):
        get_json.return_value = ({"data": [
            {"id": "gpt-4o-mini-tts"},
            {"id": "tts-1"},
            {"id": "gpt-4.1"},
        ]}, None)

        catalog, error = provider_catalog.fetch_provider_catalog("openai", "key")

        self.assertIsNone(error)
        self.assertEqual(catalog["models"], ["gpt-4o-mini-tts", "tts-1"])

    @patch("provider_catalog._get_json")
    def test_gemini_removes_model_prefix_and_filters_tts(self, get_json):
        get_json.return_value = ({"models": [
            {"name": "models/gemini-3.1-flash-tts-preview"},
            {"name": "models/gemini-3.1-flash"},
        ]}, None)

        catalog, error = provider_catalog.fetch_provider_catalog("gemini", "key")

        self.assertIsNone(error)
        self.assertEqual(catalog["models"], ["gemini-3.1-flash-tts-preview"])

    @patch("provider_catalog._get_json")
    def test_elevenlabs_loads_tts_models_and_account_voices(self, get_json):
        get_json.side_effect = [
            ([
                {"model_id": "eleven_multilingual_v2", "can_do_text_to_speech": True},
                {"model_id": "voice-conversion", "can_do_text_to_speech": False},
            ], None),
            ({
                "voices": [{"voice_id": "abc", "name": "My Voice"}],
                "has_more": False,
            }, None),
        ]

        catalog, error = provider_catalog.fetch_provider_catalog("elevenlabs", "key")

        self.assertIsNone(error)
        self.assertEqual(catalog["models"], ["eleven_multilingual_v2"])
        self.assertEqual(catalog["voices"], [{"chinese": "My Voice", "english": "abc"}])

    def test_api_key_is_required(self):
        catalog, error = provider_catalog.fetch_provider_catalog("openai", "")

        self.assertIsNone(catalog)
        self.assertEqual(error, "API key is required")

    @patch("provider_catalog._get_json")
    def test_local_server_lists_all_models_without_api_key(self, get_json):
        get_json.side_effect = [
            ({"data": [{"id": "orpheus-3b"}, {"id": "kokoro"}]}, None),
            ({"voices": ["af_bella", {"id": "tara", "name": "Tara"}]}, None),
        ]

        catalog, error = provider_catalog.fetch_provider_catalog("local", "", "http://localhost:8000/v1")

        self.assertIsNone(error)
        self.assertEqual(catalog["models"], ["kokoro", "orpheus-3b"])
        self.assertEqual(catalog["voices"], [
            {"chinese": "af_bella", "english": "af_bella"},
            {"chinese": "Tara", "english": "tara"},
        ])
        self.assertEqual(get_json.call_args_list[0].args[0], "http://localhost:8000/v1/models")
        self.assertEqual(get_json.call_args_list[0].args[1], {})
        self.assertFalse(get_json.call_args_list[0].kwargs["use_env_proxy"])

    @patch("provider_catalog._get_json")
    def test_local_server_without_voice_list_still_returns_models(self, get_json):
        get_json.side_effect = [
            ({"data": [{"id": "llama3"}]}, None),
            (None, "HTTP 404"),
        ]

        catalog, error = provider_catalog.fetch_provider_catalog("local", "", "http://localhost:8880/v1")

        self.assertIsNone(error)
        self.assertEqual(catalog, {"models": ["llama3"], "voices": []})


if __name__ == "__main__":
    unittest.main()
