
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import sys
vendor = Path(__file__).resolve().parent / "vendor_build"
if str(vendor) not in sys.path:
    sys.path.insert(0, str(vendor))


import os, re, html
from typing import Optional, Tuple, List, Dict

from aqt import mw, gui_hooks, dialogs
from aqt.qt import (
    QAction, QKeySequence, qconnect,
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QCheckBox, QProgressBar
)
from aqt.utils import showInfo

ADDON_TITLE = "AnkiDeck TTS"
TOOLBAR_LINK_LABEL = "TTS"
TOOLBAR_LINK_TOOLTIP = "Open AnkiDeck TTS"

DEFAULT_CONFIG = {
    "tts": {
        "provider": "dashscope",
        "api_key": "",
        "model": "qwen3-tts-flash",
        "voice": "Ethan",
        "language_type": "Chinese",
        "ext": "wav"
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

def _get_cfg():
    cfg = mw.addonManager.getConfig(__name__) or {}
    merged = dict(DEFAULT_CONFIG)
    merged_tts = dict(DEFAULT_CONFIG.get("tts", {}))
    merged_tts.update((cfg.get("tts") or {}))
    merged.update(cfg)
    merged["tts"] = merged_tts
    merged_batch = dict(DEFAULT_CONFIG.get("batch", {}))
    merged_batch.update((cfg.get("batch") or {}))
    merged["batch"] = merged_batch
    return merged

# --- Qt5/Qt6 compatibility for header enums
try:
    RESIZE_TO_CONTENTS = QHeaderView.ResizeMode.ResizeToContents  # PyQt6
    RESIZE_STRETCH = QHeaderView.ResizeMode.Stretch
except Exception:
    RESIZE_TO_CONTENTS = QHeaderView.ResizeToContents             # PyQt5
    RESIZE_STRETCH = QHeaderView.Stretch

# --- HTTP with progress
def _http_get_bytes_stream(url: str, on_progress=None) -> Tuple[Optional[bytes], Optional[str]]:
    try:
        import requests
        with requests.get(url, stream=True, timeout=120) as r:
            if int(r.status_code) != 200:
                return None, f"HTTP {r.status_code}"
            total = int(r.headers.get("Content-Length") or 0)
            chunks = []
            downloaded = 0
            for chunk in r.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                chunks.append(chunk)
                downloaded += len(chunk)
                if on_progress and total:
                    pct = int(downloaded * 100 / total)
                    on_progress(min(pct, 100))
            data = b"".join(chunks)
            if on_progress and total:
                on_progress(100)
            return data, None
    except Exception as e:
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=120) as resp:
                if int(resp.status) != 200:
                    return None, f"HTTP {resp.status}"
                data = resp.read()
                if on_progress:
                    on_progress(100)
                return data, None
        except Exception as e2:
            return None, f"{e2}"

# --- Collection helpers
def _all_deck_names_and_ids():
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

def _all_model_names_and_ids():
    mman = mw.col.models
    try:
        return [(m["name"], m["id"]) for m in mman.all()]
    except Exception:
        try:
            return list(mman.all_names_and_ids())
        except Exception:
            return []

def _model_by_id_or_name(model_id_or_name):
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

def _field_names_for_model(model):
    try:
        flds = model.get("flds", [])
        return [f.get("name", "") for f in flds if isinstance(f, dict)]
    except Exception:
        try:
            return [f.name for f in model.fields]
        except Exception:
            return []

# --- Media & note helpers
def _add_media_bytes(preferred_name: str, data: bytes) -> Optional[str]:
    try:
        return mw.col.media.write_data(preferred_name, data)
    except Exception:
        import tempfile
        tmp = tempfile.NamedTemporaryFile(delete=False)
        try:
            tmp.write(data); tmp.flush(); tmp.close()
            try:
                return mw.col.media.add_file(tmp.name)
            except Exception:
                return None
        finally:
            try: os.unlink(tmp.name)
            except Exception: pass

def _update_note(note):
    try:
        mw.col.update_note(note)
    except Exception:
        try: note.flush()
        except Exception: pass

# --- TTS provider (DashScope) with download progress callback
def _synthesize_tts_bytes(text: str, cfg: dict, on_download_progress=None) -> Tuple[Optional[bytes], Optional[str]]:
    tts = cfg.get("tts") or {}
    api_key = tts.get("api_key") or ""
    model = tts.get("model") or "qwen3-tts-flash"
    voice = tts.get("voice") or "Cherry"
    lang = tts.get("language_type") or "Chinese"
    if not api_key:
        return None, "API key (tts.api_key) is not set in add-on config."
    try:
        import dashscope
    except Exception:
        return None, "Module 'dashscope' is not installed in Anki's environment."
    try:
        response = dashscope.audio.qwen_tts.SpeechSynthesizer.call(
            model=model, api_key=api_key, text=text, voice=voice, language_type=lang
        )
    except Exception as e:
        return None, f"DashScope error: {e}"
    status = getattr(response, "status_code", None)
    if status != 200:
        msg = getattr(response, "message", "unknown error")
        return None, f"API error (status={status}): {msg}"
    try:
        audio_url = response.output['audio']['url']
    except Exception:
        return None, "Audio URL not found in API response."
    data, err = _http_get_bytes_stream(audio_url, on_progress=on_download_progress)
    if err: return None, f"Audio download error: {err}"
    return data, None

def _strip_html(text: str) -> str:
    if not text:
        return ""
    s = re.sub(r"<[^>]+>", "", text)
    return html.unescape(s)

def _safe_filename_from_text(text: str, ext: str) -> str:
    base = (text or "")[:20]
    base = re.sub(r'[<>:\"/\\\\|?*]', '', base).strip() or "audio"
    return f"{base}.{ext}"

def _render_sound_tag(fname: str) -> str:
    return f"[sound:{fname}]"

def _selected_note_ids_in_browser() -> Optional[List[int]]:
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

def _current_reviewer_note_id() -> Optional[int]:
    try:
        c = mw.reviewer.card
        if c:
            return c.note().id
    except Exception:
        pass
    return None

# -------------------------
# Main dialog with queue
# -------------------------

class TTSDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.setWindowTitle(ADDON_TITLE)
        self.resize(900, 680)

        self.deck_combo = QComboBox(self)
        self.model_combo = QComboBox(self)
        self.source_field_combo = QComboBox(self)
        self.target_field_combo = QComboBox(self)

        cfg = _get_cfg()
        self.overwrite_chk = QCheckBox("Overwrite audio (replace target field content)", self)
        self.overwrite_chk.setChecked(bool(cfg.get("batch", {}).get("overwrite", False)))

        # Buttons (as requested)
        self.process_current_btn = QPushButton("Process current/selected", self)
        self.process_selected_btn = QPushButton("Process selected (Browser)", self)
        self.clear_btn = QPushButton("Clear", self) # Новая кнопка
        self.close_btn = QPushButton("Close", self)

        # Queue table: Text | State | Progress
        self.table = QTableWidget(self); self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Text", "State", "Progress"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, RESIZE_TO_CONTENTS)
        header.setSectionResizeMode(1, RESIZE_TO_CONTENTS)
        header.setSectionResizeMode(2, RESIZE_STRETCH)

        # Overall progress
        self.batch_bar = QProgressBar(self); self.batch_bar.setValue(0); self.batch_bar.setFormat("%p% processed")

        # Layout
        form = QFormLayout()
        form.addRow("Deck:", self.deck_combo)
        form.addRow("Note type:", self.model_combo)
        form.addRow("Source field (text → API):", self.source_field_combo)
        form.addRow("Target field (will get audio):", self.target_field_combo)
        form.addRow("Overwrite:", self.overwrite_chk)

        top = QVBoxLayout(self); top.addLayout(form)

        btns = QHBoxLayout()
        btns.addWidget(self.process_current_btn)
        btns.addWidget(self.process_selected_btn)
        btns.addStretch(1)
        btns.addWidget(self.clear_btn) # Добавляем кнопку в макет
        btns.addWidget(self.close_btn)
        top.addLayout(btns)

        top.addWidget(QLabel("Queue:"))
        top.addWidget(self.table)
        top.addWidget(self.batch_bar)

        # Signals
        qconnect(self.process_current_btn.clicked, self.process_current_note)
        qconnect(self.process_selected_btn.clicked, self.process_selected_notes)
        qconnect(self.clear_btn.clicked, self._clear_queue) # Сигнал для новой кнопки
        qconnect(self.close_btn.clicked, self._on_close_clicked) # Измененный сигнал для кнопки Close
        qconnect(self.model_combo.currentIndexChanged, self._on_model_changed)

        # Queue state
        self.jobs: List[Dict] = []
        self._queue_running = False

        # Populate
        self._load_decks(); self._load_models(); self._select_current_deck(); self._on_model_changed()
    
    # --- Новые методы для очистки и закрытия ---
    def _clear_queue(self):
        """Очищает таблицу и список задач."""
        self.jobs.clear()
        self.table.setRowCount(0)
        self.batch_bar.setValue(0)
        self._queue_running = False

    def _on_close_clicked(self):
        """Очищает очередь и закрывает диалоговое окно."""
        self._clear_queue()
        self.close()

    # --- populate combos ---
    def _load_decks(self):
        self.deck_combo.clear()
        for name, did in _all_deck_names_and_ids():
            self.deck_combo.addItem(name or "(no name)", did)

    def _select_current_deck(self):
        try:
            cur = mw.col.decks.current(); did = cur.get("id")
            if did is None: return
            for i in range(self.deck_combo.count()):
                if self.deck_combo.itemData(i) == did:
                    self.deck_combo.setCurrentIndex(i); return
        except Exception: pass

    def _load_models(self):
        self.model_combo.clear()
        for name, mid in _all_model_names_and_ids():
            self.model_combo.addItem(name, mid)

    def _on_model_changed(self):
        self.source_field_combo.clear(); self.target_field_combo.clear()
        model_name = self.model_combo.currentText(); model_id = self.model_combo.currentData()
        model = _model_by_id_or_name(model_id) or _model_by_id_or_name(model_name)
        if not model: return
        fields = _field_names_for_model(model)
        for fn in fields:
            self.source_field_combo.addItem(fn)
            self.target_field_combo.addItem(fn)
        lf = [f.lower() for f in fields]
        def sel(combo, cands, default_index=0):
            for cand in cands:
                if cand.lower() in lf:
                    combo.setCurrentIndex(lf.index(cand.lower())); return
            combo.setCurrentIndex(default_index)
        sel(self.source_field_combo, ["Back","Text","Expression","Front"])
        sel(self.target_field_combo, ["Audio","Pronunciation","BackAudio","Sound","AudioBack"])

    # --- Queue utilities
    def _append_job_row(self, text: str, state: str) -> int:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(text))
        self.table.setItem(row, 1, QTableWidgetItem(state))
        bar = QProgressBar(self.table); bar.setValue(0); bar.setFormat("%p%")
        self.table.setCellWidget(row, 2, bar)
        return row

    def _update_row(self, row: int, *, state: Optional[str]=None, progress: Optional[int]=None, busy: bool=False):
        if state is not None:
            self.table.item(row, 1).setText(state)
        bar: QProgressBar = self.table.cellWidget(row, 2)
        if busy:
            bar.setRange(0,0)  # indeterminate
        else:
            bar.setRange(0,100)
        if progress is not None:
            bar.setValue(max(0, min(100, progress)))

    def _enqueue_notes(self, nids: List[int]):
        src = self.source_field_combo.currentText()
        for nid in nids:
            try:
                note = mw.col.get_note(nid)
                text = _strip_html(note.get(src, "")) if hasattr(note, "get") else _strip_html(note[src])
            except Exception:
                text = ""
            preview = (text[:80] + "…") if len(text) > 80 else text
            row = self._append_job_row(preview or "(empty)", "waiting")
            self.jobs.append({"nid": nid, "row": row, "state": "waiting", "progress": 0, "text": text})
        self._update_batch_bar()

    def _update_batch_bar(self):
        total = max(1, len(self.jobs))
        done = len([j for j in self.jobs if j["state"] in ("done","skipped","error")])
        self.batch_bar.setValue(int(done * 100 / total))

    def _start_queue(self):
        if not self._queue_running and self.jobs:
            self._queue_running = True
            self._process_next()

    def _process_next(self):
        next_job = None
        for job in self.jobs:
            if job["state"] == "waiting":
                next_job = job; break
        if not next_job:
            self._queue_running = False
            showInfo(f"Queue finished. Total: {len(self.jobs)}")
            return
        self._process_job(next_job)

    def _process_job(self, job: Dict):
        cfg = _get_cfg()
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
            audio_bytes, err = _synthesize_tts_bytes(text, cfg, on_download_progress=on_dl)
            if err: return ("error", None, err)
            if not audio_bytes: return ("no_audio", None, "no audio returned")

            # Store media
            tts_cfg = cfg.get("tts") or {}; ext = (tts_cfg.get("ext") or "wav").lstrip(".")
            template = cfg.get("filename_template") or "tts_{nid}_{field}.{ext}"
            preferred_name = template.format(nid=job["nid"], field=dst, ext=ext)
            if len(preferred_name) < 8:
                preferred_name = _safe_filename_from_text(text, ext)
            stored_name = _add_media_bytes(preferred_name, audio_bytes)
            if not stored_name: return ("error", None, "failed to store media")

            # Update note
            tag = _render_sound_tag(stored_name)
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
                _update_note(note)
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
                job["state"] = "done"; job["progress"] = 100
                self._update_row(job["row"], state="done", busy=False, progress=100)
            elif status in ("skip_empty", "skip_has_sound"):
                job["state"] = "skipped"; job["progress"] = 0
                label = "skipped (empty)" if status=="skip_empty" else "skipped (already has sound)"
                self._update_row(job["row"], state=label, busy=False, progress=0)
            elif status == "no_audio":
                job["state"] = "error"; self._update_row(job["row"], state="no audio", busy=False, progress=0)
            else:
                job["state"] = "error"; self._update_row(job["row"], state=f"error: {err}", busy=False, progress=0)
            self._update_batch_bar()
            mw.taskman.run_on_main(self._process_next)

        # Run in background
        try:
            mw.taskman.run_in_background(bg, on_done)
        except Exception:
            # Fallback: synchronous
            res = bg()
            on_done(res)

    # --- Buttons
    def process_current_note(self):
        nids = _selected_note_ids_in_browser()
        nid = (nids[0] if nids else None) or _current_reviewer_note_id()
        if not nid:
            showInfo("Open the Browser and select a note, or open a card in Review."); return
        self._enqueue_notes([nid])
        self._start_queue()

    def process_selected_notes(self):
        sel = _selected_note_ids_in_browser()
        if not sel:
            showInfo("Nothing selected in the Browser. Select notes and try again."); return
        self._enqueue_notes(list(sel))
        self._start_queue()


# Keep a single dialog instance referenced to avoid GC
_dialog_instance: TTSDialog | None = None
def open_tts_dialog():
    global _dialog_instance
    if _dialog_instance is None:
        _dialog_instance = TTSDialog(mw)
    _dialog_instance.show(); _dialog_instance.raise_(); _dialog_instance.activateWindow()

# Toolbar link
def _add_top_toolbar_link(links, toolbar, *args, **kwargs):
    link = toolbar.create_link(TOOLBAR_LINK_LABEL, TOOLBAR_LINK_TOOLTIP, open_tts_dialog)
    links.append(link)
gui_hooks.top_toolbar_did_init_links.append(_add_top_toolbar_link)

# Menu item & hotkey
def _add_menu_action() -> None:
    action = QAction(f"{ADDON_TITLE}: Open", mw)
    action.setShortcut(QKeySequence("Ctrl+Alt+T"))
    qconnect(action.triggered, open_tts_dialog)
    mw.form.menuTools.addAction(action)

def _on_main_window_did_init(_mw=None, *args, **kwargs):
    _add_menu_action()
gui_hooks.main_window_did_init.append(_on_main_window_did_init)