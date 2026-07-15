from pathlib import Path
import tempfile
import unittest

from analyzer.project_scan import ProjectScanner
from report import write_reports


class ReportTests(unittest.TestCase):
    def test_writes_markdown_and_html_with_file_responsibilities(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "demo"
            root.mkdir()
            (root / "main.py").write_text("def run():\n    return True\n", encoding="utf-8")
            result = ProjectScanner(max_workers=1).scan(root)
            output = Path(directory) / "output"

            paths = write_reports(result, output)
            markdown = Path(paths["markdown"]).read_text(encoding="utf-8")
            html = Path(paths["html"]).read_text(encoding="utf-8")

        self.assertIn("项目目录组成", markdown)
        self.assertIn("文件职责与代码组成", markdown)
        self.assertIn("`main.py`", markdown)
        self.assertIn("`run()`", markdown)
        self.assertIn("<!doctype html>", html)


if __name__ == "__main__":
    unittest.main()
