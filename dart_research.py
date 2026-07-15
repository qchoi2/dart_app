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

의존성:  requests  (pip install requests)   /  표준 라이브러리만으로도 동작
"""
import os
import re
import io
import csv
import json
import time
import zipfile
import argparse
import urllib.request
import urllib.parse

from env_loader import load_dotenv

load_dotenv()

BASE = "https://opendart.fss.or.kr/api"
# DART 웹 문서 뷰어(사람이 클릭해서 보는 링크)
VIEWER = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={}"


def _get_key(explicit=None):
    key = explicit or os.environ.get("DART_API_KEY")
    if not key:
        raise SystemExit(".env 파일에 DART_API_KEY를 설정하거나 --key 로 전달하세요.")
    return key


def _http_get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "dart-research/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ---------------------------------------------------------------------------
# 1단계: 공시목록 검색 (list.json)
# ---------------------------------------------------------------------------
def search_list(key, bgn_de, end_de, pblntf_ty="B", corp_cls=None,
                corp_code=None, page_count=100, max_pages=100, pause=0.1):
    """
    기간 내 공시목록을 페이지네이션하여 모두 수집한다.
    pblntf_ty: A=정기공시 B=주요사항보고 C=발행공시 D=지분공시 E=기타 I=거래소 ...
    corp_cls : Y=유가증권 K=코스닥 N=코넥스 E=기타 (None=전체)
    """
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
        data = json.loads(_http_get(url))
        status = data.get("status")
        if status == "013":       # 조회된 데이터 없음
            break
        if status != "000":
            raise RuntimeError(f"list.json 오류 {status}: {data.get('message')}")
        items.extend(data.get("list", []))
        total_page = data.get("total_page", 1)
        if page >= total_page:
            break
        page += 1
        time.sleep(pause)
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
    url = BASE + "/document.xml?" + urllib.parse.urlencode(
        {"crtfc_key": key, "rcept_no": rcept_no})
    raw = _http_get(url, timeout=timeout)
    # 정상이면 ZIP, 오류면 JSON/XML 에러메시지가 온다
    if raw[:2] != b"PK":
        # 에러 메시지(예: 열람 제한 문서)일 수 있음
        return ""
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
                       pause=0.25, verbose=True):
    """공시목록 → 원문검색 → 키워드 매칭 사례 리스트 반환."""
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

    results = []
    if verbose:
        print(f"[3/3] 원문 {len(items):,}건에서 '{keyword}' 검색 ...")
    for n, it in enumerate(items, 1):
        rcept = it.get("rcept_no")
        try:
            text = fetch_document_text(key, rcept)
        except Exception as e:
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
    return results


def save(results, out_prefix):
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
    ap.add_argument("--key", default=None, help="API 키(미지정 시 DART_API_KEY 환경변수)")
    ap.add_argument("--out", default="dart_results", help="출력 파일 접두어")
    args = ap.parse_args()

    key = _get_key(args.key)
    res = find_keyword_cases(
        key, args.keyword, args.bgn, args.end,
        pblntf_ty=args.pblntf_ty, report_filters=args.report,
        corp_cls=args.corp_cls, max_docs=args.max_docs)
    save(res, args.out)


if __name__ == "__main__":
    main()
