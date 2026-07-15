# -*- coding: utf-8 -*-
"""Claude Desktop 설정에 OpenDART MCP 서버를 안전하게 등록한다."""

import json
import os
import shutil
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
SERVER = HERE / "dart_opendart_server.py"


def find_config_path():
    """명시적 경로, 일반 설치, MSIX 설치 순서로 Claude 설정을 찾는다."""
    override = os.environ.get("CLAUDE_CONFIG_PATH")
    if override:
        return Path(override).expanduser().resolve()

    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    standard = appdata / "Claude" / "claude_desktop_config.json"
    if standard.exists():
        return standard

    local_appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    package_root = local_appdata / "Packages"
    msix_matches = list(package_root.glob(
        "Claude_*/*/Roaming/Claude/claude_desktop_config.json"))
    msix_matches += list(package_root.glob(
        "Claude_*/LocalCache/Roaming/Claude/claude_desktop_config.json"))
    existing = sorted({path.resolve() for path in msix_matches if path.is_file()},
                      key=lambda path: path.stat().st_mtime, reverse=True)
    return existing[0] if existing else standard


def load_config(path):
    """없는 설정은 새로 시작하되, 손상된 JSON은 절대 덮어쓰지 않는다."""
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as file:
            config = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Claude 설정 JSON이 올바르지 않습니다({exc.lineno}행 {exc.colno}열). "
            "파일을 수정한 뒤 다시 실행하세요.") from None
    if not isinstance(config, dict):
        raise ValueError("Claude 설정의 최상위 값은 JSON 객체여야 합니다.")
    return config


def save_config(path, config):
    """기존 파일을 백업하고 임시 파일을 거쳐 원자적으로 저장한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)
        print("백업 생성:", backup)

    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(config, file, ensure_ascii=False, indent=2)
        file.write("\n")
    os.replace(temporary, path)


def main():
    config_path = find_config_path()
    print("대상 설정 파일:", config_path)

    try:
        config = load_config(config_path)
    except ValueError as exc:
        print("[오류]", exc)
        return 1

    servers = config.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        print("[오류] mcpServers 값은 JSON 객체여야 합니다. 설정 파일을 확인하세요.")
        return 1

    before = list(servers.keys())
    servers["opendart"] = {
        "command": sys.executable,
        "args": [str(SERVER)],
    }
    save_config(config_path, config)

    print("기존 서버:", before)
    print("현재 서버:", list(servers.keys()))
    print("API 키: 프로젝트 .env 파일에서 로드")
    print("\n완료! Claude Desktop을 완전히 종료한 뒤 다시 실행하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
