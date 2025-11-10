# -*- coding: utf-8 -*-
"""Media and note update utilities for AnkiDeck TTS addon."""

from __future__ import annotations
import os
import tempfile
from typing import Optional

from aqt import mw


def add_media_bytes(preferred_name: str, data: bytes) -> Optional[str]:
    """Add media file to Anki's media collection from bytes.

    Args:
        preferred_name: Preferred filename for the media file
        data: Audio data as bytes

    Returns:
        The actual filename used by Anki, or None if failed
    """
    try:
        return mw.col.media.write_data(preferred_name, data)
    except Exception:
        tmp = tempfile.NamedTemporaryFile(delete=False)
        try:
            tmp.write(data)
            tmp.flush()
            tmp.close()
            try:
                return mw.col.media.add_file(tmp.name)
            except Exception:
                return None
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass


def update_note(note):
    """Update a note in the collection, compatible with different Anki versions.

    Args:
        note: The note to update
    """
    try:
        mw.col.update_note(note)
    except Exception:
        try:
            note.flush()
        except Exception:
            pass
