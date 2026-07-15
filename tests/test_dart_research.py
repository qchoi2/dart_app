import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from unittest.mock import patch

import dart_research as dr


class DateWindowTests(unittest.TestCase):
    def test_long_range_is_split_into_contiguous_90_day_windows(self):
        windows = dr.date_windows("20260101", "20260714")

        self.assertGreater(len(windows), 1)
        self.assertEqual(windows[0][0], "20260101")
        self.assertEqual(windows[-1][1], "20260714")
        for index, (start, end) in enumerate(windows):
            start_date = datetime.strptime(start, "%Y%m%d").date()
            end_date = datetime.strptime(end, "%Y%m%d").date()
            self.assertLessEqual((end_date - start_date).days + 1, 90)
            if index:
                previous_end = datetime.strptime(windows[index - 1][1], "%Y%m%d").date()
                self.assertEqual((start_date - previous_end).days, 1)

    def test_corp_code_keeps_one_window(self):
        self.assertEqual(
            dr.date_windows("20250101", "20251231", corp_code="00126380"),
            [("20250101", "20251231")])

    def test_invalid_or_reversed_dates_are_rejected(self):
        with self.assertRaises(ValueError):
            dr.date_windows("20260230", "20260301")
        with self.assertRaises(ValueError):
            dr.date_windows("20260302", "20260301")


class SearchTests(unittest.TestCase):
    def test_missing_api_key_raises_regular_runtime_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                dr.get_api_key()

    @patch("dart_research.urllib.request.urlopen")
    def test_network_error_is_retried_and_sanitized(self, urlopen):
        urlopen.side_effect = URLError("temporary failure")

        with self.assertRaisesRegex(RuntimeError, "OpenDART 연결 실패") as context:
            dr.http_get("https://example.invalid/?crtfc_key=secret", retries=2, retry_delay=0)

        self.assertNotIn("secret", str(context.exception))
        self.assertEqual(urlopen.call_count, 2)

    @patch("dart_research._search_window")
    def test_search_list_combines_windows_and_sorts_newest_first(self, search_window):
        search_window.side_effect = [
            [{"rcept_dt": "20260101", "rcept_no": "20260101000001"}],
            [{"rcept_dt": "20260401", "rcept_no": "20260401000001"}],
        ]

        items = dr.search_list("key", "20260101", "20260401")

        self.assertEqual([item["rcept_dt"] for item in items], ["20260401", "20260101"])
        self.assertEqual(search_window.call_count, 2)

    @patch("dart_research.fetch_document_text")
    @patch("dart_research.search_list")
    def test_keyword_search_reports_partial_failures(self, search_list, fetch_text):
        search_list.return_value = [
            {"rcept_no": "20260101000001", "corp_name": "가", "report_nm": "보고서"},
            {"rcept_no": "20260101000002", "corp_name": "나", "report_nm": "보고서"},
        ]
        fetch_text.side_effect = ["앞 상계납입 뒤", RuntimeError("열람 제한")]

        report = dr.find_keyword_cases(
            "key", "상계납입", "20260101", "20260102",
            pause=0, verbose=False, include_diagnostics=True)

        self.assertEqual(report["summary"], {
            "candidates": 2, "processed": 1, "matched": 1, "failed": 1})
        self.assertEqual(len(report["results"]), 1)
        self.assertEqual(report["failures"][0]["rcept_no"], "20260101000002")

    @patch("dart_research.http_get")
    def test_document_api_error_is_not_hidden(self, http_get):
        http_get.return_value = json.dumps(
            {"status": "014", "message": "파일이 존재하지 않습니다."}).encode()

        with self.assertRaises(dr.OpenDartAPIError) as context:
            dr.fetch_document_text("key", "20260101000001")

        self.assertEqual(context.exception.status, "014")

    def test_empty_keyword_and_invalid_limits_are_rejected(self):
        with self.assertRaises(ValueError):
            dr.find_keyword_cases("key", " ", "20260101", "20260102")
        with self.assertRaises(ValueError):
            dr.find_keyword_cases("key", "상계", "20260101", "20260102", max_docs=0)
        with self.assertRaises(ValueError):
            dr.search_list("key", "20260101", "20260102", corp_code="123")

    def test_save_creates_output_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / "nested" / "results"

            with patch("builtins.print"):
                dr.save([], str(prefix))

            self.assertTrue(prefix.with_suffix(".csv").exists())
            self.assertTrue(prefix.with_suffix(".json").exists())


if __name__ == "__main__":
    unittest.main()
