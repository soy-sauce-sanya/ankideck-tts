import unittest

import text_utils


class StripHtmlTests(unittest.TestCase):
    def test_empty_values_return_empty_string(self):
        self.assertEqual(text_utils.strip_html(""), "")
        self.assertEqual(text_utils.strip_html(None), "")

    def test_removes_tags(self):
        self.assertEqual(text_utils.strip_html("<b>你好</b> <i>world</i>"), "你好 world")

    def test_removes_tags_with_attributes(self):
        html = '<span style="color: red" class="x">text</span>'
        self.assertEqual(text_utils.strip_html(html), "text")

    def test_unescapes_entities(self):
        self.assertEqual(text_utils.strip_html("Tom &amp; Jerry&nbsp;&quot;x&quot;"), 'Tom & Jerry\xa0"x"')

    def test_escaped_tags_are_kept_as_text(self):
        self.assertEqual(text_utils.strip_html("&lt;b&gt;bold&lt;/b&gt;"), "<b>bold</b>")

    def test_plain_text_is_unchanged(self):
        self.assertEqual(text_utils.strip_html("plain text"), "plain text")


class SafeFilenameTests(unittest.TestCase):
    def test_uses_text_and_extension(self):
        self.assertEqual(text_utils.safe_filename_from_text("hello", "mp3"), "hello.mp3")

    def test_truncates_to_twenty_characters(self):
        name = text_utils.safe_filename_from_text("a" * 50, "wav")
        self.assertEqual(name, "a" * 20 + ".wav")

    def test_removes_forbidden_characters(self):
        name = text_utils.safe_filename_from_text('a<b>c:d"e/f\\g|h?i*j', "mp3")
        self.assertEqual(name, "abcdefghij.mp3")

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(text_utils.safe_filename_from_text("  word  ", "mp3"), "word.mp3")

    def test_falls_back_to_audio(self):
        self.assertEqual(text_utils.safe_filename_from_text("", "mp3"), "audio.mp3")
        self.assertEqual(text_utils.safe_filename_from_text(None, "mp3"), "audio.mp3")
        self.assertEqual(text_utils.safe_filename_from_text("  ", "mp3"), "audio.mp3")
        self.assertEqual(text_utils.safe_filename_from_text("<>:?*", "mp3"), "audio.mp3")

    def test_keeps_unicode(self):
        self.assertEqual(text_utils.safe_filename_from_text("你好世界", "mp3"), "你好世界.mp3")


class RenderSoundTagTests(unittest.TestCase):
    def test_renders_anki_sound_tag(self):
        self.assertEqual(text_utils.render_sound_tag("hello.mp3"), "[sound:hello.mp3]")


if __name__ == "__main__":
    unittest.main()
