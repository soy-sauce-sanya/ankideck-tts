# -*- coding: utf-8 -*-
"""TTS synthesis provider for AnkiDeck TTS addon."""

from __future__ import annotations
from typing import Optional, Tuple, Callable
from abc import ABC, abstractmethod


def http_get_bytes_stream(url: str, on_progress: Optional[Callable[[int], None]] = None) -> Tuple[Optional[bytes], Optional[str]]:
    """Download file from URL with progress tracking.

    Args:
        url: URL to download from
        on_progress: Optional callback function that receives progress percentage (0-100)

    Returns:
        Tuple of (data, error_message). If successful, data is bytes and error is None.
        If failed, data is None and error is a string describing the error.
    """
    try:
        import requests
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
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=120) as resp:
                if int(resp.status) != 200:
                    return None, f"HTTP {resp.status}"
                data = resp.read()
                if on_progress:
                    on_progress(100)
                return data, None
        except Exception as e2:
            return None, f"{e2}"


class TTSProvider(ABC):
    """Base class for TTS providers."""

    @abstractmethod
    def synthesize(self, text: str, cfg: dict, on_download_progress: Optional[Callable[[int], None]] = None) -> Tuple[Optional[bytes], Optional[str]]:
        """Synthesize text to audio.

        Args:
            text: Text to synthesize
            cfg: Configuration dictionary containing TTS settings
            on_download_progress: Optional callback for download progress (0-100)

        Returns:
            Tuple of (audio_bytes, error_message). If successful, audio_bytes is bytes and error is None.
            If failed, audio_bytes is None and error is a string describing the error.
        """
        pass


class QwenTTSProvider(TTSProvider):
    """DashScope/Qwen TTS provider."""

    def synthesize(self, text: str, cfg: dict, on_download_progress: Optional[Callable[[int], None]] = None) -> Tuple[Optional[bytes], Optional[str]]:
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
        api_key = tts.get("api_key") or ""
        model = tts.get("model") or "qwen3-tts-flash"
        voice = tts.get("voice") or "Cherry"
        lang = tts.get("language_type") or "Chinese"

        if not api_key:
            return None, "API key (tts.api_key) is not set in add-on config."

        try:
            import dashscope
        except Exception:
            return None, "Module 'dashscope' is not installed in Anki's environment."

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


class OpenAITTSProvider(TTSProvider):
    """OpenAI TTS provider."""

    def synthesize(self, text: str, cfg: dict, on_download_progress: Optional[Callable[[int], None]] = None) -> Tuple[Optional[bytes], Optional[str]]:
        """Synthesize text to audio using OpenAI TTS API.

        Args:
            text: Text to synthesize
            cfg: Configuration dictionary containing TTS settings
            on_download_progress: Optional callback for download progress (0-100)

        Returns:
            Tuple of (audio_bytes, error_message). If successful, audio_bytes is bytes and error is None.
            If failed, audio_bytes is None and error is a string describing the error.
        """
        tts = cfg.get("tts") or {}
        api_key = tts.get("api_key") or ""
        model = tts.get("model") or "tts-1"
        voice = tts.get("voice") or "alloy"
        speed = tts.get("speed") or 1.0

        if not api_key:
            return None, "API key (tts.api_key) is not set in add-on config."

        try:
            from openai import OpenAI
        except Exception:
            return None, "Module 'openai' is not installed in Anki's environment."

        try:
            client = OpenAI(api_key=api_key)

            # OpenAI TTS API returns audio data directly
            response = client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                speed=speed,
                response_format="mp3"
            )

            # Read the response content
            audio_bytes = response.content

            # Simulate progress since OpenAI returns data immediately
            if on_download_progress:
                on_download_progress(100)

            return audio_bytes, None

        except Exception as e:
            return None, f"OpenAI error: {e}"


def get_tts_provider(cfg: dict) -> TTSProvider:
    """Get the appropriate TTS provider based on configuration.

    Args:
        cfg: Configuration dictionary

    Returns:
        TTSProvider instance
    """
    tts = cfg.get("tts") or {}
    provider = tts.get("provider") or "dashscope"

    if provider == "openai":
        return OpenAITTSProvider()
    else:
        return QwenTTSProvider()


def synthesize_tts_bytes(text: str, cfg: dict, on_download_progress: Optional[Callable[[int], None]] = None) -> Tuple[Optional[bytes], Optional[str]]:
    """Synthesize text to audio using the configured TTS provider.

    Args:
        text: Text to synthesize
        cfg: Configuration dictionary containing TTS settings
        on_download_progress: Optional callback for download progress (0-100)

    Returns:
        Tuple of (audio_bytes, error_message). If successful, audio_bytes is bytes and error is None.
        If failed, audio_bytes is None and error is a string describing the error.
    """
    provider = get_tts_provider(cfg)
    return provider.synthesize(text, cfg, on_download_progress)
