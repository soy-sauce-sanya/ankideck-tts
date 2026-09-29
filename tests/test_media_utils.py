import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

if "aqt" not in sys.modules:
    fake_aqt = types.ModuleType("aqt")
    fake_aqt.mw = None
    sys.modules["aqt"] = fake_aqt

import media_utils


class AddMediaBytesTests(unittest.TestCase):
    def setUp(self):
        self.mw = MagicMock()
        patcher = patch.object(media_utils, "mw", self.mw)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_uses_write_data(self):
        self.mw.col.media.write_data.return_value = "hello-1.mp3"

        result = media_utils.add_media_bytes("hello.mp3", b"audio")

        self.assertEqual(result, "hello-1.mp3")
        self.mw.col.media.write_data.assert_called_once_with("hello.mp3", b"audio")
        self.mw.col.media.add_file.assert_not_called()

    def test_falls_back_to_add_file_with_temp_file(self):
        self.mw.col.media.write_data.side_effect = AttributeError("old Anki")
        seen = {}

        def add_file(path):
            seen["path"] = path
            with open(path, "rb") as f:
                seen["data"] = f.read()
            return "stored.mp3"

        self.mw.col.media.add_file.side_effect = add_file

        result = media_utils.add_media_bytes("hello.mp3", b"audio")

        self.assertEqual(result, "stored.mp3")
        self.assertEqual(seen["data"], b"audio")
        self.assertFalse(os.path.exists(seen["path"]))

    def test_returns_none_when_both_methods_fail(self):
        self.mw.col.media.write_data.side_effect = RuntimeError("fail")
        seen = {}

        def add_file(path):
            seen["path"] = path
            raise RuntimeError("fail")

        self.mw.col.media.add_file.side_effect = add_file

        result = media_utils.add_media_bytes("hello.mp3", b"audio")

        self.assertIsNone(result)
        self.assertFalse(os.path.exists(seen["path"]))


class UpdateNoteTests(unittest.TestCase):
    def setUp(self):
        self.mw = MagicMock()
        patcher = patch.object(media_utils, "mw", self.mw)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_uses_collection_update_note(self):
        note = MagicMock()

        media_utils.update_note(note)

        self.mw.col.update_note.assert_called_once_with(note)
        note.flush.assert_not_called()

    def test_notifies_open_windows_about_the_change(self):
        note = MagicMock()
        changes = object()
        initiator = object()
        self.mw.col.update_note.return_value = changes
        hooks = types.SimpleNamespace(operation_did_execute=MagicMock())

        with patch.object(sys.modules["aqt"], "gui_hooks", hooks, create=True):
            media_utils.update_note(note, initiator=initiator)

        hooks.operation_did_execute.assert_called_once_with(changes, initiator)

    def test_old_anki_without_changes_skips_notification(self):
        self.mw.col.update_note.return_value = None
        hooks = types.SimpleNamespace(operation_did_execute=MagicMock())

        with patch.object(sys.modules["aqt"], "gui_hooks", hooks, create=True):
            media_utils.update_note(MagicMock())

        hooks.operation_did_execute.assert_not_called()

    def test_falls_back_to_flush(self):
        self.mw.col.update_note.side_effect = AttributeError("old Anki")
        note = MagicMock()

        media_utils.update_note(note)

        note.flush.assert_called_once_with()

    def test_swallows_errors_when_both_methods_fail(self):
        self.mw.col.update_note.side_effect = RuntimeError("fail")
        note = MagicMock()
        note.flush.side_effect = RuntimeError("fail")

        media_utils.update_note(note)

        note.flush.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
