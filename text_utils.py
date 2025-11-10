# -*- coding: utf-8 -*-
"""Text processing utilities for AnkiDeck TTS addon."""

from __future__ import annotations
import re
import html


def strip_html(text: str) -> str:
    """Remove HTML tags from text and unescape HTML entities.

    Args:
        text: Text potentially containing HTML

    Returns:
        Plain text with HTML stripped and entities unescaped
    """
    if not text:
        return ""
    s = re.sub(r"<[^>]+>", "", text)
    return html.unescape(s)


def safe_filename_from_text(text: str, ext: str) -> str:
    """Generate a safe filename from text.

    Args:
        text: Source text
        ext: File extension (without dot)

    Returns:
        Safe filename with extension
    """
    base = (text or "")[:20]
    base = re.sub(r'[<>:\"/\\\\|?*]', '', base).strip() or "audio"
    return f"{base}.{ext}"


def render_sound_tag(fname: str) -> str:
    """Render Anki sound tag.

    Args:
        fname: Audio filename

    Returns:
        Anki sound tag in format [sound:filename]
    """
    return f"[sound:{fname}]"
