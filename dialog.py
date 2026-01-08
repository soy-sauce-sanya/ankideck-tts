# -*- coding: utf-8 -*-
"""Main dialog UI for AnkiDeck TTS addon."""

from __future__ import annotations
from typing import Optional, List, Dict

from aqt import mw
from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QCheckBox, QProgressBar,
    qconnect
)
from aqt.utils import showInfo

from .config import get_config
from .anki_helpers import (
    all_deck_names_and_ids,
    all_model_names_and_ids,
    model_by_id_or_name,
    field_names_for_model,
    selected_note_ids_in_browser,
    current_reviewer_note_id
)
from .media_utils import add_media_bytes, update_note
from .tts_provider import synthesize_tts_bytes
from .text_utils import strip_html, safe_filename_from_text, render_sound_tag
from .voice_utils import (
    get_voice_display_name,
    language_display_to_api_format,
    get_provider_voices_and_languages
)


# Qt5/Qt6 compatibility for header enums
try:
    RESIZE_TO_CONTENTS = QHeaderView.ResizeMode.ResizeToContents  # PyQt6
    RESIZE_STRETCH = QHeaderView.ResizeMode.Stretch
except Exception:
    RESIZE_TO_CONTENTS = QHeaderView.ResizeToContents  # PyQt5
    RESIZE_STRETCH = QHeaderView.Stretch


ADDON_TITLE = "AnkiDeck TTS"


class TTSDialog(QDialog):
    """Main dialog for batch TTS processing."""

    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.setWindowTitle(ADDON_TITLE)
        self.resize(900, 680)

        self.deck_combo = QComboBox(self)
        self.model_combo = QComboBox(self)
        self.source_field_combo = QComboBox(self)
        self.target_field_combo = QComboBox(self)
        self.provider_combo = QComboBox(self)
        self.voice_combo = QComboBox(self)
        self.language_combo = QComboBox(self)

        cfg = get_config()
        self.overwrite_chk = QCheckBox("Overwrite audio (replace target field content)", self)
        self.overwrite_chk.setChecked(bool(cfg.get("batch", {}).get("overwrite", False)))

        # Buttons
        self.process_current_btn = QPushButton("Process current/selected", self)
        self.process_selected_btn = QPushButton("Process selected (Browser)", self)
        self.clear_btn = QPushButton("Clear", self)
        self.close_btn = QPushButton("Close", self)

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

        # Layout
        form = QFormLayout()
        form.addRow("Deck:", self.deck_combo)
        form.addRow("Note type:", self.model_combo)
        form.addRow("Source field (text → API):", self.source_field_combo)
        form.addRow("Target field (will get audio):", self.target_field_combo)
        form.addRow("Provider:", self.provider_combo)
        form.addRow("Voice:", self.voice_combo)
        form.addRow("Language:", self.language_combo)
        form.addRow("Overwrite:", self.overwrite_chk)

        top = QVBoxLayout(self)
        top.addLayout(form)

        btns = QHBoxLayout()
        btns.addWidget(self.process_current_btn)
        btns.addWidget(self.process_selected_btn)
        btns.addStretch(1)
        btns.addWidget(self.clear_btn)
        btns.addWidget(self.close_btn)
        top.addLayout(btns)

        top.addWidget(QLabel("Queue:"))
        top.addWidget(self.table)
        top.addWidget(self.batch_bar)

        # Signals
        qconnect(self.process_current_btn.clicked, self.process_current_note)
        qconnect(self.process_selected_btn.clicked, self.process_selected_notes)
        qconnect(self.clear_btn.clicked, self._clear_queue)
        qconnect(self.close_btn.clicked, self._on_close_clicked)
        qconnect(self.model_combo.currentIndexChanged, self._on_model_changed)
        qconnect(self.provider_combo.currentIndexChanged, self._on_provider_changed)
        qconnect(self.voice_combo.currentIndexChanged, self._on_voice_changed)
        qconnect(self.language_combo.currentIndexChanged, self._on_language_changed)

        # Queue state
        self.jobs: List[Dict] = []
        self._queue_running = False

        # Voice/language data
        self.voices_data = []
        self.languages_data = []

        # Populate
        self._load_decks()
        self._load_models()
        self._load_providers()
        self._load_voices_and_languages()
        self._select_current_deck()
        self._on_model_changed()

    def _clear_queue(self):
        """Clear the queue table and job list."""
        self.jobs.clear()
        self.table.setRowCount(0)
        self.batch_bar.setValue(0)
        self._queue_running = False

    def _on_close_clicked(self):
        """Clear queue and close the dialog."""
        self._clear_queue()
        self.close()

    def _load_decks(self):
        """Load all decks into the deck combo box."""
        self.deck_combo.clear()
        for name, did in all_deck_names_and_ids():
            self.deck_combo.addItem(name or "(no name)", did)

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

    def _load_models(self):
        """Load all note types into the model combo box."""
        self.model_combo.clear()
        for name, mid in all_model_names_and_ids():
            self.model_combo.addItem(name, mid)

    def _on_model_changed(self):
        """Update field combos when model selection changes."""
        self.source_field_combo.clear()
        self.target_field_combo.clear()
        model_name = self.model_combo.currentText()
        model_id = self.model_combo.currentData()
        model = model_by_id_or_name(model_id) or model_by_id_or_name(model_name)
        if not model:
            return
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
        """Load voices and languages from voices.txt file."""
        provider = self.provider_combo.currentData() or cfg.get("tts", {}).get("provider", "dashscope")
        self.voices_data, self.languages_data = get_provider_voices_and_languages(provider)

        # Populate voice combo box
        self.voice_combo.clear()
        for voice in self.voices_data:
            display_name = get_voice_display_name(voice)
            self.voice_combo.addItem(display_name, voice['english'])

        # Populate language combo box
        self.language_combo.clear()
        for lang in self.languages_data:
            self.language_combo.addItem(lang, language_display_to_api_format(lang))

        # Select current voice and language from config
        cfg = get_config()
        tts_cfg = cfg.get("tts", {})
        current_voice = tts_cfg.get("voice", "Ethan")
        current_language_api = tts_cfg.get("language_type", "Chinese")

        # Find and select the current voice
        for i in range(self.voice_combo.count()):
            if self.voice_combo.itemData(i) == current_voice:
                self.voice_combo.setCurrentIndex(i)
                break

        # Find and select the current language
        if self.language_combo.count() == 0:
            self.language_combo.setEnabled(False)
        else:
            self.language_combo.setEnabled(True)
            for i in range(self.language_combo.count()):
                if self.language_combo.itemData(i) == current_language_api:
                    self.language_combo.setCurrentIndex(i)
                    break

    def _load_providers(self):
        """Load provider options into the combo box."""
        self.provider_combo.clear()
        self.provider_combo.addItem("Qwen (DashScope)", "dashscope")
        self.provider_combo.addItem("ChatGPT (OpenAI)", "openai")

        cfg = get_config()
        current_provider = (cfg.get("tts", {}) or {}).get("provider", "dashscope")
        for i in range(self.provider_combo.count()):
            if self.provider_combo.itemData(i) == current_provider:
                self.provider_combo.setCurrentIndex(i)
                break

    def _on_provider_changed(self):
        """Handle provider selection change."""
        provider = self.provider_combo.currentData()
        if provider:
            cfg = mw.addonManager.getConfig(__name__) or {}
            if "tts" not in cfg:
                cfg["tts"] = {}
            cfg["tts"]["provider"] = provider
            mw.addonManager.writeConfig(__name__, cfg)
            self._load_voices_and_languages()

    def _on_voice_changed(self):
        """Handle voice selection change."""
        voice_english = self.voice_combo.currentData()
        if voice_english:
            # Update config
            cfg = mw.addonManager.getConfig(__name__) or {}
            if "tts" not in cfg:
                cfg["tts"] = {}
            cfg["tts"]["voice"] = voice_english
            mw.addonManager.writeConfig(__name__, cfg)

    def _on_language_changed(self):
        """Handle language selection change."""
        language_api = self.language_combo.currentData()
        if language_api:
            # Update config
            cfg = mw.addonManager.getConfig(__name__) or {}
            if "tts" not in cfg:
                cfg["tts"] = {}
            cfg["tts"]["language_type"] = language_api
            mw.addonManager.writeConfig(__name__, cfg)

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
        for nid in nids:
            try:
                note = mw.col.get_note(nid)
                text = strip_html(note.get(src, "") if hasattr(note, "get") else note[src])
            except Exception:
                text = ""
            preview = (text[:80] + "…") if len(text) > 80 else text
            row = self._append_job_row(preview or "(empty)", "waiting")
            self.jobs.append({"nid": nid, "row": row, "state": "waiting", "progress": 0, "text": text})
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
        src = self.source_field_combo.currentText()
        dst = self.target_field_combo.currentText()
        overwrite = self.overwrite_chk.isChecked()

        job["state"] = "processing"
        self._update_row(job["row"], state="processing (generating…)", busy=True, progress=0)

        def bg():
            # Re-read text
            try:
                note = mw.col.get_note(job["nid"])
                text = note[src]
            except Exception:
                text = job.get("text") or ""
            # Skip if empty
            if not (text or "").strip() and bool((cfg.get("batch") or {}).get("skip_if_source_empty", True)):
                return ("skip_empty", None, "source empty")
            # Skip if has sound and not overwrite
            try:
                note = mw.col.get_note(job["nid"])
                cur_val = note[dst]
            except Exception:
                cur_val = ""
            if not overwrite and bool((cfg.get("batch") or {}).get("skip_if_target_has_sound", True)) and "[sound:" in (cur_val or ""):
                return ("skip_has_sound", None, "already has sound")

            # Synthesize & show download progress
            def on_dl(pct: int):
                mw.taskman.run_on_main(lambda: self._update_row(job["row"], state="processing (downloading…)", busy=False, progress=pct))

            audio_bytes, err = synthesize_tts_bytes(text, cfg, on_download_progress=on_dl)
            if err:
                return ("error", None, err)
            if not audio_bytes:
                return ("no_audio", None, "no audio returned")

            # Store media
            tts_cfg = cfg.get("tts") or {}
            ext = (tts_cfg.get("ext") or "wav").lstrip(".")
            template = cfg.get("filename_template") or "tts_{nid}_{field}.{ext}"
            preferred_name = template.format(nid=job["nid"], field=dst, ext=ext)
            if len(preferred_name) < 8:
                preferred_name = safe_filename_from_text(text, ext)
            stored_name = add_media_bytes(preferred_name, audio_bytes)
            if not stored_name:
                return ("error", None, "failed to store media")

            # Update note
            tag = render_sound_tag(stored_name)
            write_mode = "replace" if overwrite else (cfg.get("write_mode") or "append").lower()
            try:
                note = mw.col.get_note(job["nid"])
                cur_val = note[dst]
            except Exception:
                cur_val = ""
            if write_mode == "replace":
                new_val = tag
            else:
                sep = cfg.get("append_separator") or " "
                new_val = cur_val if tag in cur_val else (cur_val + (sep if cur_val.strip() else "") + tag)
            try:
                note[dst] = new_val
                update_note(note)
            except Exception as e:
                return ("error", None, f"write failed: {e}")

            return ("ok", stored_name, None)

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
                    status, stored_name, err = ("error", None, str(e))
                else:
                    status, stored_name, err = result
            else:
                result = result_or_future
                status, stored_name, err = result
            if status == "ok":
                job["state"] = "done"
                job["progress"] = 100
                self._update_row(job["row"], state="done", busy=False, progress=100)
            elif status in ("skip_empty", "skip_has_sound"):
                job["state"] = "skipped"
                job["progress"] = 0
                label = "skipped (empty)" if status == "skip_empty" else "skipped (already has sound)"
                self._update_row(job["row"], state=label, busy=False, progress=0)
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

    def process_current_note(self):
        """Process the current note or first selected note."""
        nids = selected_note_ids_in_browser()
        nid = (nids[0] if nids else None) or current_reviewer_note_id()
        if not nid:
            showInfo("Open the Browser and select a note, or open a card in Review.")
            return
        self._enqueue_notes([nid])
        self._start_queue()

    def process_selected_notes(self):
        """Process all selected notes in the browser."""
        sel = selected_note_ids_in_browser()
        if not sel:
            showInfo("Nothing selected in the Browser. Select notes and try again.")
            return
        self._enqueue_notes(list(sel))
        self._start_queue()


# Keep a single dialog instance referenced to avoid GC
_dialog_instance: Optional[TTSDialog] = None


def open_tts_dialog():
    """Open or show the TTS dialog."""
    global _dialog_instance
    if _dialog_instance is None:
        _dialog_instance = TTSDialog(mw)
    _dialog_instance.show()
    _dialog_instance.raise_()
    _dialog_instance.activateWindow()
