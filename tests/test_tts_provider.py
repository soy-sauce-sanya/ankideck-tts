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
