# -*- coding: utf-8 -*-
"""
앱이 실제로 읽는 MSIX 설정 파일에 opendart 서버를 병합한다.
(기존 커넥터는 보존, 백업 생성, 결과를 dart 폴더로 복사해 검증 가능하게 함)
"""
import os
import json
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "dart_opendart_server.py").replace("\\", "/")
PY = r"C:\Users\3100025\AppData\Local\Programs\Python\Python312\python.exe".replace("\\", "/")

# 앱이 실제로 읽는 설정 파일 (찾기.bat 로 확인된 경로)
REAL = r"C:\Users\3100025\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json"

# 이전에 넣어둔(엉뚱한 위치) 설정에서 키를 재사용
OLD = os.path.join(os.environ.get("APPDATA", ""), "Claude", "claude_desktop_config.json")


def get_key():
    for p in (REAL, OLD):
        try:
            with open(p, encoding="utf-8") as f:
                c = json.load(f)
            k = c.get("mcpServers", {}).get("opendart", {}).get("env", {}).get("DART_API_KEY")
            if k:
                return k
        except Exception:
            pass
    return ""


def main():
    print("대상 설정 파일:", REAL)
    if not os.path.exists(REAL):
        print("[!] 실제 설정 파일이 없습니다. 경로를 다시 확인해야 합니다.")
        return

    with open(REAL, "r", encoding="utf-8") as f:
        try:
            cfg = json.load(f) or {}
        except Exception:
            cfg = {}

    shutil.copy(REAL, REAL + ".bak")
    print("백업 생성:", REAL + ".bak")

    cfg.setdefault("mcpServers", {})
    before = list(cfg["mcpServers"].keys())
    cfg["mcpServers"]["opendart"] = {
        "command": PY,
        "args": [SERVER],
        "env": {"DART_API_KEY": get_key()},
    }

    with open(REAL, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    # 검증용으로 결과를 dart 폴더에 복사
    shutil.copy(REAL, os.path.join(HERE, "_real_config_after.json"))

    print("기존 서버:", before)
    print("현재 서버:", list(cfg["mcpServers"].keys()))
    print("키 등록됨:", "예" if cfg["mcpServers"]["opendart"]["env"]["DART_API_KEY"] else "아니오(비어있음)")
    print("\n완료! 이제 Claude 앱을 완전히 종료(트레이/작업관리자) 후 다시 켜세요.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print("[예외]", e)
        traceback.print_exc()
