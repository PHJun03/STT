@echo off
chcp 65001 > nul
title STT 변환기
cls

echo ========================================================
echo  Speech-to-Text (STT) 변환 시작
for /f "tokens=1,2 delims=: " %%a in ("%TIME%") do set STARTTIME=%%a:%%b
set START_H=%STARTTIME:~0,2%
set START_M=%STARTTIME:~3,2%
echo  시작 시간: %STARTTIME%
echo ========================================================
echo.

:: 1. 임베디드 파이썬 확인
if not exist "python-embed\python.exe" (
    echo [ERROR] 'python-embed' 폴더를 찾을 수 없습니다!
    echo.
    echo 이 배치 파일이 'python-embed' 폴더와
    echo 동일한 폴더에 위치해 있는지 확인해주세요.
    echo.
    pause
    exit
)

:: 3. 전원 설정 백업 및 절전 방지 ("아무 것도 안 함" 설정)
echo.
echo [전원 설정] Windows 전원 설정을 저장하고 절전 모드를 방지합니다...
python-embed\python.exe src\power_control.py save

:: 4. 파이썬 스크립트 실행
echo.
echo stt.py 실행 중...
set HF_HUB_DISABLE_SYMLINKS_WARNING=1
python-embed\python.exe src\stt.py

:: 5. 전원 설정 복구
echo.
echo [전원 설정] 전원 설정을 복원합니다...
python-embed\python.exe src\power_control.py restore

:: 4. 작업이 끝나면 창이 바로 꺼지지 않게 대기
echo.
echo ========================================================
echo  모든 작업 완료. 종료하려면 아무 키나 누르세요.
for /f "tokens=1,2 delims=: " %%a in ("%TIME%") do set ENDTIME=%%a:%%b
set END_H=%ENDTIME:~0,2%
set END_M=%ENDTIME:~3,2%

:: 소요 시간 계산
set /a ELAPSED_H=%END_H%-%START_H%
set /a ELAPSED_M=%END_M%-%START_M%
if %ELAPSED_M% lss 0 (
    set /a ELAPSED_M+=60
    set /a ELAPSED_H-=1
)
set ELAPSED=%ELAPSED_H%h %ELAPSED_M%m

echo 종료 시간: %ENDTIME%   (소요 시간: %ELAPSED%)
echo ========================================================
pause