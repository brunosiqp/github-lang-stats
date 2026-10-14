import os
import sys
import unittest
from xml.dom import minidom

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("GH_TOKEN", "offline-test")  # the module exits on import without a token

import language_stats  # noqa: E402

SAMPLE = [("Python", 86.5), ("GDScript", 10.9), ("HTML", 1.2), ("C<Weird>", 0.003)]


class LanguageCardTests(unittest.TestCase):
    def test_card_is_valid_svg_with_profile_width(self):
        doc = minidom.parseString(language_stats.build_svg(SAMPLE))
        self.assertEqual(doc.documentElement.getAttribute("width"), "830")

    def test_card_lists_every_language_with_percentage(self):
        svg = language_stats.build_svg(SAMPLE)
        self.assertIn(">Python<", svg)
        self.assertIn(">86.5%<", svg)
        self.assertIn(">0.003%<", svg)

    def test_card_escapes_language_names(self):
        self.assertIn("C&lt;Weird&gt;", language_stats.build_svg(SAMPLE))

    def test_card_has_title_and_subtitle(self):
        svg = language_stats.build_svg(SAMPLE)
        self.assertIn("Most Used Languages", svg)
        self.assertIn("public and private", svg)


if __name__ == "__main__":
    unittest.main()
