import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import merge_config


class MergeConfigTests(unittest.TestCase):
    def test_invalid_json_is_rejected_without_modification(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            original = "{invalid"
            path.write_text(original, encoding="utf-8")

            with self.assertRaises(ValueError):
                merge_config.load_config(path)

            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_save_config_creates_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{"old": true}\n', encoding="utf-8")

            with patch("builtins.print"):
                merge_config.save_config(path, {"mcpServers": {"opendart": {}}})

            self.assertTrue(path.with_suffix(".json.bak").exists())
            self.assertIn("opendart", json.loads(path.read_text(encoding="utf-8"))["mcpServers"])

    def test_explicit_config_path_has_priority(self):
        with tempfile.TemporaryDirectory() as directory:
            expected = Path(directory) / "claude.json"
            with patch.dict(os.environ, {"CLAUDE_CONFIG_PATH": str(expected)}):
                self.assertEqual(merge_config.find_config_path(), expected.resolve())

    def test_main_preserves_existing_servers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(
                json.dumps({"mcpServers": {"existing": {"command": "other"}}}),
                encoding="utf-8")

            with patch.object(merge_config, "find_config_path", return_value=path), \
                    patch("builtins.print"):
                self.assertEqual(merge_config.main(), 0)

            servers = json.loads(path.read_text(encoding="utf-8"))["mcpServers"]
            self.assertIn("existing", servers)
            self.assertIn("opendart", servers)


if __name__ == "__main__":
    unittest.main()
