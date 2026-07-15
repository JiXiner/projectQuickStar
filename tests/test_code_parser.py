from pathlib import Path
import tempfile
import unittest

from analyzer.code_parser import analyze_source_file


class CodeParserTests(unittest.TestCase):
    def test_python_file_reports_classes_functions_and_docstrings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "user_service.py"
            path.write_text(
                '"""用户业务服务。"""\n'
                "import json\n\n"
                "class UserService:\n"
                "    \"\"\"处理用户业务。\"\"\"\n"
                "    def get_user(self, user_id):\n"
                "        \"\"\"按编号读取用户。\"\"\"\n"
                "        return user_id\n",
                encoding="utf-8",
            )

            analysis = analyze_source_file(path)

        self.assertEqual(analysis["purpose"], "用户业务服务。")
        self.assertEqual(analysis["imports"], ["json"])
        self.assertEqual([symbol["name"] for symbol in analysis["symbols"]], ["UserService", "get_user"])
        self.assertEqual(analysis["symbols"][1]["purpose"], "按编号读取用户。")


if __name__ == "__main__":
    unittest.main()
