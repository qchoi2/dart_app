import importlib
import json
import os
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class FakeFastMCP:
    def __init__(self, _name):
        pass

    def tool(self):
        return lambda function: function

    def run(self):
        pass


def import_server_without_mcp_dependency():
    mcp_module = types.ModuleType("mcp")
    server_module = types.ModuleType("mcp.server")
    fastmcp_module = types.ModuleType("mcp.server.fastmcp")
    fastmcp_module.FastMCP = FakeFastMCP
    modules = {
        "mcp": mcp_module,
        "mcp.server": server_module,
        "mcp.server.fastmcp": fastmcp_module,
    }
    with patch.dict(sys.modules, modules):
        sys.modules.pop("dart_opendart_server", None)
        return importlib.import_module("dart_opendart_server")


class FinancialSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = import_server_without_mcp_dependency()

    def test_standard_account_id_wins_and_statement_is_respected(self):
        spec = self.server._ACCOUNT_TARGETS["매출액"]
        rows = [
            {"sj_div": "BS", "account_id": "ifrs-full_Revenue", "account_nm": "매출액"},
            {"sj_div": "IS", "account_id": "custom_Revenue", "account_nm": "매출액"},
            {"sj_div": "IS", "account_id": "ifrs-full_Revenue", "account_nm": "수익"},
        ]

        selected = self.server._select_account(rows, spec)

        self.assertEqual(selected["account_id"], "ifrs-full_Revenue")
        self.assertEqual(selected["sj_div"], "IS")

    def test_similar_but_wrong_account_name_is_not_selected(self):
        spec = self.server._ACCOUNT_TARGETS["매출액"]
        rows = [{"sj_div": "IS", "account_id": "custom_Cost", "account_nm": "매출원가"}]

        self.assertIsNone(self.server._select_account(rows, spec))

    def test_empty_company_query_is_rejected(self):
        with self.assertRaises(ValueError):
            self.server._resolve(" ")

    def test_stale_company_cache_is_refreshed(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "corp.json"
            cache.write_text(json.dumps([{"corp_name": "오래된 회사"}]), encoding="utf-8")
            stale_time = time.time() - self.server._CORP_CACHE_MAX_AGE - 1
            os.utime(cache, (stale_time, stale_time))
            refreshed = [{"corp_name": "새 회사", "corp_code": "00000001", "stock_code": ""}]

            with patch.object(self.server, "_CACHE", str(cache)), \
                    patch.object(self.server, "_CORP_MAP", None), \
                    patch.object(self.server, "_build_corp_map", return_value=refreshed) as build:
                self.assertEqual(self.server._corp_entries(), refreshed)
                build.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
