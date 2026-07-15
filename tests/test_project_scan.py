from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from analyzer.project_scan import ProjectScanner


class ProjectScannerTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_scans_directory_and_excludes_generated_directories(self):
        (self.tmp_path / "main.py").write_text("print('ok')", encoding="utf-8")
        (self.tmp_path / "README.md").write_text("hello", encoding="utf-8")
        node_modules = self.tmp_path / "node_modules"
        node_modules.mkdir()
        (node_modules / "ignored.js").write_text("x", encoding="utf-8")

        result = ProjectScanner(max_workers=2).scan(self.tmp_path)

        self.assertEqual(result.total_files, 2)
        self.assertEqual(result.detected_languages, {"Python": 1})
        self.assertEqual({item.path for item in result.files}, {"main.py", "README.md"})

    def test_scans_zip_and_filters_other_source_languages(self):
        archive_path = self.tmp_path / "sample.zip"
        with ZipFile(archive_path, "w") as archive:
            archive.writestr("demo/app.py", "print('ok')")
            archive.writestr("demo/App.java", "class App {}")
            archive.writestr("demo/config.yml", "name: demo")

        result = ProjectScanner(max_workers=2).scan(archive_path, "Python")

        self.assertEqual({item.path for item in result.files}, {"app.py", "config.yml"})
        self.assertEqual(result.skipped_files, 1)

    def test_rejects_zip_path_traversal(self):
        archive_path = self.tmp_path / "unsafe.zip"
        with ZipFile(archive_path, "w") as archive:
            archive.writestr("../escape.py", "bad")

        with self.assertRaisesRegex(ValueError, "不安全路径"):
            ProjectScanner().scan(archive_path)


if __name__ == "__main__":
    unittest.main()
