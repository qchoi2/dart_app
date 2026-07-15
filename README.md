# OpenDART 공시 리서치

금융감독원 OpenDART에서 기업 공시와 재무정보를 찾아주는 Python 프로젝트입니다.
명령줄에서 직접 검색하거나 Claude Desktop에 MCP 서버로 연결해 자연어로 사용할 수 있습니다.

## 할 수 있는 일

- 기간별 공시 목록 검색
- 공시 원문에서 `상계납입` 같은 문구 검색
- 접수번호로 공시 본문 확인
- 회사명·종목코드로 DART 회사 고유번호 검색
- 사업보고서·분기보고서의 주요 재무항목 조회
- 검색 결과를 CSV와 JSON으로 저장

## 가장 빠른 시작

1. Python 3.10 이상을 설치합니다.
2. 이 폴더에서 `python -m pip install -r requirements.txt`를 실행합니다.
3. `.env.example`을 `.env`로 복사하고 OpenDART API 키를 입력합니다.
4. `리서치.bat`을 실행하거나 아래 명령을 사용합니다.

```powershell
python dart_research.py --keyword 상계납입 --bgn 20260101 --end 20260714 --report 유상증자결정 --max-docs 200 --out output/results
```

회사코드 없는 공시검색은 한 번에 최대 3개월까지 가능하지만, 이 프로젝트는 긴 기간을 최대 90일 단위로 자동 분할합니다.

Claude Desktop 연결을 포함한 자세한 설명은 [Windows 설치 및 사용법](Windows_설치_사용법.md)을 참고하세요.

## 주요 파일

| 파일 | 역할 |
|---|---|
| `dart_research.py` | 공시 목록·원문 검색과 결과 저장을 담당하는 공통 엔진 |
| `dart_opendart_server.py` | Claude Desktop에 제공하는 MCP 도구 5개 |
| `run_research.py` | 미리 지정한 조건으로 검색하는 간단 실행기 |
| `merge_config.py` | Claude Desktop 설정을 백업하고 OpenDART 서버를 등록 |
| `env_loader.py` | 프로젝트의 `.env`를 읽는 공통 로더 |
| `리서치.bat` | 간단 실행기 시작 |
| `커넥터등록.bat` | Claude Desktop 커넥터 등록 |

## 보안

- 실제 API 키는 `.env`에만 저장합니다.
- `.env`는 Git에서 제외됩니다.
- `.env`, API 키, Claude 설정 파일을 다른 사람에게 전달하지 마세요.

## 테스트

```powershell
python -m unittest discover -s tests -v
```
