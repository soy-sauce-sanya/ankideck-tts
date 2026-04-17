# -*- coding: utf-8 -*-
"""Configuration management for AnkiDeck TTS addon."""

from __future__ import annotations
from aqt import mw

DEFAULT_CONFIG = {
    "tts": {
        "provider": "dashscope",
        "api_key": "",
        "api_keys": {
            "dashscope": "",
            "openai": "",
            "elevenlabs": "",
            "gemini": ""
        },
        "model": "qwen3-tts-flash",
        "voice": "Ethan",
        "language_type": "Chinese",
        "ext": "wav",
        "models": {
            "dashscope": "qwen3-tts-flash",
            "openai": "gpt-4o-mini-tts",
            "elevenlabs": "eleven_multilingual_v2",
            "gemini": "gemini-2.5-flash-preview-tts"
        },
        "voices": {
            "dashscope": "Ethan",
            "openai": "alloy",
            "elevenlabs": "21m00Tcm4TlvDq8ikWAM",
            "gemini": "Kore"
        },
        "exts": {
            "dashscope": "wav",
            "openai": "mp3",
            "elevenlabs": "mp3",
            "gemini": "wav"
        }
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


def _addon_config_key() -> str:
    """Resolve the add-on config key shared by all submodules."""
    package_root = (__package__ or "").split(".")[0]
    if package_root:
        return package_root
    return __name__.split(".")[0]


def _read_config_by_key(key: str) -> dict:
    """Safely read config by key, returning a dict."""
    try:
        cfg = mw.addonManager.getConfig(key) or {}
    except Exception:
        cfg = {}
    return cfg if isinstance(cfg, dict) else {}


def _merge_shallow_dicts(base: dict, incoming: dict) -> dict:
    """Merge dicts with one-level nested dict support."""
    merged = dict(base or {})
    for key, value in (incoming or {}).items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            nested = dict(merged[key])
            nested.update(value)
            merged[key] = nested
        else:
            merged[key] = value
    return merged


def get_raw_config() -> dict:
    """Get user config, including legacy-key fallback for older releases."""
    primary_key = _addon_config_key()
    cfg = _read_config_by_key(primary_key)

    legacy_keys = []
    for key in (__name__, f"{primary_key}.dialog", f"{primary_key}.config"):
        if key and key != primary_key:
            legacy_keys.append(key)

    for legacy_key in legacy_keys:
        legacy_cfg = _read_config_by_key(legacy_key)
        if legacy_cfg:
            cfg = _merge_shallow_dicts(legacy_cfg, cfg)

    return cfg


def write_raw_config(cfg: dict) -> None:
    """Persist config using the canonical add-on key."""
    mw.addonManager.writeConfig(_addon_config_key(), cfg if isinstance(cfg, dict) else {})


def get_config():
    """Get merged configuration from addon config and defaults."""
    cfg = get_raw_config()
    merged = dict(DEFAULT_CONFIG)

    user_tts = cfg.get("tts") if isinstance(cfg.get("tts"), dict) else {}
    merged_tts = dict(DEFAULT_CONFIG.get("tts", {}))
    for key, value in user_tts.items():
        if key in ("api_keys", "models", "voices", "exts"):
            base_map = DEFAULT_CONFIG.get("tts", {}).get(key, {})
            merged_map = dict(base_map) if isinstance(base_map, dict) else {}
            if isinstance(value, dict):
                merged_map.update(value)
            merged_tts[key] = merged_map
        else:
            merged_tts[key] = value

    merged.update(cfg)
    merged["tts"] = merged_tts
    merged_batch = dict(DEFAULT_CONFIG.get("batch", {}))
    merged_batch.update((cfg.get("batch") or {}))
    merged["batch"] = merged_batch
    return merged
