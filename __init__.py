# -*- coding: utf-8 -*-
"""AnkiDeck TTS - Text-to-Speech addon for Anki using DashScope API."""

from __future__ import annotations

from pathlib import Path
import sys

# Add vendor_build to path for bundled dependencies
vendor = Path(__file__).resolve().parent / "vendor_build"
if str(vendor) not in sys.path:
    sys.path.insert(0, str(vendor))

from aqt import mw, gui_hooks
from aqt.qt import QAction, QKeySequence, qconnect

from .dialog import open_tts_dialog

# Constants
ADDON_TITLE = "AnkiDeck TTS"
TOOLBAR_LINK_LABEL = "TTS"
TOOLBAR_LINK_TOOLTIP = "Open AnkiDeck TTS"


def _add_top_toolbar_link(links, toolbar, *args, **kwargs):
    """Add TTS button to the top toolbar."""
    link = toolbar.create_link(TOOLBAR_LINK_LABEL, TOOLBAR_LINK_TOOLTIP, open_tts_dialog)
    links.append(link)


def _add_menu_action() -> None:
    """Add TTS menu item to Tools menu with keyboard shortcut."""
    action = QAction(f"{ADDON_TITLE}: Open", mw)
    action.setShortcut(QKeySequence("Ctrl+Alt+T"))
    qconnect(action.triggered, open_tts_dialog)
    mw.form.menuTools.addAction(action)


def _on_main_window_did_init(_mw=None, *args, **kwargs):
    """Initialize addon after main window is ready."""
    _add_menu_action()


# Register hooks
gui_hooks.top_toolbar_did_init_links.append(_add_top_toolbar_link)
gui_hooks.main_window_did_init.append(_on_main_window_did_init)
