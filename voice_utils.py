# -*- coding: utf-8 -*-
"""Utility functions for parsing and managing voice/language options."""

from __future__ import annotations
from typing import List, Tuple, Dict
from pathlib import Path


def parse_voices_file(file_path: str) -> Tuple[List[Dict[str, str]], List[str]]:
    """Parse voices.txt to extract available voices and languages.

    Args:
        file_path: Path to the voices.txt file

    Returns:
        Tuple of (voices_list, languages_list) where:
        - voices_list is a list of dicts with 'chinese' and 'english' keys
        - languages_list is a list of language strings
    """
    voices = []
    languages = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        in_voices = False
        in_languages = False

        for line in lines:
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Check for section markers
            if line.startswith('# voices:'):
                in_voices = True
                in_languages = False
                continue
            elif line.startswith('# languages:'):
                in_voices = False
                in_languages = True
                continue

            # Skip other comment lines without content
            if line.startswith('#') and '/' not in line and '、' not in line:
                continue

            # Parse voices (format: # 芊悦 / Cherry)
            if in_voices and line.startswith('#'):
                parts = line[1:].strip().split('/')
                if len(parts) == 2:
                    chinese_name = parts[0].strip()
                    english_name = parts[1].strip()
                    voices.append({
                        'chinese': chinese_name,
                        'english': english_name
                    })

            # Parse languages (format: # 中文、英语、法语...)
            elif in_languages and line.startswith('#'):
                langs = line[1:].strip().split('、')
                languages.extend([lang.strip() for lang in langs if lang.strip()])

    except Exception as e:
        # Return empty lists on error
        print(f"Error parsing voices file: {e}")
        return [], []

    return voices, languages


def get_voice_display_name(voice: Dict[str, str]) -> str:
    """Get display name for a voice combining Chinese and English names.

    Args:
        voice: Dictionary with 'chinese' and 'english' keys

    Returns:
        Display string in format "Chinese (English)"
    """
    return f"{voice['chinese']} ({voice['english']})"


OPENAI_VOICES = [
    {"chinese": "Alloy", "english": "alloy"},
    {"chinese": "Ash", "english": "ash"},
    {"chinese": "Ballad", "english": "ballad"},
    {"chinese": "Coral", "english": "coral"},
    {"chinese": "Echo", "english": "echo"},
    {"chinese": "Fable", "english": "fable"},
    {"chinese": "Nova", "english": "nova"},
    {"chinese": "Onyx", "english": "onyx"},
    {"chinese": "Sage", "english": "sage"},
    {"chinese": "Shimmer", "english": "shimmer"},
    {"chinese": "Verse", "english": "verse"},
    {"chinese": "Marin", "english": "marin"},
    {"chinese": "Cedar", "english": "cedar"},
]

ELEVENLABS_VOICES = [
    {"chinese": "Rachel", "english": "21m00Tcm4TlvDq8ikWAM"},
    {"chinese": "Domi", "english": "AZnzlk1XvdvUeBnXmlld"},
    {"chinese": "Bella", "english": "EXAVITQu4vr4xnSDxMaL"},
    {"chinese": "Antoni", "english": "ErXwobaYiN019PkySvjV"},
    {"chinese": "Elli", "english": "MF3mGyEYCl7XYWbV9V6O"},
    {"chinese": "Josh", "english": "TxGEqnHWrfWFTfGW9XjX"},
    {"chinese": "Adam", "english": "pNInz6obpgDQGcFmaJgB"},
    {"chinese": "Sam", "english": "yoZ06aMxZJJ28mfd3POQ"},
]

GEMINI_VOICES = [
    {"chinese": "Zephyr - Bright", "english": "Zephyr"},
    {"chinese": "Puck - Upbeat", "english": "Puck"},
    {"chinese": "Charon - Informative", "english": "Charon"},
    {"chinese": "Kore - Firm", "english": "Kore"},
    {"chinese": "Fenrir - Excitable", "english": "Fenrir"},
    {"chinese": "Leda - Youthful", "english": "Leda"},
    {"chinese": "Orus - Firm", "english": "Orus"},
    {"chinese": "Aoede - Breezy", "english": "Aoede"},
    {"chinese": "Callirrhoe - Easy-going", "english": "Callirrhoe"},
    {"chinese": "Autonoe - Bright", "english": "Autonoe"},
    {"chinese": "Enceladus - Breathy", "english": "Enceladus"},
    {"chinese": "Iapetus - Clear", "english": "Iapetus"},
    {"chinese": "Umbriel - Easy-going", "english": "Umbriel"},
    {"chinese": "Algieba - Smooth", "english": "Algieba"},
    {"chinese": "Despina - Smooth", "english": "Despina"},
    {"chinese": "Erinome - Clear", "english": "Erinome"},
    {"chinese": "Algenib - Gravelly", "english": "Algenib"},
    {"chinese": "Rasalgethi - Informative", "english": "Rasalgethi"},
    {"chinese": "Laomedeia - Upbeat", "english": "Laomedeia"},
    {"chinese": "Achernar - Soft", "english": "Achernar"},
    {"chinese": "Alnilam - Firm", "english": "Alnilam"},
    {"chinese": "Schedar - Even", "english": "Schedar"},
    {"chinese": "Gacrux - Mature", "english": "Gacrux"},
    {"chinese": "Pulcherrima - Forward", "english": "Pulcherrima"},
    {"chinese": "Achird - Friendly", "english": "Achird"},
    {"chinese": "Zubenelgenubi - Casual", "english": "Zubenelgenubi"},
    {"chinese": "Vindemiatrix - Gentle", "english": "Vindemiatrix"},
    {"chinese": "Sadachbia - Lively", "english": "Sadachbia"},
    {"chinese": "Sadaltager - Knowledgeable", "english": "Sadaltager"},
    {"chinese": "Sulafat - Warm", "english": "Sulafat"},
]

PROVIDER_MODELS = {
    "dashscope": ["qwen3-tts-flash", "qwen3-tts"],
    "openai": ["gpt-4o-mini-tts", "tts-1", "tts-1-hd"],
    "elevenlabs": ["eleven_multilingual_v2", "eleven_turbo_v2_5", "eleven_flash_v2_5", "eleven_ttv_v3", "eleven_v3"],
    "gemini": ["gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts"],
}


def get_voices_and_languages() -> Tuple[List[Dict[str, str]], List[str]]:
    """Get available voices and languages from the voices.txt file.

    Returns:
        Tuple of (voices_list, languages_list)
    """
    # Get the addon directory
    addon_dir = Path(__file__).resolve().parent
    voices_file = addon_dir / "voices.txt"

    if not voices_file.exists():
        return [], []

    return parse_voices_file(str(voices_file))


def get_provider_voices_and_languages(provider: str) -> Tuple[List[Dict[str, str]], List[str]]:
    """Get available voices and languages for a specific provider.

    Args:
        provider: TTS provider identifier (e.g., "dashscope", "openai")

    Returns:
        Tuple of (voices_list, languages_list)
    """
    provider = (provider or "").lower()
    if provider == "openai":
        return OPENAI_VOICES, []
    elif provider == "elevenlabs":
        return ELEVENLABS_VOICES, []
    elif provider == "gemini":
        return GEMINI_VOICES, []
    return get_voices_and_languages()


def get_provider_models(provider: str) -> List[str]:
    """Get available models for a specific provider.

    Args:
        provider: TTS provider identifier (e.g., "dashscope", "openai")

    Returns:
        List of model identifiers for the provider.
    """
    return PROVIDER_MODELS.get((provider or "").lower(), [])


def language_display_to_api_format(display_name: str) -> str:
    """Convert display language name to API format.

    Args:
        display_name: Language name in Chinese (e.g., "中文", "英语")

    Returns:
        API format language name (e.g., "Chinese", "English")
    """
    # Mapping from Chinese display names to API format
    mapping = {
        "中文": "Chinese",
        "英语": "English",
        "法语": "French",
        "德语": "German",
        "俄语": "Russian",
        "意大利语": "Italian",
        "西班牙语": "Spanish",
        "葡萄牙语": "Portuguese",
        "日语": "Japanese",
        "韩语": "Korean"
    }
    return mapping.get(display_name, display_name)


def api_format_to_language_display(api_name: str) -> str:
    """Convert API format language name to display format.

    Args:
        api_name: API format language name (e.g., "Chinese", "English")

    Returns:
        Display language name in Chinese (e.g., "中文", "英语")
    """
    # Reverse mapping from API format to Chinese display names
    mapping = {
        "Chinese": "中文",
        "English": "英语",
        "French": "法语",
        "German": "德语",
        "Russian": "俄语",
        "Italian": "意大利语",
        "Spanish": "西班牙语",
        "Portuguese": "葡萄牙语",
        "Japanese": "日语",
        "Korean": "韩语"
    }
    return mapping.get(api_name, api_name)
