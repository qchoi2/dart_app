# OpenDART MCP 서버 — Windows 설치 & 사용법

Claude Desktop에 붙여서, 대화창에서 자연어로 공시 사례를 검색하는 세팅입니다.
아래 5단계면 끝납니다. (파일: `dart_opendart_server.py` 하나만 있으면 됩니다.)

---

## STEP 1. Python 확인 / 설치

`시작 → cmd` 실행 후:

```
python --version
```

- `Python 3.10` 이상이 나오면 OK.
- "인식할 수 없는…" 오류면 <https://www.python.org/downloads/> 에서 설치하고,
  설치 첫 화면에서 **"Add python.exe to PATH" 체크** 후 설치하세요.

## STEP 2. MCP 라이브러리 설치

cmd에 붙여넣기:

```
python -m pip install "mcp[cli]"
```

(그 외 라이브러리는 필요 없습니다.)

## STEP 3. 서버 파일 저장

받은 `dart_opendart_server.py` 를 찾기 쉬운 곳에 저장하세요. 예: `C:\dart\dart_opendart_server.py`
→ 이 **전체 경로**를 다음 단계에서 씁니다.

## STEP 4. Claude Desktop 설정 파일 편집

Claude Desktop → **Settings(설정) → Developer(개발자) → Edit Config** 클릭
(그러면 `claude_desktop_config.json` 파일이 열립니다. 위치: `%APPDATA%\Claude\`)

서버 파일과 같은 폴더에 `.env` 파일을 만들고 API 키를 저장하세요.

```dotenv
DART_API_KEY=여기에_발급받은_키_입력
```

그다음 설정 파일 내용을 아래로 만들고 **경로**를 본인 값으로 바꾸세요.
(경로는 역슬래시 대신 `/` 를 쓰면 오류가 없습니다.)

```json
{
  "mcpServers": {
    "opendart": {
      "command": "python",
      "args": ["C:/dart/dart_opendart_server.py"]
    }
  }
}
```

> 이미 다른 mcpServers 항목이 있다면 `"opendart": { ... }` 블록만 그 안에 추가하세요.

저장 후 **Claude Desktop을 완전히 종료했다가 다시 실행**합니다.

## STEP 5. 작동 확인

새 대화에서 물어보세요:

> opendart 도구 연결됐어? 쓸 수 있는 도구 알려줘

`search_disclosures`, `find_keyword_cases`, `get_document_text` 3개가 보이면 성공입니다.

---

## 사용법 (자연어로 이렇게 시키면 됩니다)

- **상계납입 사례 검색**
  > 2025년 1월부터 7월까지 유상증자결정 공시 중 **상계납입** 방식 사례를 찾아서
  > 회사명 · 접수일 · DART링크 · 핵심문구 표로 정리해줘

- **전환사채 상계 발행**
  > 2025년 상반기 전환사채 발행 결정 공시에서 '상계'가 들어간 사례 찾아줘

- **주제만 바꿔서 재활용**
  > 2025년 무상감자 결정 공시 목록 뽑아줘 / 최대주주 변경 사례 찾아줘

- **특정 공시 본문 확인**
  > 접수번호 20250714000123 공시 본문에서 '상계납입' 관련 문구 보여줘

### 팁: 프로젝트에 고정 지침 넣기
Claude **프로젝트 → 커스텀 인스트럭션**에 아래처럼 적어두면 매번 형식을 설명할 필요가 없습니다.

> 공시 리서치는 opendart 도구를 사용한다. 결과는 항상
> [회사명 | 접수일 | 보고서명 | DART링크 | 핵심문구] 표로 정리하고, 건수를 함께 알려준다.
> 검색 범위가 넓으면 max_docs를 300 이하로 제한해 먼저 결과를 보여준 뒤 확장 여부를 묻는다.

---

## 잘 안 될 때

| 증상 | 해결 |
|---|---|
| 도구가 안 보임 | Claude Desktop 완전 종료 후 재실행. 설정 JSON 문법(쉼표/따옴표) 확인 |
| 서버가 시작 실패 | `"command": "python"` 을 파이썬 전체경로로 교체<br>예: `"C:/Users/이름/AppData/Local/Programs/Python/Python312/python.exe"` |
| `DART_API_KEY 없음` 오류 | 서버 파일과 같은 폴더의 `.env`에서 `DART_API_KEY` 값 확인 |
| 결과가 느림/많음 | 자연어로 "max_docs 200으로 제한해서" 라고 요청 |
| 본문이 비어있는 공시 | 열람제한 문서일 수 있음(자동 건너뜀) |

## ⚠️ 보안
API 키는 `.env`에만 넣고 코드·문서·Claude 설정에 남기지 마세요. `.env`는 Git에서 제외됩니다.
