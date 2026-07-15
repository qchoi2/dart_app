import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from env_loader import load_dotenv


class EnvLoaderTests(unittest.TestCase):
    def test_project_env_overrides_existing_value(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("DART_API_KEY=new-value\n", encoding="utf-8")
            with patch.dict(os.environ, {"DART_API_KEY": "old-value"}):
                load_dotenv(env_file)
                self.assertEqual(os.environ["DART_API_KEY"], "new-value")


if __name__ == "__main__":
    unittest.main()
