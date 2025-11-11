# -*- coding: utf-8 -*-
"""Utility functions for parsing and managing voice/language options."""

from __future__ import annotations
from typing import List, Tuple, Dict
from pathlib import Path
import re


def parse_voices_file(file_path: str) -> Tuple[Dict[str, List[Dict[str, str]]], List[str]]:
    """Parse voices.txt to extract available voices and languages.

    Args:
        file_path: Path to the voices.txt file

    Returns:
        Tuple of (voices_dict, languages_list) where:
        - voices_dict is a dict mapping provider names to lists of voice dicts
        - languages_list is a list of language strings
    """
    voices_by_provider = {}
    languages = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        in_voices = False
        in_languages = False
        current_provider = None

        for line in lines:
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Check for section markers
            # Match: # voices: or # voices (ProviderName):
            voices_match = re.match(r'#\s*voices\s*(?:\(([^)]+)\))?:', line, re.IGNORECASE)
            if voices_match:
                in_voices = True
                in_languages = False
                # Extract provider name from parentheses, or default to "dashscope"
                provider_text = voices_match.group(1)
                if provider_text:
                    # Normalize provider name (e.g., "DashScope/Qwen" -> "dashscope", "OpenAI" -> "openai")
                    provider_lower = provider_text.lower()
                    if 'openai' in provider_lower:
                        current_provider = 'openai'
                    elif 'dashscope' in provider_lower or 'qwen' in provider_lower:
                        current_provider = 'dashscope'
                    else:
                        current_provider = 'dashscope'
                else:
                    current_provider = 'dashscope'

                if current_provider not in voices_by_provider:
                    voices_by_provider[current_provider] = []
                continue

            if line.startswith('# languages:'):
                in_voices = False
                in_languages = True
                continue

            # Skip other comment lines without content
            if line.startswith('#') and '/' not in line and '、' not in line:
                continue

            # Parse voices (format: # 芊悦 / Cherry or # Alloy / alloy)
            if in_voices and line.startswith('#') and current_provider:
                parts = line[1:].strip().split('/')
                if len(parts) == 2:
                    chinese_name = parts[0].strip()
                    english_name = parts[1].strip()
                    voices_by_provider[current_provider].append({
                        'chinese': chinese_name,
                        'english': english_name
                    })

            # Parse languages (format: # 中文、英语、法语...)
            elif in_languages and line.startswith('#'):
                langs = line[1:].strip().split('、')
                languages.extend([lang.strip() for lang in langs if lang.strip()])

    except Exception as e:
        # Return empty dicts/lists on error
        print(f"Error parsing voices file: {e}")
        return {}, []

    return voices_by_provider, languages


def get_voice_display_name(voice: Dict[str, str]) -> str:
    """Get display name for a voice combining Chinese and English names.

    Args:
        voice: Dictionary with 'chinese' and 'english' keys

    Returns:
        Display string in format "Chinese (English)"
    """
    return f"{voice['chinese']} ({voice['english']})"


def get_voices_and_languages(provider: str = None) -> Tuple[List[Dict[str, str]], List[str]]:
    """Get available voices and languages from the voices.txt file.

    Args:
        provider: Optional provider name to filter voices (e.g., "dashscope", "openai")
                 If None, returns all voices from all providers.

    Returns:
        Tuple of (voices_list, languages_list)
    """
    # Get the addon directory
    addon_dir = Path(__file__).resolve().parent
    voices_file = addon_dir / "voices.txt"

    if not voices_file.exists():
        return [], []

    voices_by_provider, languages = parse_voices_file(str(voices_file))

    # If provider is specified, return only voices for that provider
    if provider:
        voices = voices_by_provider.get(provider.lower(), [])
    else:
        # Return all voices from all providers
        voices = []
        for provider_voices in voices_by_provider.values():
            voices.extend(provider_voices)

    return voices, languages


def get_all_voices_by_provider() -> Dict[str, List[Dict[str, str]]]:
    """Get all voices organized by provider.

    Returns:
        Dictionary mapping provider names to lists of voice dicts
    """
    addon_dir = Path(__file__).resolve().parent
    voices_file = addon_dir / "voices.txt"

    if not voices_file.exists():
        return {}

    voices_by_provider, _ = parse_voices_file(str(voices_file))
    return voices_by_provider


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
