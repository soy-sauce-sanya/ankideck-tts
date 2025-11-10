# -*- coding: utf-8 -*-
"""Anki collection and note utilities for AnkiDeck TTS addon."""

from __future__ import annotations
from typing import Optional, List, Tuple

from aqt import mw, dialogs


def all_deck_names_and_ids() -> List[Tuple[str, int]]:
    """Get all deck names and IDs, sorted by name."""
    dman = mw.col.decks
    try:
        items = list(dman.all_names_and_ids())
        items.sort(key=lambda x: x[0].lower())
        return items
    except Exception:
        try:
            items = []
            for d in dman.all():
                items.append((d.get("name"), d.get("id")))
            items.sort(key=lambda x: (x[0] or "").lower())
            return items
        except Exception:
            return []


def all_model_names_and_ids() -> List[Tuple[str, int]]:
    """Get all note type (model) names and IDs."""
    mman = mw.col.models
    try:
        return [(m["name"], m["id"]) for m in mman.all()]
    except Exception:
        try:
            return list(mman.all_names_and_ids())
        except Exception:
            return []


def model_by_id_or_name(model_id_or_name):
    """Get model by ID or name, compatible with different Anki versions."""
    mman = mw.col.models
    try:
        m = mman.get(model_id_or_name)
        if m:
            return m
    except Exception:
        pass
    try:
        return mman.byName(model_id_or_name)
    except Exception:
        return None


def field_names_for_model(model) -> List[str]:
    """Get field names from a model, compatible with different Anki versions."""
    try:
        flds = model.get("flds", [])
        return [f.get("name", "") for f in flds if isinstance(f, dict)]
    except Exception:
        try:
            return [f.name for f in model.fields]
        except Exception:
            return []


def selected_note_ids_in_browser() -> Optional[List[int]]:
    """Get selected note IDs from the Browser dialog."""
    try:
        bdlg = dialogs._dialogs.get("Browser")
        if bdlg and bdlg[1]:
            br = bdlg[1]
            sel = br.selectedNotes()
            if sel:
                return sel
    except Exception:
        pass
    return None


def current_reviewer_note_id() -> Optional[int]:
    """Get the note ID of the current card in the reviewer."""
    try:
        c = mw.reviewer.card
        if c:
            return c.note().id
    except Exception:
        pass
    return None
