# -*- coding: utf-8 -*-
"""Main dialog UI for AnkiDeck TTS addon."""

from __future__ import annotations
from typing import Optional, List, Dict
import time

from anki.collection import SearchNode
from aqt import mw, dialogs
from aqt.qt import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QDockWidget,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QCheckBox, QProgressBar, QLineEdit,
    QSizePolicy, Qt, qconnect
)
from aqt.utils import showInfo

from .config import get_config, get_raw_config, write_raw_config
from .anki_helpers import (
    all_deck_names_and_ids,
    all_model_names_and_ids,
    model_by_id_or_name,
    field_names_for_model,
    selected_note_ids_in_browser,
    current_reviewer_note_id
)
from .media_utils import add_media_bytes, update_note
from .provider_catalog import fetch_provider_catalog
from .tts_provider import synthesize_tts_bytes
from .text_utils import strip_html, safe_filename_from_text, render_sound_tag
from .voice_utils import (
    get_voice_display_name,
    language_display_to_api_format,
    get_provider_voices_and_languages,
    get_provider_models
)


# Qt5/Qt6 compatibility for header enums
try:
    RESIZE_TO_CONTENTS = QHeaderView.ResizeMode.ResizeToContents  # PyQt6
    RESIZE_STRETCH = QHeaderView.ResizeMode.Stretch
except Exception:
    RESIZE_TO_CONTENTS = QHeaderView.ResizeToContents  # PyQt5
    RESIZE_STRETCH = QHeaderView.Stretch


ADDON_TITLE = "AnkiDeck TTS"
CATALOG_CACHE_SECONDS = 24 * 60 * 60


class TTSPanel(QWidget):
    """Dockable panel for batch TTS processing inside the Browser."""

    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.browser = parent

        self.deck_combo = QComboBox(self)
        self.model_combo = QComboBox(self)
        self.source_field_combo = QComboBox(self)
        self.source_field_combo.setToolTip("Text sent to the TTS provider")
        self.target_field_combo = QComboBox(self)
        self.target_field_combo.setToolTip("Field that receives generated audio")
        self.provider_combo = QComboBox(self)
        self.api_key_edit = QLineEdit(self)
        self.api_key_toggle_btn = QPushButton("👁", self)
        self.api_key_toggle_btn.setFixedWidth(32)
        self.api_key_toggle_btn.setCheckable(True)
        self.api_key_toggle_btn.setToolTip("Show/hide API key")
        self.refresh_catalog_btn = QPushButton("↻", self)
        self.refresh_catalog_btn.setFixedWidth(32)
        self.refresh_catalog_btn.setToolTip("Refresh models and voices from the provider")
        self.tts_model_combo = QComboBox(self)
        self.tts_model_combo.setEditable(True)
        self.tts_model_combo.setToolTip("Select a model or enter its ID")
        self.voice_combo = QComboBox(self)
        self.voice_combo.setEditable(True)
        self.voice_combo.setToolTip("Select a voice or enter its ID")
        self.language_combo = QComboBox(self)
        self.catalog_status_label = QLabel("", self)

        cfg = get_config()
        self.overwrite_chk = QCheckBox("Replace existing audio", self)
        self.overwrite_chk.setToolTip("Replace existing content in the target field")
        self.overwrite_chk.setChecked(bool(cfg.get("batch", {}).get("overwrite", False)))

        try:
            expanding = QSizePolicy.Policy.Expanding
            fixed = QSizePolicy.Policy.Fixed
            compact_combo = QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        except Exception:
            expanding = QSizePolicy.Expanding
            fixed = QSizePolicy.Fixed
            compact_combo = QComboBox.AdjustToMinimumContentsLengthWithIcon
        for combo in (
            self.deck_combo,
            self.model_combo,
            self.source_field_combo,
            self.target_field_combo,
            self.provider_combo,
            self.tts_model_combo,
            self.voice_combo,
            self.language_combo,
        ):
            combo.setSizeAdjustPolicy(compact_combo)
            combo.setMinimumContentsLength(8)
            combo.setMinimumWidth(0)
            combo.setSizePolicy(expanding, fixed)
        self.api_key_edit.setMinimumWidth(0)
        self.api_key_edit.setSizePolicy(expanding, fixed)

        # Buttons
        self.process_btn = QPushButton("Process", self)
        self.clear_btn = QPushButton("Clear", self)
        self.close_btn = QPushButton("Hide TTS", self)

        # Queue table: Text | State | Progress
        self.table = QTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Text", "State", "Progress"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, RESIZE_TO_CONTENTS)
        header.setSectionResizeMode(1, RESIZE_TO_CONTENTS)
        header.setSectionResizeMode(2, RESIZE_STRETCH)

        # Overall progress
        self.batch_bar = QProgressBar(self)
        self.batch_bar.setValue(0)
        self.batch_bar.setFormat("%p% processed")

        # Compact two-column settings layout for the Browser dock.
        settings = QGridLayout()
        settings.addWidget(QLabel("Deck:"), 0, 0)
        settings.addWidget(self.deck_combo, 0, 1)
        settings.addWidget(QLabel("Note type:"), 0, 2)
        settings.addWidget(self.model_combo, 0, 3)
        settings.addWidget(QLabel("Source field:"), 1, 0)
        settings.addWidget(self.source_field_combo, 1, 1)
        settings.addWidget(QLabel("Target field:"), 1, 2)
        settings.addWidget(self.target_field_combo, 1, 3)
        settings.addWidget(QLabel("Provider:"), 2, 0)

        provider_widget = QWidget(self)
        provider_layout = QHBoxLayout()
        provider_layout.setContentsMargins(0, 0, 0, 0)
        provider_layout.addWidget(self.provider_combo)
        provider_layout.addWidget(self.refresh_catalog_btn)
        provider_widget.setLayout(provider_layout)
        provider_widget.setMinimumWidth(0)
        provider_widget.setSizePolicy(expanding, fixed)
        settings.addWidget(provider_widget, 2, 1)

        api_key_widget = QWidget(self)
        api_key_layout = QHBoxLayout()
        api_key_layout.setContentsMargins(0, 0, 0, 0)
        api_key_layout.addWidget(self.api_key_edit)
        api_key_layout.addWidget(self.api_key_toggle_btn)
        api_key_widget.setLayout(api_key_layout)
        api_key_widget.setMinimumWidth(0)
        api_key_widget.setSizePolicy(expanding, fixed)
        settings.addWidget(QLabel("API key:"), 2, 2)
        settings.addWidget(api_key_widget, 2, 3)
        settings.addWidget(QLabel("TTS model:"), 3, 0)
        settings.addWidget(self.tts_model_combo, 3, 1)
        settings.addWidget(QLabel("Voice:"), 3, 2)
        settings.addWidget(self.voice_combo, 3, 3)
        settings.addWidget(QLabel("Language:"), 4, 0)
        settings.addWidget(self.language_combo, 4, 1)
        settings.addWidget(QLabel("Overwrite:"), 4, 2)
        settings.addWidget(self.overwrite_chk, 4, 3)
        settings.setColumnStretch(1, 1)
        settings.setColumnStretch(3, 1)

        top = QVBoxLayout(self)
        top.addLayout(settings)

        btns = QHBoxLayout()
        btns.addWidget(self.process_btn)
        btns.addWidget(self.catalog_status_label)
        btns.addStretch(1)
        btns.addWidget(self.clear_btn)
        btns.addWidget(self.close_btn)
        top.addLayout(btns)

        top.addWidget(QLabel("Queue:"))
        top.addWidget(self.table)
        top.addWidget(self.batch_bar)

        # Signals
        qconnect(self.process_btn.clicked, self.process_notes)
        qconnect(self.clear_btn.clicked, self._clear_queue)
        qconnect(self.close_btn.clicked, self._on_close_clicked)
        qconnect(self.deck_combo.activated, self._on_deck_selected)
        qconnect(self.model_combo.currentIndexChanged, self._on_model_changed)
        qconnect(self.provider_combo.currentIndexChanged, self._on_provider_changed)
        qconnect(self.api_key_edit.editingFinished, self._on_api_key_changed)
        qconnect(self.api_key_toggle_btn.clicked, self._toggle_api_key_visibility)
        qconnect(self.refresh_catalog_btn.clicked, self._refresh_catalog)
        qconnect(self.tts_model_combo.currentIndexChanged, self._on_tts_model_changed)
        qconnect(self.voice_combo.currentIndexChanged, self._on_voice_changed)
        qconnect(self.tts_model_combo.lineEdit().editingFinished, self._on_tts_model_changed)
        qconnect(self.voice_combo.lineEdit().editingFinished, self._on_voice_changed)
        qconnect(self.language_combo.currentIndexChanged, self._on_language_changed)

        # Queue state
        self.jobs: List[Dict] = []
        self._queue_running = False
        self._catalog_refreshing = False

        # Voice/language data
        self.voices_data = []
        self.languages_data = []

        # Populate
        self._load_decks()
        self._load_models()
        self._load_providers()
        self._setup_api_key_field()
        self._load_api_key_for_provider()
        self._load_tts_models()
        self._load_voices_and_languages()
        self._select_current_deck()
        self._on_model_changed()
        self._refresh_catalog_if_stale()

    def _clear_queue(self):
        """Clear the queue table and job list."""
        self.jobs.clear()
        self.table.setRowCount(0)
        self.batch_bar.setValue(0)
        self._queue_running = False

    def _on_close_clicked(self):
        """Hide the containing Browser dock without clearing its queue."""
        parent = self.parentWidget()
        if isinstance(parent, QDockWidget):
            parent.hide()
        else:
            self.hide()

    def _cached_catalog(self, provider: str) -> dict:
        """Return a validated cached catalog entry for a provider."""
        cache = (get_config().get("tts", {}) or {}).get("catalog_cache", {})
        entry = cache.get(provider, {}) if isinstance(cache, dict) else {}
        return entry if isinstance(entry, dict) else {}

    def _set_catalog_status(self, text: str, tooltip: str = "") -> None:
        self.catalog_status_label.setText(text)
        self.catalog_status_label.setToolTip(tooltip or text)

    def _refresh_catalog_if_stale(self) -> None:
        """Refresh supported provider catalogs at most once per day."""
        provider = self.provider_combo.currentData() or "dashscope"
        if provider == "dashscope":
            self.refresh_catalog_btn.setEnabled(False)
            self._set_catalog_status("Built-in catalog")
            return

        self.refresh_catalog_btn.setEnabled(True)
        cached = self._cached_catalog(provider)
        updated_at = float(cached.get("updated_at") or 0)
        age = max(0, time.time() - updated_at) if updated_at else None
        if age is not None and age < CATALOG_CACHE_SECONDS:
            hours = int(age // 3600)
            self._set_catalog_status("Updated recently" if hours == 0 else f"Updated {hours}h ago")
            return

        api_key = self._resolve_provider_api_key(get_config().get("tts", {}), provider)
        if not api_key:
            self._set_catalog_status("Add API key to refresh")
            return
        self._refresh_catalog()

    def _refresh_catalog(self, *_args) -> None:
        """Fetch the selected provider catalog without blocking Anki."""
        if self._catalog_refreshing:
            return
        provider = self.provider_combo.currentData() or "dashscope"
        if provider == "dashscope":
            self._set_catalog_status("Built-in catalog")
            return
        api_key = self._resolve_provider_api_key(get_config().get("tts", {}), provider)
        if not api_key:
            self._set_catalog_status("Add API key to refresh")
            return

        previous = self._cached_catalog(provider)
        bundled_models = set(get_provider_models(provider))
        bundled_voices, _languages = get_provider_voices_and_languages(provider)
        bundled_voice_ids = {
            str(voice.get("english"))
            for voice in bundled_voices
            if isinstance(voice, dict) and voice.get("english")
        }
        self._catalog_refreshing = True
        self.refresh_catalog_btn.setEnabled(False)
        self._set_catalog_status("Refreshing…")

        def background():
            return fetch_provider_catalog(provider, api_key)

        def on_done(result_or_future):
            try:
                result = result_or_future.result() if hasattr(result_or_future, "result") else result_or_future
                catalog, error = result
            except Exception as exc:
                catalog, error = None, str(exc)

            self._catalog_refreshing = False
            try:
                current_provider = self.provider_combo.currentData() or "dashscope"
                self.refresh_catalog_btn.setEnabled(current_provider != "dashscope")
            except RuntimeError:
                current_provider = None
            if error or not catalog:
                if current_provider == provider:
                    fallback = "Using saved catalog" if previous else "Refresh failed"
                    self._set_catalog_status(fallback, error or "No catalog returned")
                return

            old_models = bundled_models | {
                model for model in previous.get("models", []) if isinstance(model, str)
            }
            old_voices = {
                str(voice.get("english"))
                for voice in previous.get("voices", [])
                if isinstance(voice, dict) and voice.get("english")
            } | bundled_voice_ids
            new_models = {
                model for model in catalog.get("models", []) if isinstance(model, str)
            }
            new_voices = {
                str(voice.get("english"))
                for voice in catalog.get("voices", [])
                if isinstance(voice, dict) and voice.get("english")
            }
            added = len(new_models - old_models) + len(new_voices - old_voices)

            cfg = get_raw_config()
            tts_cfg = cfg.setdefault("tts", {})
            cache = tts_cfg.setdefault("catalog_cache", {})
            cache[provider] = {
                "updated_at": time.time(),
                "models": catalog.get("models", []),
                "voices": catalog.get("voices", []),
                "new_models": sorted(new_models - old_models),
                "new_voices": sorted(new_voices - old_voices),
            }
            write_raw_config(cfg)

            if current_provider == provider:
                self._load_tts_models()
                self._load_voices_and_languages()
                self._set_catalog_status(f"{added} new items" if added else "Catalog is current")
            elif current_provider:
                self._refresh_catalog_if_stale()

        try:
            mw.taskman.run_in_background(background, on_done)
        except Exception as exc:
            self._catalog_refreshing = False
            self.refresh_catalog_btn.setEnabled(True)
            self._set_catalog_status("Refresh failed", str(exc))

    def _load_decks(self):
        """Load all decks into the deck combo box."""
        self.deck_combo.clear()
        for name, did in all_deck_names_and_ids():
            self.deck_combo.addItem(name or "(no name)", did)

    def refresh_decks(self):
        """Refresh deck list while trying to keep current selection."""
        selected_did = self.deck_combo.currentData()
        self._load_decks()

        if selected_did is not None:
            for i in range(self.deck_combo.count()):
                if self.deck_combo.itemData(i) == selected_did:
                    self.deck_combo.setCurrentIndex(i)
                    return

        self._select_current_deck()

    def _select_current_deck(self):
        """Select the currently active deck in the combo box."""
        try:
            cur = mw.col.decks.current()
            did = cur.get("id")
            if did is None:
                return
            for i in range(self.deck_combo.count()):
                if self.deck_combo.itemData(i) == did:
                    self.deck_combo.setCurrentIndex(i)
                    return
        except Exception:
            pass

    def _on_deck_selected(self, *_args):
        """Filter the containing Browser to the deck selected by the user."""
        deck_name = self.deck_combo.currentText()
        if not deck_name:
            return
        try:
            self.browser.search_for_terms(SearchNode(deck=deck_name))
        except Exception as exc:
            showInfo(f"Could not browse the selected deck: {exc}")

    def _load_models(self):
        """Load all note types into the model combo box."""
        last_model_id = get_config().get("last_note_type_id")
        self.model_combo.blockSignals(True)
        try:
            self.model_combo.clear()
            for name, mid in all_model_names_and_ids():
                self.model_combo.addItem(name, mid)
            if last_model_id is not None:
                for i in range(self.model_combo.count()):
                    if str(self.model_combo.itemData(i)) == str(last_model_id):
                        self.model_combo.setCurrentIndex(i)
                        break
        finally:
            self.model_combo.blockSignals(False)

    def _on_model_changed(self):
        """Update field combos when model selection changes."""
        self.source_field_combo.clear()
        self.target_field_combo.clear()
        model_name = self.model_combo.currentText()
        model_id = self.model_combo.currentData()
        model = model_by_id_or_name(model_id) or model_by_id_or_name(model_name)
        if not model:
            return
        cfg = get_raw_config()
        cfg["last_note_type_id"] = model_id
        write_raw_config(cfg)
        fields = field_names_for_model(model)
        for fn in fields:
            self.source_field_combo.addItem(fn)
            self.target_field_combo.addItem(fn)
        lf = [f.lower() for f in fields]

        def sel(combo, cands, default_index=0):
            for cand in cands:
                if cand.lower() in lf:
                    combo.setCurrentIndex(lf.index(cand.lower()))
                    return
            combo.setCurrentIndex(default_index)

        sel(self.source_field_combo, ["Back", "Text", "Expression", "Front"])
        sel(self.target_field_combo, ["Audio", "Pronunciation", "BackAudio", "Sound", "AudioBack"])

    def _load_voices_and_languages(self):
        """Load bundled voices plus any cached provider voices."""
        cfg = get_config()
        tts_cfg = cfg.get("tts", {})
        provider = self.provider_combo.currentData() or tts_cfg.get("provider", "dashscope")

        bundled_voices, bundled_languages = get_provider_voices_and_languages(provider)
        self.voices_data = list(bundled_voices)
        self.languages_data = list(bundled_languages)
        cached = self._cached_catalog(provider)
        new_voice_ids = set(cached.get("new_voices", []))
        known_voice_ids = {str(voice.get("english")) for voice in self.voices_data}
        for voice in cached.get("voices", []):
            if isinstance(voice, dict) and voice.get("english") and str(voice["english"]) not in known_voice_ids:
                self.voices_data.append(voice)
                known_voice_ids.add(str(voice["english"]))

        # Populate voice combo box
        self.voice_combo.blockSignals(True)
        try:
            self.voice_combo.clear()
            for voice in self.voices_data:
                display_name = get_voice_display_name(voice)
                if str(voice.get("english")) in new_voice_ids:
                    display_name += " · New"
                self.voice_combo.addItem(display_name, voice['english'])

            voices_cfg = tts_cfg.get("voices") or {}
            current_voice = voices_cfg.get(provider) or tts_cfg.get("voice", "Ethan")
            selected = False
            for i in range(self.voice_combo.count()):
                if self.voice_combo.itemData(i) == current_voice:
                    self.voice_combo.setCurrentIndex(i)
                    selected = True
                    break
            if current_voice and not selected:
                self.voice_combo.addItem(str(current_voice), str(current_voice))
                self.voice_combo.setCurrentIndex(self.voice_combo.count() - 1)
        finally:
            self.voice_combo.blockSignals(False)

        # Populate language combo box
        self.language_combo.clear()
        for lang in self.languages_data:
            self.language_combo.addItem(lang, language_display_to_api_format(lang))

        # Select current voice and language from config
        current_language_api = tts_cfg.get("language_type", "Chinese")

        # Find and select the current language
        if self.language_combo.count() == 0:
            self.language_combo.setEnabled(False)
        else:
            self.language_combo.setEnabled(True)
            for i in range(self.language_combo.count()):
                if self.language_combo.itemData(i) == current_language_api:
                    self.language_combo.setCurrentIndex(i)
                    break

    def _load_tts_models(self):
        """Load bundled models plus any cached provider models."""
        cfg = get_config()
        tts_cfg = cfg.get("tts", {})
        provider = self.provider_combo.currentData() or tts_cfg.get("provider", "dashscope")
        models = list(get_provider_models(provider))
        cached = self._cached_catalog(provider)
        new_models = set(cached.get("new_models", []))
        for model in cached.get("models", []):
            if isinstance(model, str) and model and model not in models:
                models.append(model)

        current_models = tts_cfg.get("models") or {}
        current_model = current_models.get(provider) or tts_cfg.get("model")
        self.tts_model_combo.blockSignals(True)
        try:
            self.tts_model_combo.clear()
            for model in models:
                label = f"{model} · New" if model in new_models else model
                self.tts_model_combo.addItem(label, model)
            if current_model and current_model not in models:
                self.tts_model_combo.addItem(str(current_model), str(current_model))
            for i in range(self.tts_model_combo.count()):
                if self.tts_model_combo.itemData(i) == current_model:
                    self.tts_model_combo.setCurrentIndex(i)
                    break
        finally:
            self.tts_model_combo.blockSignals(False)

    def _load_providers(self):
        """Load provider options into the combo box."""
        self.provider_combo.blockSignals(True)
        try:
            self.provider_combo.clear()
            self.provider_combo.addItem("Qwen (DashScope)", "dashscope")
            self.provider_combo.addItem("ChatGPT (OpenAI)", "openai")
            self.provider_combo.addItem("11 Labs", "elevenlabs")
            self.provider_combo.addItem("Gemini (Google AI)", "gemini")

            cfg = get_config()
            current_provider = (cfg.get("tts", {}) or {}).get("provider", "dashscope")
            for i in range(self.provider_combo.count()):
                if self.provider_combo.itemData(i) == current_provider:
                    self.provider_combo.setCurrentIndex(i)
                    break
        finally:
            self.provider_combo.blockSignals(False)

    def _setup_api_key_field(self):
        """Set API key input behavior."""
        self.api_key_edit.setClearButtonEnabled(True)
        try:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        except Exception:
            self.api_key_edit.setEchoMode(QLineEdit.Password)

    def _toggle_api_key_visibility(self):
        """Toggle API key field between visible and hidden."""
        try:
            normal = QLineEdit.EchoMode.Normal
            password = QLineEdit.EchoMode.Password
        except Exception:
            normal = QLineEdit.Normal
            password = QLineEdit.Password
        if self.api_key_edit.echoMode() == password:
            self.api_key_edit.setEchoMode(normal)
            self.api_key_toggle_btn.setText("🔒")
        else:
            self.api_key_edit.setEchoMode(password)
            self.api_key_toggle_btn.setText("👁")

    def _resolve_provider_api_key(self, cfg_tts: dict, provider: str) -> str:
        """Resolve API key for selected provider from config."""
        if not isinstance(cfg_tts, dict):
            return ""

        api_keys = cfg_tts.get("api_keys")
        if isinstance(api_keys, dict):
            provider_key = (provider or "").strip().lower()
            for key, value in api_keys.items():
                if (str(key).strip().lower() == provider_key) and isinstance(value, str) and value.strip():
                    return value.strip()

        fallback = cfg_tts.get("api_key")
        if isinstance(fallback, str):
            return fallback.strip()
        return ""

    def _load_api_key_for_provider(self):
        """Load API key for selected provider into the input field."""
        cfg = get_config()
        tts_cfg = cfg.get("tts", {})
        provider = self.provider_combo.currentData() or tts_cfg.get("provider", "dashscope")
        provider_label = self.provider_combo.currentText() or provider
        self.api_key_edit.setPlaceholderText(f"Enter {provider_label} API key")
        self.api_key_edit.setText(self._resolve_provider_api_key(tts_cfg, provider))

    def _on_provider_changed(self):
        """Handle provider selection change."""
        provider = self.provider_combo.currentData()
        if provider:
            cfg = get_raw_config()
            if "tts" not in cfg:
                cfg["tts"] = {}
            cfg["tts"]["provider"] = provider
            write_raw_config(cfg)
            self._load_api_key_for_provider()
            self._load_tts_models()
            self._load_voices_and_languages()
            self._refresh_catalog_if_stale()

    def _on_api_key_changed(self):
        """Persist API key for selected provider."""
        provider = self.provider_combo.currentData() or "dashscope"
        api_key = (self.api_key_edit.text() or "").strip()
        cfg = get_raw_config()
        tts_cfg = cfg.setdefault("tts", {})
        api_keys = tts_cfg.setdefault("api_keys", {})
        api_keys[provider] = api_key
        tts_cfg["api_key"] = api_key
        write_raw_config(cfg)
        self._refresh_catalog_if_stale()

    @staticmethod
    def _editable_combo_value(combo: QComboBox) -> str:
        """Return item data for a selection, or the manually entered text."""
        index = combo.currentIndex()
        if index >= 0 and combo.currentText() == combo.itemText(index):
            return str(combo.itemData(index) or combo.currentText()).strip()
        return combo.currentText().strip()

    def _on_tts_model_changed(self):
        """Handle TTS model selection change."""
        model = self._editable_combo_value(self.tts_model_combo)
        if model:
            cfg = get_raw_config()
            cfg.setdefault("tts", {})
            cfg["tts"]["model"] = model
            provider = self.provider_combo.currentData()
            if provider:
                models_cfg = cfg["tts"].setdefault("models", {})
                models_cfg[provider] = model
            write_raw_config(cfg)

    def _on_voice_changed(self):
        """Handle voice selection change."""
        voice_english = self._editable_combo_value(self.voice_combo)
        if voice_english:
            # Update config
            cfg = get_raw_config()
            if "tts" not in cfg:
                cfg["tts"] = {}
            cfg["tts"]["voice"] = voice_english
            provider = self.provider_combo.currentData()
            if provider:
                voices_cfg = cfg["tts"].setdefault("voices", {})
                voices_cfg[provider] = voice_english
            write_raw_config(cfg)

    def _on_language_changed(self):
        """Handle language selection change."""
        language_api = self.language_combo.currentData()
        if language_api:
            # Update config
            cfg = get_raw_config()
            if "tts" not in cfg:
                cfg["tts"] = {}
            cfg["tts"]["language_type"] = language_api
            write_raw_config(cfg)

    def _append_job_row(self, text: str, state: str) -> int:
        """Add a new job row to the table."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(text))
        self.table.setItem(row, 1, QTableWidgetItem(state))
        bar = QProgressBar(self.table)
        bar.setValue(0)
        bar.setFormat("%p%")
        self.table.setCellWidget(row, 2, bar)
        return row

    def _update_row(self, row: int, *, state: Optional[str] = None, progress: Optional[int] = None, busy: bool = False):
        """Update a job row's state and progress."""
        if state is not None:
            self.table.item(row, 1).setText(state)
        bar: QProgressBar = self.table.cellWidget(row, 2)
        if busy:
            bar.setRange(0, 0)  # indeterminate
        else:
            bar.setRange(0, 100)
        if progress is not None:
            bar.setValue(max(0, min(100, progress)))

    def _enqueue_notes(self, nids: List[int]):
        """Add notes to the processing queue."""
        src = self.source_field_combo.currentText()
        dst = self.target_field_combo.currentText()
        for nid in nids:
            try:
                note = mw.col.get_note(nid)
                text = strip_html(note.get(src, "") if hasattr(note, "get") else note[src])
            except Exception:
                text = ""
            preview = (text[:80] + "…") if len(text) > 80 else text
            row = self._append_job_row(preview or "(empty)", "waiting")
            self.jobs.append({
                "nid": nid,
                "row": row,
                "state": "waiting",
                "progress": 0,
                "text": text,
                "src": src,
                "dst": dst,
            })
        self._update_batch_bar()

    def _update_batch_bar(self):
        """Update the overall progress bar."""
        total = max(1, len(self.jobs))
        done = len([j for j in self.jobs if j["state"] in ("done", "skipped", "error")])
        self.batch_bar.setValue(int(done * 100 / total))

    def _start_queue(self):
        """Start processing the queue."""
        if not self._queue_running and self.jobs:
            self._queue_running = True
            self._process_next()

    def _process_next(self):
        """Process the next job in the queue."""
        next_job = None
        for job in self.jobs:
            if job["state"] == "waiting":
                next_job = job
                break
        if not next_job:
            self._queue_running = False
            showInfo(f"Queue finished. Total: {len(self.jobs)}")
            return
        self._process_job(next_job)

    def _process_job(self, job: Dict):
        """Process a single job."""
        cfg = get_config()
        src = job.get("src") or self.source_field_combo.currentText()
        dst = job.get("dst") or self.target_field_combo.currentText()
        overwrite = self.overwrite_chk.isChecked()

        # Read note/fields on the main thread before background synthesis.
        try:
            note = mw.col.get_note(job["nid"])
        except Exception as e:
            job["state"] = "error"
            self._update_row(job["row"], state=f"error: note load failed: {e}", busy=False, progress=0)
            self._update_batch_bar()
            mw.taskman.run_on_main(self._process_next)
            return

        try:
            text = strip_html(note[src])
        except Exception:
            text = job.get("text") or ""

        if not (text or "").strip() and bool((cfg.get("batch") or {}).get("skip_if_source_empty", True)):
            job["state"] = "skipped"
            job["progress"] = 0
            self._update_row(job["row"], state="skipped (empty)", busy=False, progress=0)
            self._update_batch_bar()
            mw.taskman.run_on_main(self._process_next)
            return

        try:
            cur_val = note[dst]
        except Exception as e:
            job["state"] = "error"
            self._update_row(job["row"], state=f"error: target field '{dst}' not found: {e}", busy=False, progress=0)
            self._update_batch_bar()
            mw.taskman.run_on_main(self._process_next)
            return

        if not overwrite and bool((cfg.get("batch") or {}).get("skip_if_target_has_sound", True)) and "[sound:" in (cur_val or ""):
            job["state"] = "skipped"
            job["progress"] = 0
            self._update_row(job["row"], state="skipped (already has sound)", busy=False, progress=0)
            self._update_batch_bar()
            mw.taskman.run_on_main(self._process_next)
            return

        job["state"] = "processing"
        self._update_row(job["row"], state="processing (generating…)", busy=True, progress=0)

        def bg():
            # Synthesize audio in background only.
            def on_dl(pct: int):
                mw.taskman.run_on_main(lambda: self._update_row(job["row"], state="processing (downloading…)", busy=False, progress=pct))

            audio_bytes, err = synthesize_tts_bytes(text, cfg, on_download_progress=on_dl)
            if err:
                return ("error", None, err)
            if not audio_bytes:
                return ("no_audio", None, "no audio returned")
            return ("ok", audio_bytes, None)

        def on_done(result_or_future):
            # Anki 25.09 passes a Future to on_done; older versions may pass the result directly.
            try:
                from concurrent.futures import Future
            except Exception:
                Future = None
            if Future and isinstance(result_or_future, Future):
                try:
                    result = result_or_future.result()
                except Exception as e:
                    status, payload, err = ("error", None, str(e))
                else:
                    status, payload, err = result
            else:
                result = result_or_future
                status, payload, err = result

            if status == "ok":
                audio_bytes = payload
                tts_cfg = cfg.get("tts") or {}
                provider = (tts_cfg.get("provider") or "dashscope").lower()
                exts = tts_cfg.get("exts") or {}
                ext = (exts.get(provider) or tts_cfg.get("ext") or "wav").lstrip(".")
                template = cfg.get("filename_template") or "tts_{nid}_{field}.{ext}"
                try:
                    preferred_name = template.format(nid=job["nid"], field=dst, ext=ext)
                    # Sanitize to prevent path traversal
                    import re
                    preferred_name = re.sub(r'[\\/]', '_', preferred_name)
                except Exception:
                    preferred_name = safe_filename_from_text(text, ext)
                if len(preferred_name) < 8:
                    preferred_name = safe_filename_from_text(text, ext)

                stored_name = add_media_bytes(preferred_name, audio_bytes)
                if not stored_name:
                    status, err = "error", "failed to store media"
                else:
                    tag = render_sound_tag(stored_name)
                    write_mode = "replace" if overwrite else (cfg.get("write_mode") or "append").lower()
                    try:
                        note = mw.col.get_note(job["nid"])
                        cur_val = note[dst]
                        if write_mode == "replace":
                            new_val = tag
                        else:
                            sep = cfg.get("append_separator") or " "
                            new_val = cur_val if tag in cur_val else (cur_val + (sep if cur_val.strip() else "") + tag)
                        note[dst] = new_val
                        update_note(note)
                    except Exception as e:
                        status, err = "error", f"write failed: {e}"
                    else:
                        status = "ok"

            if status == "ok":
                job["state"] = "done"
                job["progress"] = 100
                self._update_row(job["row"], state="done", busy=False, progress=100)
            elif status == "no_audio":
                job["state"] = "error"
                self._update_row(job["row"], state="no audio", busy=False, progress=0)
            else:
                job["state"] = "error"
                self._update_row(job["row"], state=f"error: {err}", busy=False, progress=0)
            self._update_batch_bar()
            mw.taskman.run_on_main(self._process_next)

        # Run in background
        try:
            mw.taskman.run_in_background(bg, on_done)
        except Exception:
            # Fallback: synchronous
            res = bg()
            on_done(res)

    def process_notes(self):
        """Process all selected notes, or the current review note."""
        nids = selected_note_ids_in_browser()
        if not nids:
            nid = current_reviewer_note_id()
            nids = [nid] if nid else []
        if not nids:
            showInfo("Open the Browser and select a note, or open a card in Review.")
            return
        self._enqueue_notes(list(nids))
        self._start_queue()


# Keep the dock and panel referenced while their Browser is open.
_panel_instance: Optional[TTSPanel] = None
_dock_instance: Optional[QDockWidget] = None
_browser_instance = None


def open_tts_dialog():
    """Open the Browser and show the TTS panel docked inside it."""
    global _panel_instance, _dock_instance, _browser_instance

    browser = dialogs.open("Browser", mw)
    if _dock_instance is None or _browser_instance is not browser:
        dock = QDockWidget(ADDON_TITLE, browser)
        dock.setObjectName("AnkiDeckTTSDock")
        try:
            bottom_area = Qt.DockWidgetArea.BottomDockWidgetArea
            dock_features = (
                QDockWidget.DockWidgetFeature.DockWidgetClosable
                | QDockWidget.DockWidgetFeature.DockWidgetMovable
            )
        except Exception:
            bottom_area = Qt.BottomDockWidgetArea
            dock_features = QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable
        dock.setAllowedAreas(bottom_area)
        dock.setFeatures(dock_features)

        panel = TTSPanel(browser)
        dock.setWidget(panel)
        browser.addDockWidget(bottom_area, dock)

        _panel_instance = panel
        _dock_instance = dock
        _browser_instance = browser

        def clear_references(*_args):
            global _panel_instance, _dock_instance, _browser_instance
            if _dock_instance is dock:
                _panel_instance = None
                _dock_instance = None
                _browser_instance = None

        qconnect(dock.destroyed, clear_references)
    else:
        _panel_instance.refresh_decks()

    _dock_instance.show()
    _dock_instance.raise_()
    browser.raise_()
    browser.activateWindow()
