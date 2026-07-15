import unittest

from analyzer.language_detector import detect_languages, language_for_path, matches_language


class LanguageDetectorTests(unittest.TestCase):
    def test_detect_languages_counts_supported_files(self):
        self.assertEqual(
            detect_languages(["a.py", "B.java", "ui.tsx", "readme.md", "view.vue"]),
            {"JavaScript": 2, "Python": 1, "Java": 1},
        )

    def test_language_filter_keeps_non_source_and_selected_source(self):
        self.assertTrue(matches_language("README.md", "Python"))
        self.assertTrue(matches_language("main.py", "Python"))
        self.assertFalse(matches_language("Main.java", "Python"))
        self.assertEqual(language_for_path("MAIN.PY"), "Python")


if __name__ == "__main__":
    unittest.main()
