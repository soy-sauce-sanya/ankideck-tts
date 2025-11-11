# -*- coding: utf-8 -*-
"""Configuration management for AnkiDeck TTS addon."""

from __future__ import annotations
from aqt import mw

DEFAULT_CONFIG = {
    "tts": {
        "provider": "dashscope",  # "dashscope" or "openai"
        "api_key": "",
        "model": "qwen3-tts-flash",  # For OpenAI use "tts-1" or "tts-1-hd"
        "voice": "Ethan",  # For OpenAI use "alloy", "echo", "fable", "onyx", "nova", "shimmer"
        "language_type": "Chinese",  # Only used by DashScope/Qwen
        "speed": 1.0,  # Only used by OpenAI (0.25 to 4.0)
        "ext": "wav"  # For OpenAI use "mp3"
    },
    "write_mode": "append",
    "append_separator": "<br>",
    "filename_template": "tts_{nid}_{field}.{ext}",
    "batch": {
        "skip_if_source_empty": True,
        "skip_if_target_has_sound": True,
        "overwrite": False
    }
}


def get_config():
    """Get merged configuration from addon config and defaults."""
    cfg = mw.addonManager.getConfig(__name__) or {}
    merged = dict(DEFAULT_CONFIG)
    merged_tts = dict(DEFAULT_CONFIG.get("tts", {}))
    merged_tts.update((cfg.get("tts") or {}))
    merged.update(cfg)
    merged["tts"] = merged_tts
    merged_batch = dict(DEFAULT_CONFIG.get("batch", {}))
    merged_batch.update((cfg.get("batch") or {}))
    merged["batch"] = merged_batch
    return merged
