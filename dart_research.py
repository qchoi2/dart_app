#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dart_research.py
전자공시(OpenDART) 키워드 공시 사례 리서치 엔진

핵심 아이디어
--------------
OpenDART의 '공시검색(list.json)'은 회사명·보고서명·접수번호 같은 '메타데이터'만
돌려줍니다. '상계납입' 같은 표현은 공시 '본문' 안에만 있으므로, 아래 2단계로 찾습니다.

  1) list.json 으로 후보 공시 목록을 뽑는다 (예: 주요사항보고서 = 유상증자/CB/BW 결정)
  2) 각 공시의 원문(document.xml, ZIP)을 받아 본문 텍스트에서 키워드를 검색한다

사용 예
--------
  .env 파일에 DART_API_KEY=발급받은키 저장
  python dart_research.py --keyword 상계납입 --bgn 20250101 --end 20250714 \
         --report 유상증자결정 --report 전환사채 --report 신주인수권부사채 \
         --max-docs 300 --out results

의존성: 직접 검색 기능은 Python 표준 라이브러리만 사용
"""
import os
import re
import io
import csv
import json
import time
import zipfile
import argparse
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

from env_loader import load_dotenv

load_dotenv()

BASE = "https://opendart.fss.or.kr/api"
# DART 웹 문서 뷰어(사람이 클릭해서 보는 링크)
VIEWER = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={}"
MAX_SEARCH_DAYS_WITHOUT_CORP = 90


class OpenDartAPIError(RuntimeError):
    """OpenDART가 반환한 상태 코드와 메시지를 보존하는 예외."""

    def __init__(self, status, message):
        self.status = str(status or "unknown")
        self.message = str(message or "알 수 없는 오류")
        super().__init__(f"OpenDART 오류 {self.status}: {self.message}")


def get_api_key(explicit=None):
    key = explicit or os.environ.get("DART_API_KEY")
    if not key:
        raise RuntimeError(".env 파일에 DART_API_KEY를 설정하세요.")
    return key


_get_key = get_api_key


def http_get(url, timeout=30, retries=3, retry_delay=0.5):
    """일시적인 네트워크 오류와 서버 오류를 재시도해 바이트 응답을 반환한다."""
    req = urllib.request.Request(url, headers={"User-Agent": "dart-research/1.0"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read()
        except HTTPError as exc:
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if not retryable or attempt == retries - 1:
                raise RuntimeError(f"OpenDART HTTP 오류 {exc.code}") from None
        except URLError as exc:
            if attempt == retries - 1:
                raise RuntimeError(f"OpenDART 연결 실패: {exc.reason}") from None
        time.sleep(retry_delay * (2 ** attempt))
    raise RuntimeError("OpenDART 연결에 실패했습니다.")


_http_get = http_get


def _parse_date(value, field_name):
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except (TypeError, ValueError):
        raise ValueError(f"{field_name}은 YYYYMMDD 형식의 유효한 날짜여야 합니다.") from None


def date_windows(bgn_de, end_de, corp_code=None):
    """회사코드가 없을 때 검색기간을 OpenDART 제한 이내로 나눈다."""
    start = _parse_date(bgn_de, "bgn_de")
    end = _parse_date(end_de, "end_de")
    if start > end:
        raise ValueError("bgn_de는 end_de보다 늦을 수 없습니다.")
    if corp_code:
        return [(bgn_de, end_de)]

    windows = []
    cursor = start
    while cursor <= end:
        window_end = min(cursor + timedelta(days=MAX_SEARCH_DAYS_WITHOUT_CORP - 1), end)
        windows.append((cursor.strftime("%Y%m%d"), window_end.strftime("%Y%m%d")))
        cursor = window_end + timedelta(days=1)
    return windows


def _api_error(raw):
    """JSON/XML 오류 응답에서 OpenDART 상태와 메시지를 읽는다."""
    try:
        payload = json.loads(raw.decode("utf-8"))
        return payload.get("status"), payload.get("message")
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        pass
    try:
        root = ET.fromstring(raw)
        return root.findtext("status"), root.findtext("message")
    except ET.ParseError:
        return "unknown", "예상하지 못한 응답 형식입니다."


# ---------------------------------------------------------------------------
# 1단계: 공시목록 검색 (list.json)
# ---------------------------------------------------------------------------
def _search_window(key, bgn_de, end_de, pblntf_ty, corp_cls, corp_code,
                   page_count, max_pages, pause):
    items, page = [], 1
    while page <= max_pages:
        params = {
            "crtfc_key": key, "bgn_de": bgn_de, "end_de": end_de,
            "page_no": page, "page_count": page_count,
        }
        if pblntf_ty:
            params["pblntf_ty"] = pblntf_ty
        if corp_cls:
            params["corp_cls"] = corp_cls
        if corp_code:
            params["corp_code"] = corp_code
        url = BASE + "/list.json?" + urllib.parse.urlencode(params)
        data = json.loads(http_get(url))
        status = data.get("status")
        if status == "013":       # 조회된 데이터 없음
            break
        if status != "000":
            raise OpenDartAPIError(status, data.get("message"))
        items.extend(data.get("list", []))
        total_page = data.get("total_page", 1)
        if page >= total_page:
            break
        page += 1
        time.sleep(pause)
    return items


def search_list(key, bgn_de, end_de, pblntf_ty="B", corp_cls=None,
                corp_code=None, page_count=100, max_pages=100, pause=0.1):
    """
    기간 내 공시목록을 수집한다. 회사코드가 없고 기간이 3개월을 넘으면
    OpenDART 제한에 맞춰 최대 90일 구간으로 자동 분할한다.
    pblntf_ty: A=정기공시 B=주요사항보고 C=발행공시 D=지분공시 E=기타 I=거래소 ...
    corp_cls : Y=유가증권 K=코스닥 N=코넥스 E=기타 (None=전체)
    """
    if not 1 <= page_count <= 100:
        raise ValueError("page_count는 1에서 100 사이여야 합니다.")
    if max_pages < 1:
        raise ValueError("max_pages는 1 이상이어야 합니다.")
    if pblntf_ty not in (None, "", *tuple("ABCDEFGHIJ")):
        raise ValueError("pblntf_ty는 A부터 J까지의 공시유형이어야 합니다.")
    if corp_cls not in (None, "", "Y", "K", "N", "E"):
        raise ValueError("corp_cls는 Y, K, N, E 중 하나여야 합니다.")
    if corp_code and (not str(corp_code).isdigit() or len(str(corp_code)) != 8):
        raise ValueError("corp_code는 8자리 DART 고유번호여야 합니다.")

    items = []
    for window_bgn, window_end in date_windows(bgn_de, end_de, corp_code=corp_code):
        items.extend(_search_window(
            key, window_bgn, window_end, pblntf_ty, corp_cls, corp_code,
            page_count, max_pages, pause))
    items.sort(key=lambda item: (item.get("rcept_dt", ""), item.get("rcept_no", "")),
               reverse=True)
    return items


def filter_by_report_name(items, keywords):
    """보고서명(report_nm)에 keywords 중 하나라도 포함된 항목만 남긴다."""
    if not keywords:
        return items
    out = []
    for it in items:
        nm = it.get("report_nm", "")
        if any(k in nm for k in keywords):
            out.append(it)
    return out


# ---------------------------------------------------------------------------
# 2단계: 원문 다운로드 + 본문 키워드 검색 (document.xml)
# ---------------------------------------------------------------------------
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def fetch_document_text(key, rcept_no, timeout=30):
    """document.xml(ZIP) 을 받아 태그를 제거한 순수 텍스트를 돌려준다."""
    if not str(rcept_no or "").isdigit() or len(str(rcept_no)) != 14:
        raise ValueError("rcept_no는 14자리 접수번호여야 합니다.")
    url = BASE + "/document.xml?" + urllib.parse.urlencode(
        {"crtfc_key": key, "rcept_no": rcept_no})
    raw = http_get(url, timeout=timeout)
    # 정상이면 ZIP, 오류면 JSON/XML 에러메시지가 온다
    if raw[:2] != b"PK":
        status, message = _api_error(raw)
        raise OpenDartAPIError(status, message)
    text_parts = []
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for name in z.namelist():
            blob = z.read(name)
            for enc in ("utf-8", "euc-kr", "cp949"):
                try:
                    text_parts.append(blob.decode(enc))
                    break
                except UnicodeDecodeError:
                    continue
    text = "\n".join(text_parts)
    text = _TAG.sub(" ", text)      # XML/HTML 태그 제거
    text = _WS.sub(" ", text)       # 공백 정리
    return text


def snippets_for(text, keyword, span=60, max_hits=3):
    """키워드 주변 문맥 조각을 추출한다."""
    hits, start = [], 0
    for _ in range(max_hits):
        i = text.find(keyword, start)
        if i < 0:
            break
        a, b = max(0, i - span), min(len(text), i + len(keyword) + span)
        hits.append("…" + text[a:b].strip() + "…")
        start = i + len(keyword)
    return hits


# ---------------------------------------------------------------------------
# 파이프라인
# ---------------------------------------------------------------------------
def find_keyword_cases(key, keyword, bgn_de, end_de, pblntf_ty="B",
                       report_filters=None, corp_cls=None, max_docs=None,
                       pause=0.25, verbose=True, include_diagnostics=False):
    """공시목록 → 원문검색 → 키워드 매칭 사례 리스트 반환."""
    keyword = str(keyword or "").strip()
    if not keyword:
        raise ValueError("keyword는 비어 있을 수 없습니다.")
    if max_docs is not None and max_docs < 1:
        raise ValueError("max_docs는 1 이상이어야 합니다.")
    if verbose:
        print(f"[1/3] 공시목록 조회 {bgn_de}~{end_de} (pblntf_ty={pblntf_ty}) ...")
    items = search_list(key, bgn_de, end_de, pblntf_ty=pblntf_ty, corp_cls=corp_cls)
    if verbose:
        print(f"      → {len(items):,}건 수집")

    items = filter_by_report_name(items, report_filters or [])
    if verbose and report_filters:
        print(f"[2/3] 보고서명 필터({report_filters}) → {len(items):,}건")

    if max_docs:
        items = items[:max_docs]

    results, failures = [], []
    if verbose:
        print(f"[3/3] 원문 {len(items):,}건에서 '{keyword}' 검색 ...")
    for n, it in enumerate(items, 1):
        rcept = it.get("rcept_no")
        try:
            text = fetch_document_text(key, rcept)
        except Exception as e:
            failures.append({"rcept_no": rcept, "error": str(e)})
            if verbose:
                print(f"  ! {rcept} 다운로드 실패: {e}")
            continue
        if keyword in text:
            results.append({
                "corp_name": it.get("corp_name"),
                "corp_code": it.get("corp_code"),
                "stock_code": it.get("stock_code"),
                "corp_cls": it.get("corp_cls"),
                "report_nm": it.get("report_nm"),
                "rcept_no": rcept,
                "rcept_dt": it.get("rcept_dt"),
                "flr_nm": it.get("flr_nm"),
                "url": VIEWER.format(rcept),
                "snippets": snippets_for(text, keyword),
            })
            if verbose:
                print(f"  ✓ [{len(results)}] {it.get('corp_name')} | {it.get('report_nm')} ({it.get('rcept_dt')})")
        if verbose and n % 25 == 0:
            print(f"    ...{n}/{len(items)} 진행")
        time.sleep(pause)   # OpenDART 호출 예의(과도한 호출 방지)
    if include_diagnostics:
        return {
            "results": results,
            "summary": {
                "candidates": len(items),
                "processed": len(items) - len(failures),
                "matched": len(results),
                "failed": len(failures),
            },
            "failures": failures[:20],
        }
    return results


def save(results, out_prefix):
    output_dir = os.path.dirname(os.path.abspath(out_prefix))
    os.makedirs(output_dir, exist_ok=True)
    with open(out_prefix + ".json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    with open(out_prefix + ".csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["회사명", "보고서명", "접수일", "제출인", "접수번호", "DART링크", "본문발췌"])
        for r in results:
            w.writerow([r["corp_name"], r["report_nm"], r["rcept_dt"],
                        r["flr_nm"], r["rcept_no"], r["url"],
                        " ||| ".join(r["snippets"])])
    print(f"\n저장 완료: {out_prefix}.json / {out_prefix}.csv  (총 {len(results)}건)")


def main():
    ap = argparse.ArgumentParser(description="OpenDART 키워드 공시 사례 리서치")
    ap.add_argument("--keyword", required=True, help="본문에서 찾을 키워드 (예: 상계납입)")
    ap.add_argument("--bgn", required=True, help="시작일 YYYYMMDD")
    ap.add_argument("--end", required=True, help="종료일 YYYYMMDD")
    ap.add_argument("--pblntf-ty", default="B", help="공시유형 (기본 B=주요사항보고)")
    ap.add_argument("--report", action="append", default=[],
                    help="보고서명 필터(여러 번 사용). 예: --report 유상증자결정 --report 전환사채")
    ap.add_argument("--corp-cls", default=None, help="Y/K/N/E (미지정=전체)")
    ap.add_argument("--max-docs", type=int, default=None, help="원문 검색 최대 건수")
    ap.add_argument("--out", default="output/dart_results", help="출력 파일 접두어")
    args = ap.parse_args()

    try:
        key = get_api_key()
    except RuntimeError as exc:
        print(f"[오류] {exc}")
        return 1
    res = find_keyword_cases(
        key, args.keyword, args.bgn, args.end,
        pblntf_ty=args.pblntf_ty, report_filters=args.report,
        corp_cls=args.corp_cls, max_docs=args.max_docs)
    save(res, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
