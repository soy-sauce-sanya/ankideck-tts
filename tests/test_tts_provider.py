import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import tts_provider


class FakeResponse:
    status_code = 200
    headers = {"Content-Length": "5"}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def iter_content(self, chunk_size):
        self.chunk_size = chunk_size
        yield b"audio"


class TtsDownloadTests(unittest.TestCase):
    def test_proxy_failure_retries_without_environment_proxy(self):
        class ProxyError(Exception):
            pass

        class Session:
            trust_env = True

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def get(self, *_args, **_kwargs):
                self.test.assertFalse(self.trust_env)
                return FakeResponse()

        session = Session()
        session.test = self
        fake_requests = SimpleNamespace(
            get=lambda *_args, **_kwargs: (_ for _ in ()).throw(ProxyError()),
            Session=lambda: session,
            exceptions=SimpleNamespace(ProxyError=ProxyError),
        )

        with patch.object(tts_provider.importlib.util, "find_spec", return_value=True), patch.dict(
            sys.modules, {"requests": fake_requests}
        ):
            data, error = tts_provider.http_get_bytes_stream("https://audio.example/file?secret=value")

        self.assertEqual(data, b"audio")
        self.assertIsNone(error)

    def test_download_error_does_not_expose_signed_url(self):
        class ProxyError(Exception):
            pass

        class ConnectionError(Exception):
            pass

        fake_requests = SimpleNamespace(
            get=lambda *_args, **_kwargs: (_ for _ in ()).throw(ConnectionError()),
            exceptions=SimpleNamespace(ProxyError=ProxyError),
        )

        with patch.object(tts_provider.importlib.util, "find_spec", return_value=True), patch.dict(
            sys.modules, {"requests": fake_requests}
        ):
            data, error = tts_provider.http_get_bytes_stream("https://audio.example/file?secret=value")

        self.assertIsNone(data)
        self.assertIn("audio.example", error)
        self.assertNotIn("secret", error)


class LocalProviderTests(unittest.TestCase):
    def test_base_url_defaults_and_normalization(self):
        self.assertEqual(tts_provider.resolve_base_url({}, "lmstudio"), "http://localhost:1234/v1")
        self.assertEqual(tts_provider.resolve_base_url({}, "ollama"), "http://localhost:11434/v1")
        self.assertEqual(tts_provider.normalize_base_url("192.168.1.5:8880/"), "http://192.168.1.5:8880/v1")
        self.assertEqual(tts_provider.normalize_base_url("http://host:5005/v1/"), "http://host:5005/v1")

    @patch("tts_provider._post_json_for_bytes")
    def test_local_synthesis_uses_openai_speech_api_without_cloud_key(self, post):
        post.return_value = (b"RIFF", None)
        cfg = {"tts": {
            "provider": "ollama",
            "api_key": "cloud-secret",
            "base_urls": {"ollama": "http://localhost:11434/v1"},
            "models": {"ollama": "orpheus"},
            "voices": {"ollama": "tara"},
            "exts": {"ollama": "wav"},
        }}

        data, error = tts_provider.synthesize_tts_bytes("hello", cfg)

        self.assertEqual(data, b"RIFF")
        self.assertIsNone(error)
        url, headers, payload = post.call_args.args
        self.assertEqual(url, "http://localhost:11434/v1/audio/speech")
        self.assertNotIn("Authorization", headers)
        self.assertEqual(payload, {"model": "orpheus", "input": "hello", "response_format": "wav", "voice": "tara"})
        self.assertFalse(post.call_args.kwargs["use_env_proxy"])

    @patch("tts_provider._post_json_for_bytes")
    def test_local_server_without_speech_endpoint_explains_error(self, post):
        post.return_value = (None, "HTTP 404: Unexpected endpoint")
        cfg = {"tts": {"provider": "lmstudio", "models": {"lmstudio": "some-model"}}}

        data, error = tts_provider.synthesize_tts_bytes("hello", cfg)

        self.assertIsNone(data)
        self.assertIn("LM Studio", error)
        self.assertIn("/audio/speech", error)

    def test_local_synthesis_requires_model(self):
        data, error = tts_provider.synthesize_tts_bytes("hello", {"tts": {"provider": "lmstudio"}})

        self.assertIsNone(data)
        self.assertIn("model", error)


class OpenAiTtsTests(unittest.TestCase):
    def test_payload_uses_response_format_from_configured_ext(self):
        tts = {"exts": {"openai": "wav"}}

        with patch.object(tts_provider, "_post_json_for_bytes", return_value=(b"audio", None)) as post:
            data, error = tts_provider._synthesize_openai_tts("hello", tts, "sk-test")

        self.assertEqual(data, b"audio")
        self.assertIsNone(error)
        url, _headers, payload = post.call_args.args
        self.assertEqual(url, "https://api.openai.com/v1/audio/speech")
        self.assertEqual(payload["response_format"], "wav")
        self.assertNotIn("format", payload)


if __name__ == "__main__":
    unittest.main()
