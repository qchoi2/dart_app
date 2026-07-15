import unittest
from pathlib import Path


class InstallerTests(unittest.TestCase):
    def test_installer_contains_required_safe_steps(self):
        installer = Path(__file__).resolve().parents[1] / "MCP 설치.bat"
        content = installer.read_text(encoding="utf-8")

        self.assertIn("pip install", content)
        self.assertIn("requirements.txt", content)
        self.assertIn("DART_API_KEY", content)
        self.assertIn("merge_config.py", content)
        self.assertNotIn("C:\\Users\\", content)


if __name__ == "__main__":
    unittest.main()
