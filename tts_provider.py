# -*- coding: utf-8 -*-
"""TTS synthesis provider for AnkiDeck TTS addon."""

from __future__ import annotations
from typing import Optional, Tuple, Callable, Dict
import importlib.util
import json
import urllib.request
import urllib.error


def http_get_bytes_stream(url: str, on_progress: Optional[Callable[[int], None]] = None) -> Tuple[Optional[bytes], Optional[str]]:
    """Download file from URL with progress tracking.

    Args:
        url: URL to download from
        on_progress: Optional callback function that receives progress percentage (0-100)

    Returns:
        Tuple of (data, error_message). If successful, data is bytes and error is None.
        If failed, data is None and error is a string describing the error.
    """
    if importlib.util.find_spec("requests"):
        import requests
        try:
            with requests.get(url, stream=True, timeout=120) as r:
                if int(r.status_code) != 200:
                    return None, f"HTTP {r.status_code}"
                total = int(r.headers.get("Content-Length") or 0)
                chunks = []
                downloaded = 0
                for chunk in r.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    chunks.append(chunk)
                    downloaded += len(chunk)
                    if on_progress and total:
                        pct = int(downloaded * 100 / total)
                        on_progress(min(pct, 100))
                data = b"".join(chunks)
                if on_progress and total:
                    on_progress(100)
                return data, None
        except Exception as e:
            return None, f"{e}"
    try:
        with urllib.request.urlopen(url, timeout=120) as resp:
            if int(resp.status) != 200:
                return None, f"HTTP {resp.status}"
            data = resp.read()
            if on_progress:
                on_progress(100)
            return data, None
    except Exception as e:
        return None, f"{e}"


def _post_json_for_bytes(url: str, headers: Dict[str, str], payload: Dict[str, str]) -> Tuple[Optional[bytes], Optional[str]]:
    if importlib.util.find_spec("requests"):
        import requests
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
        except Exception as e:
            return None, f"{e}"
        if int(resp.status_code) != 200:
            return None, f"HTTP {resp.status_code}: {resp.text}"
        return resp.content, None

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            if int(resp.status) != 200:
                return None, f"HTTP {resp.status}"
            return resp.read(), None
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        return None, f"HTTP {e.code}: {err_body}"
    except Exception as e:
        return None, f"{e}"


def _resolve_api_key(tts: dict, provider: str) -> str:
    api_keys = tts.get("api_keys")
    if isinstance(api_keys, dict):
        api_key = api_keys.get(provider)
        if api_key:
            return api_key
    return tts.get("api_key") or ""


def _resolve_tts_setting(tts: dict, provider: str, key: str, fallback: str) -> str:
    mapping = tts.get(f"{key}s")
    if isinstance(mapping, dict):
        value = mapping.get(provider)
        if value is not None:
            return value
    return tts.get(key) or fallback


def synthesize_tts_bytes(text: str, cfg: dict, on_download_progress: Optional[Callable[[int], None]] = None) -> Tuple[Optional[bytes], Optional[str]]:
    """Synthesize text to audio using DashScope TTS API.

    Args:
        text: Text to synthesize
        cfg: Configuration dictionary containing TTS settings
        on_download_progress: Optional callback for download progress (0-100)

    Returns:
        Tuple of (audio_bytes, error_message). If successful, audio_bytes is bytes and error is None.
        If failed, audio_bytes is None and error is a string describing the error.
    """
    tts = cfg.get("tts") or {}
    provider = (tts.get("provider") or "dashscope").lower()
    api_key = _resolve_api_key(tts, provider)

    if not api_key:
        return None, "API key (tts.api_key or tts.api_keys.<provider>) is not set in add-on config."

    if provider == "openai":
        return _synthesize_openai_tts(text, tts, api_key)
    return _synthesize_dashscope_tts(text, tts, api_key, on_download_progress)

    if provider == "openai":
        return _synthesize_openai_tts(text, tts)
    return _synthesize_dashscope_tts(text, tts, on_download_progress)


def _synthesize_dashscope_tts(text: str, tts: dict, api_key: str, on_download_progress: Optional[Callable[[int], None]] = None) -> Tuple[Optional[bytes], Optional[str]]:
    model = _resolve_tts_setting(tts, "dashscope", "model", "qwen3-tts-flash")
    voice = _resolve_tts_setting(tts, "dashscope", "voice", "Cherry")
    lang = tts.get("language_type") or "Chinese"
    api_key = api_key or tts.get("api_key") or ""

    if importlib.util.find_spec("dashscope") is None:
        return None, "Module 'dashscope' is not installed in Anki's environment."

    import dashscope

    try:
        response = dashscope.audio.qwen_tts.SpeechSynthesizer.call(
            model=model, api_key=api_key, text=text, voice=voice, language_type=lang
        )
    except Exception as e:
        return None, f"DashScope error: {e}"

    status = getattr(response, "status_code", None)
    if status != 200:
        msg = getattr(response, "message", "unknown error")
        return None, f"API error (status={status}): {msg}"

    try:
        audio_url = response.output['audio']['url']
    except Exception:
        return None, "Audio URL not found in API response."

    data, err = http_get_bytes_stream(audio_url, on_progress=on_download_progress)
    if err:
        return None, f"Audio download error: {err}"

    return data, None


def _synthesize_openai_tts(text: str, tts: dict, api_key: str) -> Tuple[Optional[bytes], Optional[str]]:
    api_key = api_key or tts.get("api_key") or ""
    model = _resolve_tts_setting(tts, "openai", "model", "gpt-4o-mini-tts")
    voice = _resolve_tts_setting(tts, "openai", "voice", "alloy")
    response_format = tts.get("response_format") or _resolve_tts_setting(tts, "openai", "ext", "mp3")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "voice": voice,
        "input": text,
        "format": response_format,
    }
    return _post_json_for_bytes("https://api.openai.com/v1/audio/speech", headers, payload)
