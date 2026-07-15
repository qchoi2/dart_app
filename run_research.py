# -*- coding: utf-8 -*-
"""
run_research.py - 사용자 PC에서 직접 실행하는 상계납입 리서치 러너.
한글 문자열은 이 .py 안에만 두어(파이썬이 UTF-8로 안전하게 읽음) 배치 인코딩 문제를 피한다.
"""
import os
import json
import dart_research as dr

# ---- 검색 조건 (필요하면 여기 값만 바꾸면 됩니다) ----
KEYWORD = "상계납입"
BGN = "20260101"        # 시작일 YYYYMMDD
END = "20260714"        # 종료일 YYYYMMDD
REPORTS = ["유상증자결정", "전환사채", "신주인수권부사채"]
MAX_DOCS = 200          # 원문을 열어볼 최대 건수
OUT = "상계납입_결과"     # 결과 파일 이름(확장자 제외)
# --------------------------------------------------


def load_key():
    # 설치 때 저장된 Claude 설정에서 키를 재사용 (별도 노출 방지)
    try:
        p = os.path.join(os.environ["APPDATA"], "Claude", "claude_desktop_config.json")
        with open(p, encoding="utf-8") as f:
            cfg = json.load(f)
        k = cfg["mcpServers"]["opendart"]["env"]["DART_API_KEY"]
        if k:
            return k
    except Exception:
        pass
    return os.environ.get("DART_API_KEY", "")


def main():
    key = load_key()
    if not key:
        print("[오류] API 키를 찾지 못했습니다.")
        return
    print(f"검색: '{KEYWORD}'  기간 {BGN}~{END}  대상 {REPORTS}  (최대 {MAX_DOCS}건)")
    print("DART에서 공시를 조회하고 원문을 검색합니다. 수 분 걸릴 수 있어요...\n")
    res = dr.find_keyword_cases(
        key, KEYWORD, BGN, END,
        report_filters=REPORTS, max_docs=MAX_DOCS, verbose=True)
    dr.save(res, OUT)
    print(f"\n총 {len(res)}건의 '{KEYWORD}' 사례를 찾았습니다.")
    print(f"결과 파일: {OUT}.csv / {OUT}.json")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[예외] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
