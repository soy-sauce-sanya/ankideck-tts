# -*- coding: utf-8 -*-
"""Fetch current TTS model and voice catalogs from provider APIs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import json
import urllib.error
import urllib.parse
import urllib.request


Catalog = Dict[str, List[Any]]


def _get_json(url: str, headers: Optional[Dict[str, str]] = None) -> Tuple[Optional[Any], Optional[str]]:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except Exception as exc:
        return None, str(exc)


def _model_ids(payload: Any, key: str = "data") -> List[str]:
    items = payload.get(key, []) if isinstance(payload, dict) else []
    return [str(item.get("id", "")).strip() for item in items if isinstance(item, dict) and item.get("id")]


def _fetch_openai(api_key: str) -> Tuple[Optional[Catalog], Optional[str]]:
    payload, error = _get_json(
        "https://api.openai.com/v1/models",
        {"Authorization": f"Bearer {api_key}"},
    )
    if error:
        return None, error
    models = [model for model in _model_ids(payload) if model.startswith("tts-") or "-tts" in model]
    return {"models": sorted(set(models)), "voices": []}, None


def _fetch_gemini(api_key: str) -> Tuple[Optional[Catalog], Optional[str]]:
    models: List[str] = []
    page_token = ""
    for _ in range(10):
        query = {"key": api_key, "pageSize": "1000"}
        if page_token:
            query["pageToken"] = page_token
        payload, error = _get_json(
            "https://generativelanguage.googleapis.com/v1beta/models?" + urllib.parse.urlencode(query)
        )
        if error:
            return None, error
        if not isinstance(payload, dict):
            return None, "Invalid models response"
        for item in payload.get("models", []):
            if not isinstance(item, dict):
                continue
            model = str(item.get("name", "")).removeprefix("models/").strip()
            if "tts" in model.lower():
                models.append(model)
        page_token = str(payload.get("nextPageToken") or "")
        if not page_token:
            break
    return {"models": sorted(set(models)), "voices": []}, None


def _fetch_elevenlabs(api_key: str) -> Tuple[Optional[Catalog], Optional[str]]:
    headers = {"xi-api-key": api_key}
    model_payload, error = _get_json("https://api.elevenlabs.io/v1/models", headers)
    if error:
        return None, error
    models = []
    if isinstance(model_payload, list):
        models = [
            str(item.get("model_id", "")).strip()
            for item in model_payload
            if isinstance(item, dict) and item.get("model_id") and item.get("can_do_text_to_speech", True)
        ]

    voices: List[Dict[str, str]] = []
    page_token = ""
    for _ in range(20):
        query = {"page_size": "100"}
        if page_token:
            query["next_page_token"] = page_token
        voice_payload, error = _get_json(
            "https://api.elevenlabs.io/v2/voices?" + urllib.parse.urlencode(query),
            headers,
        )
        if error:
            return None, error
        if not isinstance(voice_payload, dict):
            return None, "Invalid voices response"
        for item in voice_payload.get("voices", []):
            if not isinstance(item, dict) or not item.get("voice_id"):
                continue
            voices.append({
                "chinese": str(item.get("name") or item["voice_id"]),
                "english": str(item["voice_id"]),
            })
        if not voice_payload.get("has_more"):
            break
        page_token = str(voice_payload.get("next_page_token") or "")
        if not page_token:
            break

    return {"models": sorted(set(models)), "voices": voices}, None


def fetch_provider_catalog(provider: str, api_key: str) -> Tuple[Optional[Catalog], Optional[str]]:
    """Fetch a provider catalog. DashScope currently uses the bundled catalog."""
    provider = (provider or "").strip().lower()
    api_key = (api_key or "").strip()
    if provider == "dashscope":
        return None, "DashScope system catalog is bundled with the add-on"
    if not api_key:
        return None, "API key is required"
    if provider == "openai":
        return _fetch_openai(api_key)
    if provider == "elevenlabs":
        return _fetch_elevenlabs(api_key)
    if provider == "gemini":
        return _fetch_gemini(api_key)
    return None, f"Unsupported provider: {provider}"
