import subprocess
import re
import json
import sys
import os

# 전원 구성 GUID
SUBGROUP_BUTTONS = "4f971e89-eebd-4455-a8de-9e59040e7347"
SETTING_LID = "5ca83367-6e45-459f-a27b-476b1d01c936"

# 절전 구성 GUID
SUBGROUP_SLEEP = "238c9fa8-0aad-41ed-83f4-97be242c8f20"
SETTING_SLEEP_TIMEOUT = "29f6c1db-86da-48c5-9fdb-f2b67b1f44da"

BACKUP_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "power_backup.json")

def run_cmd(args):
    """명령을 실행하고 표준 출력을 반환합니다."""
    try:
        # 간단한 캡처 사용, 오류 무시하고 디코드
        result = subprocess.run(args, capture_output=True, check=True)
        # STT.bat에서 chcp 65001을 사용하므로 UTF-8 우선 시도
        try:
            return result.stdout.decode('utf-8')
        except UnicodeDecodeError:
            try:
                return result.stdout.decode('cp949') 
            except:
                return result.stdout.decode('utf-8', errors='ignore')
    except subprocess.CalledProcessError as e:
        print(f"명령 실행 오류 {' '.join(args)}: {e}")
        return ""

def get_active_scheme():
    """활성 전원 구성표의 GUID를 가져옵니다."""
    output = run_cmd(["powercfg", "/getactivescheme"])
    match = re.search(r"GUID:\s+([a-f0-9\-]+)", output, re.IGNORECASE)
    if match:
        return match.group(1)
    return None

def get_setting_state(scheme, subgroup, setting_guid):
    """
    특정 설정을 조회하여 AC 및 DC 값을 가져옵니다.
    반환값: {'ac': val, 'dc': val} 또는 찾지 못한 경우 None
    """
    # powercfg /q 는 계층적 정보를 출력합니다.
    # 모든 케이스에 대한 복잡한 상태 머신 없이 올바르게 구문 분석하기 위해,
    # /q [Scheme_GUID] [Subgroup_GUID] 를 사용하여 출력을 이격합니다.
    # 일부 히든 설정(덮개 등)을 찾기 위해 /qh (query hidden) 사용
    output = run_cmd(["powercfg", "/qh", scheme, subgroup])
    
    lines = output.splitlines()
    found_guid = False
    
    ac_val = None
    dc_val = None
    
    for line in lines:
        line = line.strip()
        
        # 설정 GUID 찾기
        if setting_guid.lower() in line.lower() and "GUID" in line:
            found_guid = True
            
        if found_guid:
            if "GUID" in line and setting_guid.lower() not in line.lower():
                # "GUID 별칭" (GUID Alias) 줄은 새로운 설정의 시작이 아니므로 무시
                if "별칭" in line or "Alias" in line:
                    pass
                else:
                    break
                
             # AC/DC 인덱스 파싱
            if "AC" in line and ("Index" in line or "인덱스" in line or "색인" in line):
                m = re.search(r"(0x[0-9a-fA-F]+|\d+)\s*$", line)
                if m:
                    val_str = m.group(1)
                    ac_val = int(val_str, 16) if val_str.startswith("0x") else int(val_str)
                    
            if "DC" in line and ("Index" in line or "인덱스" in line or "색인" in line):
                m = re.search(r"(0x[0-9a-fA-F]+|\d+)\s*$", line)
                if m:
                    val_str = m.group(1)
                    dc_val = int(val_str, 16) if val_str.startswith("0x") else int(val_str)

    if ac_val is not None and dc_val is not None:
        return {'ac': ac_val, 'dc': dc_val}
        
    return None

def set_setting_value(scheme, subgroup, setting, ac_val, dc_val):
    """설정의 AC 및 DC 값을 설정합니다."""
    # AC
    subprocess.run(["powercfg", "/setacvalueindex", scheme, subgroup, setting, str(ac_val)], check=True)
    # DC
    subprocess.run(["powercfg", "/setdcvalueindex", scheme, subgroup, setting, str(dc_val)], check=True)

def apply_scheme(scheme):
    """변경 사항을 적용하기 위해 구성표를 활성화합니다."""
    subprocess.run(["powercfg", "/setactive", scheme], check=True)
    
def save_and_disable():
    print("현재 전원 설정 저장 중 (덮개 및 절전 시간)...")
    scheme = get_active_scheme()
    if not scheme:
        print("오류: 활성 전원 구성표를 확인할 수 없습니다.")
        return

    if os.path.exists(BACKUP_FILE):
        print(f"  백업 파일 '{BACKUP_FILE}'이(가) 이미 존재합니다.")
        print("  원래 설정을 보존하기 위해 새로운 백업을 건너뜁니다.")
    else:
        current_state = {
            "scheme": scheme,
            "settings": {}
        }
        
        # 1. 덮개 설정 캡처 (하위 그룹: 단추)
        lid_state = get_setting_state(scheme, SUBGROUP_BUTTONS, SETTING_LID)
        if lid_state:
            current_state["settings"]["Lid"] = {
                "subgroup": SUBGROUP_BUTTONS,
                "guid": SETTING_LID,
                "ac": lid_state['ac'],
                "dc": lid_state['dc']
            }
            print(f"  덮개 설정 캡처됨: AC={lid_state['ac']}, DC={lid_state['dc']}")
        else:
            print("  경고: 덮개 설정을 캡처할 수 없습니다.")

        # 2. 절전 시간 설정 캡처 (하위 그룹: 절전)
        sleep_state = get_setting_state(scheme, SUBGROUP_SLEEP, SETTING_SLEEP_TIMEOUT)
        if sleep_state:
            current_state["settings"]["SleepTimeout"] = {
                "subgroup": SUBGROUP_SLEEP,
                "guid": SETTING_SLEEP_TIMEOUT,
                "ac": sleep_state['ac'],
                "dc": sleep_state['dc']
            }
            print(f"  절전 시간 설정 캡처됨: AC={sleep_state['ac']}, DC={sleep_state['dc']}")
        else:
            print("  경고: 절전 시간 설정을 캡처할 수 없습니다.")

        # 파일로 저장
        try:
            with open(BACKUP_FILE, "w") as f:
                json.dump(current_state, f, indent=4)
            print(f"  백업이 {BACKUP_FILE}에 저장되었습니다")
        except Exception as e:
            print(f"백업 파일 저장 오류: {e}")
            return

    # 3. 설정 수정
    # 덮개 -> 아무것도 안 함 (0)
    print("  덮개 동작을 '아무것도 안 함'으로 설정 중...")
    try:
        set_setting_value(scheme, SUBGROUP_BUTTONS, SETTING_LID, 0, 0)
    except Exception as e:
        print(f"  덮개 설정 오류: {e}")
        
    # 절전 시간 -> 해당 없음 (0)
    print("  절전 시간을 '해당 없음'(0)으로 설정 중...")
    try:
        set_setting_value(scheme, SUBGROUP_SLEEP, SETTING_SLEEP_TIMEOUT, 0, 0)
    except Exception as e:
        print(f"  절전 시간 설정 오류: {e}")

    apply_scheme(scheme)
    print("전원 설정이 업데이트되었습니다.")

def restore():
    print("백업에서 전원 설정을 복원 중...")
    if not os.path.exists(BACKUP_FILE):
        print(f"오류: 백업 파일 {BACKUP_FILE}을 찾을 수 없습니다.")
        return

    try:
        with open(BACKUP_FILE, "r") as f:
            backup = json.load(f)
    except Exception as e:
        print(f"백업 파일 읽기 오류: {e}")
        return

    scheme = backup.get("scheme")
    if not scheme:
        print("오류: 백업에 구성표 GUID가 없습니다.")
        return
        
    settings = backup.get("settings", {})
    
    for name, data in settings.items():
        subgroup = data.get("subgroup")
        guid = data.get("guid")
        ac = data.get("ac")
        dc = data.get("dc")
        
        if subgroup and guid and ac is not None and dc is not None:
            print(f"  복원 중 {name}: AC={ac}, DC={dc}")
            try:
                set_setting_value(scheme, subgroup, guid, ac, dc)
            except Exception as e:
                print(f"  {name} 복원 오류: {e}")
        else:
            print(f"  {name} 건너뜀 (데이터 불완전)")
            
    apply_scheme(scheme)
    print("전원 설정이 복원되었습니다.")
    
    # 백업 파일 정리
    try:
        os.remove(BACKUP_FILE)
        print(f"백업 파일 {BACKUP_FILE} 삭제됨.")
    except Exception as e:
        print(f"경고: 백업 파일 삭제 실패: {e}")

def main():
    if len(sys.argv) < 2:
        print("사용법: python power_control.py [save|restore]")
        return
    
    mode = sys.argv[1].lower()
    if mode == "save":
        save_and_disable()
    elif mode == "restore":
        restore()
    else:
        print(f"알 수 없는 모드: {mode}")

if __name__ == "__main__":
    main()
