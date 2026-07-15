# OpenDART 공시 리서치 — Windows 설치 및 사용법

이 프로젝트는 금융감독원 OpenDART에서 기업 공시와 재무정보를 검색합니다.
초보자는 `리서치.bat`으로 직접 검색할 수 있고, Claude Desktop에 연결하면 자연어로 질문할 수 있습니다.

## 1. 필요한 파일

프로젝트 폴더를 통째로 보관하세요. 특히 다음 파일은 서로 같은 폴더에 있어야 합니다.

- `dart_opendart_server.py`: Claude가 실행하는 MCP 서버
- `dart_research.py`: 공시 검색 공통 엔진
- `env_loader.py`: `.env`를 읽는 도구
- `.env`: 실제 OpenDART API 키

서버 파일 하나만 다른 폴더로 옮기면 실행되지 않습니다.

## 2. Python 설치

1. <https://www.python.org/downloads/>에서 Python 3.10 이상을 설치합니다.
2. 설치 첫 화면에서 **Add python.exe to PATH**를 체크합니다.
3. 명령 프롬프트에서 확인합니다.

```powershell
python --version
```

## 3. 필수 패키지 설치

프로젝트 폴더에서 다음 명령을 실행합니다.

```powershell
python -m pip install -r requirements.txt
```

직접 검색 기능은 Python 표준 라이브러리만 사용하지만, Claude 연결에는 `mcp` 패키지가 필요합니다.

## 4. API 키 설정

1. `.env.example` 파일을 복사해 이름을 `.env`로 바꿉니다.
2. 발급받은 OpenDART API 키를 입력합니다.

```dotenv
DART_API_KEY=여기에_발급받은_키_입력
```

`.env`는 Git에서 제외됩니다. 이 파일이나 키를 다른 사람에게 보내지 마세요.

## 5. 직접 검색하기

### 가장 쉬운 방법

`리서치.bat`을 더블클릭합니다. 검색 조건은 `run_research.py` 위쪽에서 바꿀 수 있습니다.

### 원하는 조건을 직접 입력하는 방법

```powershell
python dart_research.py --keyword 상계납입 --bgn 20260101 --end 20260714 --report 유상증자결정 --report 전환사채 --max-docs 200 --out output/results
```

긴 기간은 OpenDART 제한에 맞춰 최대 90일 단위로 자동 검색됩니다. 완료되면 다음 파일이 생성됩니다.

- `output/results.csv`: Excel에서 열기 좋은 표
- `output/results.json`: 프로그램에서 사용하기 좋은 구조화 데이터

## 6. Claude Desktop에 연결하기

### 자동 등록

1. `MCP 설치.bat`을 더블클릭합니다.
2. 스크립트가 Python 확인, API 키 확인, 패키지 설치, Claude 등록을 차례로 수행합니다.
3. `.env`가 없으면 메모장이 열립니다. API 키를 입력하고 저장한 뒤 메모장을 닫습니다.
4. 등록이 끝나면 Claude Desktop을 완전히 종료했다가 다시 실행합니다.

등록 스크립트는 현재 실행 중인 Python 경로를 사용하고, 기존 Claude 설정을 같은 폴더에 `.bak`으로 백업합니다.
설정 JSON이 손상돼 있으면 원본을 덮어쓰지 않고 중단합니다.

`커넥터등록.bat`은 패키지 설치 없이 Claude 등록만 다시 하고 싶을 때 사용합니다.

Claude 설정 위치를 직접 지정해야 한다면 먼저 환경변수를 설정한 뒤 실행합니다.

```powershell
$env:CLAUDE_CONFIG_PATH="C:/원하는/경로/claude_desktop_config.json"
python merge_config.py
```

### 수동 등록

Claude Desktop의 **Settings → Developer → Edit Config**에서 다음 항목을 추가합니다.

```json
{
  "mcpServers": {
    "opendart": {
      "command": "python",
      "args": ["C:/프로젝트/전체경로/dart_opendart_server.py"]
    }
  }
}
```

이미 다른 `mcpServers`가 있다면 `opendart` 항목만 추가합니다.

## 7. Claude에서 사용할 수 있는 도구

- `search_disclosures`: 기간별 공시 목록 검색
- `find_keyword_cases`: 공시 본문에서 특정 문구 검색
- `get_document_text`: 접수번호로 공시 본문 확인
- `resolve_company`: 회사명이나 종목코드로 회사 찾기
- `get_financials`: 사업보고서·분기보고서의 주요 재무정보 조회

질문 예시:

> 2026년 상반기 유상증자결정 공시 중 상계납입 사례를 찾아서 회사명, 접수일, DART 링크, 핵심 문구를 표로 정리해줘.

> 삼성전자의 2025년 사업보고서 기준 주요 재무정보를 보여줘.

본문 검색 결과에는 후보 수, 처리 성공 수, 일치 수, 실패 수가 함께 표시됩니다. 일부 문서가 열람 제한되거나 다운로드에 실패했는지 확인할 수 있습니다.

## 8. 문제 해결

| 증상 | 해결 방법 |
|---|---|
| `python`을 찾을 수 없음 | Python을 다시 설치하고 **Add python.exe to PATH**를 체크합니다. |
| `No module named mcp` | `python -m pip install -r requirements.txt`를 실행합니다. |
| `DART_API_KEY` 오류 | 프로젝트 폴더의 `.env` 파일과 키 값을 확인합니다. |
| Claude에서 도구가 안 보임 | Claude Desktop을 완전히 종료한 뒤 다시 실행하고 설정 경로를 확인합니다. |
| 설정 JSON 오류 | 표시된 행·열의 JSON 문법을 수정합니다. 스크립트는 손상된 설정을 덮어쓰지 않습니다. |
| 일부 공시 검색 실패 | 결과의 `summary.failed`와 `failures`를 확인합니다. 열람 제한 또는 일시적인 네트워크 문제일 수 있습니다. |
| SSL 인증서 오류 | Python과 Windows 업데이트를 적용하고 회사 보안 프로그램·프록시 설정을 확인합니다. 인증서 검증을 코드에서 끄지는 마세요. |
| 회사 검색 결과가 오래됨 | `_corpcode_cache.json`을 삭제하면 즉시 다시 받습니다. 삭제하지 않아도 7일 후 자동 갱신됩니다. |

## 9. 보안 주의사항

- API 키는 `.env`에만 저장합니다.
- Claude 설정 파일이나 백업 파일을 프로젝트 폴더에 복사하지 않습니다.
- 검색 결과에 비공개 메모를 추가했다면 공유 전에 내용을 확인합니다.
