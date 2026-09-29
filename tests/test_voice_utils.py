import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

import voice_utils


class ParseVoicesFileTests(unittest.TestCase):
    def write_voices(self, content):
        fd, path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        self.addCleanup(os.unlink, path)
        return path

    def test_parses_voices_and_languages(self):
        path = self.write_voices(
            "# voices:\n"
            "# 芊悦 / Cherry\n"
            "#  晨煦/Ethan  \n"
            "\n"
            "# languages:\n"
            "# 中文、英语、 法语 \n"
            "# 日语、\n"
        )

        voices, languages = voice_utils.parse_voices_file(path)

        self.assertEqual(voices, [
            {"chinese": "芊悦", "english": "Cherry"},
            {"chinese": "晨煦", "english": "Ethan"},
        ])
        self.assertEqual(languages, ["中文", "英语", "法语", "日语"])

    def test_ignores_lines_outside_sections_and_malformed_voices(self):
        path = self.write_voices(
            "# 不在 / Section\n"
            "# some comment\n"
            "# voices:\n"
            "# a / b / c\n"
            "not a comment / Voice\n"
            "# 甜茶 / Ryan\n"
        )

        voices, languages = voice_utils.parse_voices_file(path)

        self.assertEqual(voices, [{"chinese": "甜茶", "english": "Ryan"}])
        self.assertEqual(languages, [])

    def test_missing_file_returns_empty_lists(self):
        with redirect_stdout(StringIO()):
            voices, languages = voice_utils.parse_voices_file("/nonexistent/voices.txt")

        self.assertEqual((voices, languages), ([], []))

    def test_bundled_voices_file(self):
        voices, languages = voice_utils.get_voices_and_languages()

        self.assertIn({"chinese": "芊悦", "english": "Cherry"}, voices)
        self.assertEqual(len(voices), len({v["english"] for v in voices}))
        self.assertIn("中文", languages)
        for lang in languages:
            self.assertNotEqual(voice_utils.language_display_to_api_format(lang), lang)


class VoiceDisplayTests(unittest.TestCase):
    def test_display_name(self):
        voice = {"chinese": "芊悦", "english": "Cherry"}
        self.assertEqual(voice_utils.get_voice_display_name(voice), "芊悦 (Cherry)")


class ProviderCatalogTests(unittest.TestCase):
    def test_provider_voices(self):
        cases = {
            "openai": voice_utils.OPENAI_VOICES,
            "OpenAI": voice_utils.OPENAI_VOICES,
            "elevenlabs": voice_utils.ELEVENLABS_VOICES,
            "gemini": voice_utils.GEMINI_VOICES,
        }
        for provider, expected in cases.items():
            with self.subTest(provider=provider):
                self.assertEqual(voice_utils.get_provider_voices_and_languages(provider), (expected, []))

    def test_dashscope_and_unknown_use_voices_file(self):
        bundled = voice_utils.get_voices_and_languages()
        for provider in ("dashscope", "", None, "unknown"):
            with self.subTest(provider=provider):
                self.assertEqual(voice_utils.get_provider_voices_and_languages(provider), bundled)

    def test_provider_models(self):
        self.assertEqual(voice_utils.get_provider_models("OPENAI"), voice_utils.PROVIDER_MODELS["openai"])
        self.assertEqual(voice_utils.get_provider_models("unknown"), [])
        self.assertEqual(voice_utils.get_provider_models(None), [])

    def test_bundled_voice_ids_are_unique(self):
        for voices in (voice_utils.OPENAI_VOICES, voice_utils.ELEVENLABS_VOICES, voice_utils.GEMINI_VOICES):
            ids = [v["english"] for v in voices]
            self.assertEqual(len(ids), len(set(ids)))


class LanguageMappingTests(unittest.TestCase):
    def test_display_to_api(self):
        self.assertEqual(voice_utils.language_display_to_api_format("中文"), "Chinese")
        self.assertEqual(voice_utils.language_display_to_api_format("俄语"), "Russian")

    def test_api_to_display(self):
        self.assertEqual(voice_utils.api_format_to_language_display("English"), "英语")
        self.assertEqual(voice_utils.api_format_to_language_display("Korean"), "韩语")

    def test_unknown_values_pass_through(self):
        self.assertEqual(voice_utils.language_display_to_api_format("Auto"), "Auto")
        self.assertEqual(voice_utils.api_format_to_language_display("Klingon"), "Klingon")

    def test_round_trip(self):
        for display in ("中文", "英语", "法语", "德语", "俄语", "意大利语", "西班牙语", "葡萄牙语", "日语", "韩语"):
            with self.subTest(display=display):
                api = voice_utils.language_display_to_api_format(display)
                self.assertEqual(voice_utils.api_format_to_language_display(api), display)


if __name__ == "__main__":
    unittest.main()
