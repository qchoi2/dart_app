#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dart_opendart_server.py  —  OpenDART 공시 리서치 MCP 서버 (단일 파일, 자체 완결형)

Claude Desktop에 연결하면 대화창에서 자연어로:
   "2025년 상반기 유상증자 중 상계납입 사례 찾아줘"
라고 하면 Claude가 실제 공시를 뒤져 회사명·접수일·DART링크·본문발췌를 정리합니다.

필요한 것:  Python 3.10+  /  pip install "mcp[cli]"
(그 외 라이브러리 불필요 — 표준 라이브러리만 사용)

Claude Desktop 설정(claude_desktop_config.json) 예시는 함께 드린 안내문 참고.
"""
import os
import re
import io
import json
import time
import zipfile
import urllib.request
import urllib.parse
from typing import Optional

from mcp.server.fastmcp import FastMCP
from env_loader import load_dotenv

load_dotenv()

BASE = "https://opendart.fss.or.kr/api"
VIEWER = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={}"
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

mcp = FastMCP("opendart")


# ----------------------------- 내부 유틸 -----------------------------
def _key() -> str:
    k = os.environ.get("DART_API_KEY")
    if not k:
        raise RuntimeError("DART_API_KEY 환경변수가 설정되어 있지 않습니다.")
    return k


def _http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "dart-mcp/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _search_list(bgn_de, end_de, pblntf_ty="B", corp_cls=None,
                 corp_code=None, page_count=100, max_pages=100, pause=0.1):
    items, page = [], 1
    while page <= max_pages:
        params = {"crtfc_key": _key(), "bgn_de": bgn_de, "end_de": end_de,
                  "page_no": page, "page_count": page_count}
        if pblntf_ty:
            params["pblntf_ty"] = pblntf_ty
        if corp_cls:
            params["corp_cls"] = corp_cls
        if corp_code:
            params["corp_code"] = corp_code
        data = json.loads(_http_get(BASE + "/list.json?" + urllib.parse.urlencode(params)))
        st = data.get("status")
        if st == "013":
            break
        if st != "000":
            raise RuntimeError(f"list.json 오류 {st}: {data.get('message')}")
        items.extend(data.get("list", []))
        if page >= data.get("total_page", 1):
            break
        page += 1
        time.sleep(pause)
    return items


def _filter_report(items, keywords):
    if not keywords:
        return items
    return [it for it in items if any(k in it.get("report_nm", "") for k in keywords)]


def _fetch_text(rcept_no, timeout=30):
    url = BASE + "/document.xml?" + urllib.parse.urlencode(
        {"crtfc_key": _key(), "rcept_no": rcept_no})
    raw = _http_get(url, timeout=timeout)
    if raw[:2] != b"PK":       # 정상이면 ZIP, 아니면 오류/열람제한
        return ""
    parts = []
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for name in z.namelist():
            blob = z.read(name)
            for enc in ("utf-8", "euc-kr", "cp949"):
                try:
                    parts.append(blob.decode(enc)); break
                except UnicodeDecodeError:
                    continue
    return _WS.sub(" ", _TAG.sub(" ", "\n".join(parts)))


def _snippets(text, keyword, span=60, max_hits=3):
    hits, start = [], 0
    for _ in range(max_hits):
        i = text.find(keyword, start)
        if i < 0:
            break
        a, b = max(0, i - span), min(len(text), i + len(keyword) + span)
        hits.append("…" + text[a:b].strip() + "…")
        start = i + len(keyword)
    return hits


# ------------------------------ MCP 도구 ------------------------------
@mcp.tool()
def search_disclosures(bgn_de: str, end_de: str, pblntf_ty: str = "B",
                       report_contains: str = "", corp_cls: str = "") -> list:
    """
    기간 내 공시 '목록'을 빠르게 검색(본문검색 아님).
    bgn_de/end_de: YYYYMMDD. pblntf_ty: A정기 B주요사항 C발행 D지분 I거래소.
    report_contains: 보고서명에 포함될 문자열(예 '유상증자결정').
    corp_cls: Y유가 K코스닥 N코넥스 (빈값=전체).
    """
    items = _search_list(bgn_de, end_de, pblntf_ty=pblntf_ty or None,
                         corp_cls=corp_cls or None)
    if report_contains:
        items = _filter_report(items, [report_contains])
    return [{"corp_name": it.get("corp_name"), "report_nm": it.get("report_nm"),
             "rcept_dt": it.get("rcept_dt"), "rcept_no": it.get("rcept_no"),
             "url": VIEWER.format(it.get("rcept_no"))} for it in items]


@mcp.tool()
def find_keyword_cases(keyword: str, bgn_de: str, end_de: str,
                       report_filters: Optional[list] = None,
                       pblntf_ty: str = "B", max_docs: int = 200) -> list:
    """
    공시 '본문'에서 keyword(예 '상계납입')가 등장하는 사례를 찾는다.
    report_filters: 후보를 줄일 보고서명 키워드(예 ['유상증자결정','전환사채']).
    max_docs: 원문을 열어볼 최대 건수(시간/호출량 제어). 각 결과에 DART링크·본문발췌 포함.
    """
    items = _search_list(bgn_de, end_de, pblntf_ty=pblntf_ty or None)
    items = _filter_report(items, report_filters or [])
    if max_docs:
        items = items[:max_docs]
    out = []
    for it in items:
        try:
            text = _fetch_text(it.get("rcept_no"))
        except Exception:
            continue
        if keyword in text:
            out.append({
                "corp_name": it.get("corp_name"), "stock_code": it.get("stock_code"),
                "report_nm": it.get("report_nm"), "rcept_dt": it.get("rcept_dt"),
                "flr_nm": it.get("flr_nm"), "rcept_no": it.get("rcept_no"),
                "url": VIEWER.format(it.get("rcept_no")),
                "snippets": _snippets(text, keyword)})
        time.sleep(0.2)
    return out


@mcp.tool()
def get_document_text(rcept_no: str, keyword: str = "") -> dict:
    """
    특정 공시(접수번호)의 본문을 가져온다. keyword를 주면 그 주변 발췌만,
    없으면 앞부분 미리보기(2000자)를 반환.
    """
    text = _fetch_text(rcept_no)
    if not text:
        return {"rcept_no": rcept_no, "error": "본문을 가져올 수 없음(열람제한 등)"}
    if keyword:
        return {"rcept_no": rcept_no, "keyword": keyword,
                "snippets": _snippets(text, keyword, max_hits=8)}
    return {"rcept_no": rcept_no, "preview": text[:2000]}


# =====================================================================
# 재무제표 조회 (회사명/종목코드 -> 고유번호 -> 정형 재무데이터)
# =====================================================================
import xml.etree.ElementTree as ET

_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_corpcode_cache.json")
_CORP_MAP = None  # {"by_stock": {...}, "by_name": {name: [entries]}, "all": [entries]}

_REPRT = {
    "사업보고서": "11011", "연간": "11011", "1분기": "11013",
    "반기": "11012", "3분기": "11014",
}
_ACCOUNT_TARGETS = {
    "매출액": ["매출액", "수익(매출액)", "영업수익", "매출"],
    "영업이익": ["영업이익", "영업이익(손실)"],
    "당기순이익": ["당기순이익", "당기순이익(손실)", "당기순손익"],
    "자산총계": ["자산총계"],
    "부채총계": ["부채총계"],
    "자본총계": ["자본총계"],
    "유동자산": ["유동자산"],
    "유동부채": ["유동부채"],
}


def _to_num(s):
    if s is None:
        return None
    s = str(s).replace(",", "").strip()
    if s in ("", "-"):
        return None
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return s


def _build_corp_map():
    """DART corpCode.xml(전체 고유번호 매핑)을 받아 캐시에 저장."""
    url = BASE + "/corpCode.xml?" + urllib.parse.urlencode({"crtfc_key": _key()})
    raw = _http_get(url, timeout=60)
    if raw[:2] != b"PK":
        raise RuntimeError("corpCode.xml 다운로드 실패")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        xml_bytes = z.read(z.namelist()[0])
    root = ET.fromstring(xml_bytes)
    entries = []
    for it in root.iter("list"):
        entries.append({
            "corp_code": (it.findtext("corp_code") or "").strip(),
            "corp_name": (it.findtext("corp_name") or "").strip(),
            "stock_code": (it.findtext("stock_code") or "").strip(),
        })
    with open(_CACHE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False)
    return entries


def _corp_entries():
    global _CORP_MAP
    if _CORP_MAP is None:
        if os.path.exists(_CACHE):
            try:
                with open(_CACHE, encoding="utf-8") as f:
                    entries = json.load(f)
            except Exception:
                entries = _build_corp_map()
        else:
            entries = _build_corp_map()
        _CORP_MAP = entries
    return _CORP_MAP


def _resolve(query):
    """회사명 또는 종목코드 -> 후보 리스트. 상장사(종목코드 보유)를 우선."""
    q = query.strip()
    ents = _corp_entries()
    # 1) 종목코드 정확 일치
    if q.isdigit() and len(q) == 6:
        hit = [e for e in ents if e["stock_code"] == q]
        if hit:
            return hit
    listed = [e for e in ents if e["stock_code"]]
    # 2) 회사명 정확 일치 (상장사 우선)
    exact = [e for e in listed if e["corp_name"] == q] or [e for e in ents if e["corp_name"] == q]
    if exact:
        return exact
    # 3) 포함 검색 (상장사 우선)
    part = [e for e in listed if q in e["corp_name"]]
    if not part:
        part = [e for e in ents if q in e["corp_name"]]
    return part[:10]


@mcp.tool()
def resolve_company(query: str) -> list:
    """
    회사명이나 종목코드로 DART 고유번호(corp_code) 후보를 찾는다.
    이름이 모호할 때 어떤 회사인지 확인용. 상장사(종목코드 보유)를 우선 반환.
    """
    return _resolve(query)


@mcp.tool()
def get_financials(company: str, year: str, report: str = "사업보고서",
                   consolidated: bool = True, full: bool = False) -> dict:
    """
    특정 회사의 재무제표 주요 항목을 숫자로 가져온다.
    company: 회사명 또는 6자리 종목코드 (예: '삼성전자' 또는 '005930')
    year: 사업연도 4자리 (예: '2024')
    report: '사업보고서'(연간) | '1분기' | '반기' | '3분기'
    consolidated: True=연결재무제표(CFS), False=별도/개별(OFS)
    full: True면 전체 계정 목록도 함께 반환
    반환: 매출액·영업이익·당기순이익·자산/부채/자본총계 등 (당기/전기/전전기).
    금액 단위는 원(KRW).
    """
    cands = _resolve(company)
    if not cands:
        return {"error": f"'{company}' 에 해당하는 회사를 찾지 못했습니다."}
    if len(cands) > 1 and not (company.isdigit() and len(company) == 6):
        # 정확 일치가 하나면 그걸로, 아니면 후보를 돌려줌
        exact = [c for c in cands if c["corp_name"] == company.strip()]
        if len(exact) == 1:
            cands = exact
        else:
            return {"ambiguous": True, "candidates": cands[:10],
                    "hint": "여러 회사가 검색됩니다. 종목코드나 정확한 회사명으로 다시 요청하세요."}
    corp = cands[0]
    reprt_code = _REPRT.get(report.strip(), "11011")

    def _call(fs_div):
        params = {"crtfc_key": _key(), "corp_code": corp["corp_code"],
                  "bsns_year": str(year), "reprt_code": reprt_code, "fs_div": fs_div}
        url = BASE + "/fnlttSinglAcntAll.json?" + urllib.parse.urlencode(params)
        return json.loads(_http_get(url))

    fs_div = "CFS" if consolidated else "OFS"
    data = _call(fs_div)
    if data.get("status") == "013" and consolidated:
        data = _call("OFS")           # 연결이 없으면 개별로 폴백
        fs_div = "OFS"
    if data.get("status") != "000":
        return {"company": corp["corp_name"], "corp_code": corp["corp_code"],
                "error": f"재무데이터 없음 ({data.get('status')}: {data.get('message')})",
                "hint": "연도/보고서 종류를 확인하세요(아직 미제출일 수 있음)."}

    rows = data.get("list", [])
    key_items = {}
    for label, targets in _ACCOUNT_TARGETS.items():
        found = None
        for t in targets:
            for r in rows:
                nm = (r.get("account_nm") or "").replace(" ", "")
                if t.replace(" ", "") == nm or t.replace(" ", "") in nm:
                    found = r
                    break
            if found:
                break
        if found:
            key_items[label] = {
                "당기": _to_num(found.get("thstrm_amount")),
                "전기": _to_num(found.get("frmtrm_amount")),
                "전전기": _to_num(found.get("bfefrmtrm_amount")),
            }

    result = {
        "company": corp["corp_name"], "corp_code": corp["corp_code"],
        "stock_code": corp["stock_code"], "year": str(year),
        "report": report, "fs_div": fs_div, "unit": "원(KRW)",
        "key": key_items,
    }
    if full:
        result["all"] = [{
            "sj": r.get("sj_nm"), "account": r.get("account_nm"),
            "당기": _to_num(r.get("thstrm_amount")),
            "전기": _to_num(r.get("frmtrm_amount")),
            "전전기": _to_num(r.get("bfefrmtrm_amount")),
        } for r in rows]
    return result


if __name__ == "__main__":
    mcp.run()
