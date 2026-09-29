import base64
import io
import sys
import unittest
import wave
from types import SimpleNamespace
from unittest.mock import patch

import tts_provider


class FakeResponse:
    def __init__(self, chunks=(b"audio",), status_code=200, content_length=None):
        self.chunks = list(chunks)
        self.status_code = status_code
        if content_length is None:
            content_length = sum(len(c) for c in self.chunks)
        self.headers = {"Content-Length": str(content_length)} if content_length else {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def iter_content(self, chunk_size):
        self.chunk_size = chunk_size
        yield from self.chunks


class ProxyError(Exception):
    pass


class ConnectionError(Exception):
    pass


def raise_(exc):
    def raiser(*_args, **_kwargs):
        raise exc
    return raiser


class FakeSession:
    def __init__(self, get):
        self.trust_env = True
        self.get_calls = []
        self._get = get

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, *args, **kwargs):
        self.get_calls.append((self.trust_env, args, kwargs))
        return self._get(*args, **kwargs)


class TtsDownloadTests(unittest.TestCase):
    URL = "https://audio.example/file?secret=value"

    def download(self, get, session=None, on_progress=None):
        fake_requests = SimpleNamespace(
            get=get,
            exceptions=SimpleNamespace(ProxyError=ProxyError),
        )
        if session is not None:
            fake_requests.Session = lambda: session
        else:
            fake_requests.Session = raise_(AssertionError("Session must not be used"))
        with patch.object(tts_provider.importlib.util, "find_spec", return_value=True), patch.dict(
            sys.modules, {"requests": fake_requests}
        ):
            return tts_provider.http_get_bytes_stream(self.URL, on_progress=on_progress)

    def test_downloads_all_chunks_and_reports_progress(self):
        calls = []

        def get(url, **kwargs):
            calls.append((url, kwargs))
            return FakeResponse([b"ab", b"", b"cd"], content_length=4)

        progress = []
        data, error = self.download(get, on_progress=progress.append)

        self.assertEqual(data, b"abcd")
        self.assertIsNone(error)
        self.assertEqual(progress, [50, 100, 100])
        self.assertEqual(calls, [(self.URL, {"stream": True, "timeout": 120})])

    def test_progress_is_capped_when_content_length_is_too_small(self):
        progress = []
        data, error = self.download(
            lambda *_a, **_k: FakeResponse([b"abcd"], content_length=2), on_progress=progress.append
        )

        self.assertEqual(data, b"abcd")
        self.assertEqual(progress, [100, 100])

    def test_no_progress_without_content_length(self):
        progress = []
        data, error = self.download(
            lambda *_a, **_k: FakeResponse([b"abcd"], content_length=0), on_progress=progress.append
        )

        self.assertEqual(data, b"abcd")
        self.assertEqual(progress, [])

    def test_http_error_status_is_returned_without_retry(self):
        data, error = self.download(lambda *_a, **_k: FakeResponse(status_code=403))

        self.assertIsNone(data)
        self.assertEqual(error, "HTTP 403")

    def test_proxy_failure_retries_without_environment_proxy(self):
        session = FakeSession(lambda *_a, **_k: FakeResponse())

        data, error = self.download(raise_(ProxyError()), session=session)

        self.assertEqual(data, b"audio")
        self.assertIsNone(error)
        self.assertEqual(len(session.get_calls), 1)
        trust_env, args, kwargs = session.get_calls[0]
        self.assertFalse(trust_env)
        self.assertEqual(args, (self.URL,))
        self.assertEqual(kwargs, {"stream": True, "timeout": 120})

    def test_direct_retry_reports_progress(self):
        session = FakeSession(lambda *_a, **_k: FakeResponse([b"ab", b"cd"]))
        progress = []

        data, error = self.download(raise_(ProxyError()), session=session, on_progress=progress.append)

        self.assertEqual(data, b"abcd")
        self.assertEqual(progress, [50, 100, 100])

    def test_direct_retry_http_error_is_returned(self):
        session = FakeSession(lambda *_a, **_k: FakeResponse(status_code=502))

        data, error = self.download(raise_(ProxyError()), session=session)

        self.assertIsNone(data)
        self.assertEqual(error, "HTTP 502")
        self.assertEqual(len(session.get_calls), 1)

    def test_direct_retry_failure_is_reported_once_without_signed_url(self):
        session = FakeSession(raise_(ConnectionError("https://audio.example/file?secret=value")))

        data, error = self.download(raise_(ProxyError()), session=session)

        self.assertIsNone(data)
        self.assertEqual(error, "Direct connection to audio.example failed (ConnectionError)")
        self.assertNotIn("secret", error)
        self.assertEqual(len(session.get_calls), 1)

    def test_proxy_error_during_streaming_retries_directly(self):
        class BrokenResponse(FakeResponse):
            def iter_content(self, chunk_size):
                yield b"partial"
                raise ProxyError()

        session = FakeSession(lambda *_a, **_k: FakeResponse([b"full"]))

        data, error = self.download(lambda *_a, **_k: BrokenResponse([b"x"]), session=session)

        self.assertEqual(data, b"full")
        self.assertIsNone(error)

    def test_download_error_does_not_expose_signed_url(self):
        data, error = self.download(raise_(ConnectionError("https://audio.example/file?secret=value")))

        self.assertIsNone(data)
        self.assertEqual(error, "Connection to audio.example failed (ConnectionError)")
        self.assertNotIn("secret", error)

    def test_urllib_fallback_without_requests(self):
        class UrlResponse(io.BytesIO):
            status = 200

        progress = []
        with patch.object(tts_provider.importlib.util, "find_spec", return_value=None), patch.object(
            tts_provider.urllib.request, "urlopen", return_value=UrlResponse(b"audio")
        ) as urlopen:
            data, error = tts_provider.http_get_bytes_stream(self.URL, on_progress=progress.append)

        self.assertEqual(data, b"audio")
        self.assertIsNone(error)
        self.assertEqual(progress, [100])
        urlopen.assert_called_once_with(self.URL, timeout=120)


def gemini_response(data=None, mime_type="audio/L16;codec=pcm;rate=24000", finish_reason="STOP"):
    candidate = {"finishReason": finish_reason, "content": {"parts": []}}
    if finish_reason is None:
        del candidate["finishReason"]
    if data is not None:
        candidate["content"]["parts"].append({"inlineData": {"mimeType": mime_type, "data": data}})
    return {"candidates": [candidate]}


def b64(data):
    return base64.b64encode(data).decode("ascii")


class GeminiRetryTests(unittest.TestCase):
    TTS = {"provider": "gemini"}

    def synthesize(self, responses):
        responses = list(responses)
        calls = []

        def post_json(url, headers, payload):
            calls.append((url, headers, payload))
            return responses.pop(0)

        with patch.object(tts_provider, "_post_json", side_effect=post_json):
            result = tts_provider._synthesize_gemini_tts("你好", self.TTS, "key")
        return result, calls

    def test_success_on_first_attempt_does_not_retry(self):
        (data, error), calls = self.synthesize([(gemini_response(b64(b"RIFF"), "audio/wav"), None)])

        self.assertEqual(data, b"RIFF")
        self.assertIsNone(error)
        self.assertEqual(len(calls), 1)

    def test_retries_when_audio_is_missing_without_finish_reason(self):
        (data, error), calls = self.synthesize([
            (gemini_response(finish_reason=None), None),
            (gemini_response(b64(b"RIFF"), "audio/wav"), None),
        ])

        self.assertEqual(data, b"RIFF")
        self.assertIsNone(error)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], calls[1])

    def test_retries_when_finish_reason_is_other(self):
        (data, error), calls = self.synthesize([
            (gemini_response(finish_reason="OTHER"), None),
            (gemini_response(b64(b"ID3"), "audio/mpeg"), None),
        ])

        self.assertEqual(data, b"ID3")
        self.assertEqual(len(calls), 2)

    def test_retries_when_response_has_no_candidates(self):
        (data, error), calls = self.synthesize([
            ({}, None),
            (gemini_response(b64(b"RIFF"), "audio/wav"), None),
        ])

        self.assertEqual(data, b"RIFF")
        self.assertEqual(len(calls), 2)

    def test_does_not_retry_on_terminal_finish_reason(self):
        (data, error), calls = self.synthesize([(gemini_response(finish_reason="SAFETY"), None)])

        self.assertIsNone(data)
        self.assertIn("finishReason=SAFETY", error)
        self.assertEqual(len(calls), 1)

    def test_gives_up_after_two_attempts(self):
        (data, error), calls = self.synthesize([
            (gemini_response(finish_reason="OTHER"), None),
            (gemini_response(finish_reason="OTHER"), None),
            (gemini_response(b64(b"RIFF"), "audio/wav"), None),
        ])

        self.assertIsNone(data)
        self.assertIn("finishReason=OTHER", error)
        self.assertEqual(len(calls), 2)

    def test_missing_finish_reason_is_reported_as_unknown(self):
        (data, error), calls = self.synthesize([
            (gemini_response(finish_reason=None), None),
            (gemini_response(finish_reason=None), None),
        ])

        self.assertIsNone(data)
        self.assertIn("finishReason=unknown", error)
        self.assertEqual(len(calls), 2)

    def test_http_error_is_not_retried(self):
        (data, error), calls = self.synthesize([
            (None, "HTTP 429: quota"),
            (gemini_response(b64(b"RIFF"), "audio/wav"), None),
        ])

        self.assertIsNone(data)
        self.assertEqual(error, "HTTP 429: quota")
        self.assertEqual(len(calls), 1)

    def test_http_error_on_retry_is_returned(self):
        (data, error), calls = self.synthesize([
            (gemini_response(finish_reason="OTHER"), None),
            (None, "HTTP 500: boom"),
        ])

        self.assertIsNone(data)
        self.assertEqual(error, "HTTP 500: boom")
        self.assertEqual(len(calls), 2)

    def test_pcm_audio_is_wrapped_as_wav(self):
        pcm = b"\x00\x01" * 100
        (data, error), _calls = self.synthesize([(gemini_response(b64(pcm)), None)])

        self.assertIsNone(error)
        with wave.open(io.BytesIO(data), "rb") as wav_file:
            self.assertEqual(wav_file.getnchannels(), 1)
            self.assertEqual(wav_file.getsampwidth(), 2)
            self.assertEqual(wav_file.getframerate(), 24000)
            self.assertEqual(wav_file.readframes(wav_file.getnframes()), pcm)

    def test_invalid_base64_is_reported(self):
        (data, error), _calls = self.synthesize([(gemini_response("abc"), None)])

        self.assertIsNone(data)
        self.assertIn("Failed to decode Gemini audio payload", error)


class DashScopeDownloadTests(unittest.TestCase):
    def test_download_error_is_prefixed(self):
        response = SimpleNamespace(status_code=200, output={"audio": {"url": "https://audio.example/a.wav"}})
        fake_dashscope = SimpleNamespace(
            audio=SimpleNamespace(qwen_tts=SimpleNamespace(
                SpeechSynthesizer=SimpleNamespace(call=lambda **_kwargs: response)
            ))
        )

        with patch.object(tts_provider.importlib.util, "find_spec", return_value=True), patch.dict(
            sys.modules, {"dashscope": fake_dashscope}
        ), patch.object(
            tts_provider, "http_get_bytes_stream", return_value=(None, "Direct connection to audio.example failed (ConnectTimeout)")
        ) as download:
            data, error = tts_provider._synthesize_dashscope_tts("你好", {}, "key")

        self.assertIsNone(data)
        self.assertEqual(error, "Audio download error: Direct connection to audio.example failed (ConnectTimeout)")
        download.assert_called_once_with("https://audio.example/a.wav", on_progress=None)


if __name__ == "__main__":
    unittest.main()
