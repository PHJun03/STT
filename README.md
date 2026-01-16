# STT 변환기 (Speech-to-Text)

오디오 및 비디오 파일을 텍스트로 변환해주는 도구입니다.

## 사용 방법 (3단계)

1. **파일 넣기**: `files` 폴더에 변환할 오디오(`mp3`, `wav`, `m4a`)나 비디오(`mp4`) 파일을 넣으세요.
2. **실행 하기**: `STT.bat` 파일을 더블 클릭하세요.
3. **확인 하기**: 작업이 끝나면 `files` 폴더에 생성된 텍스트(`txt`) 파일을 확인하세요.

---

## 필수 설치 및 환경 설정

이 프로그램은 **Windows 10 / 11**에서 작동합니다.
더 빠른 속도를 위해 **하드웨어 가속(GPU/NPU)** 사용을 권장합니다. (Intel 전용)

### 1. FFmpeg 설치
영상에서 소리를 추출하기 위해 **FFmpeg**가 필요합니다.
설치가 안 되어 있다면 아래 방법으로 설치해주세요.

1. [FFmpeg 다운로드 (gyan.dev)](https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip) 링크를 눌러 다운로드.
2. 압축을 풀고 `bin` 폴더 안에 있는 `ffmpeg.exe`를 복사합니다.
3. 이 프로그램의 `src` 폴더 또는 `C:\Windows\System32` 폴더에 붙여넣으세요. (가장 간단한 방법)

### 2. Python Embed 압축 해제
동봉된 `python-embed.zip` 파일을 압축 해제하여 `python-embed` 폴더가 생성되도록 해주세요.

### 3. 드라이버 설치
본인의 PC 사양에 맞는 드라이버를 설치해야 가속 기능이 정상 작동합니다.

*   **Intel GPU** (내장/외장 그래픽 카드)
    *   [👉 Intel® Arc™ & Iris® Xe 그래픽 드라이버 다운로드](https://www.intel.co.kr/content/www/kr/ko/download/785597/intel-arc-iris-xe-graphics-windows.html)
*   **Intel NPU** (AI 전용 프로세서, 최신 노트북 등)
    *   [👉 Intel® NPU 드라이버 다운로드](https://www.intel.com/content/www/us/en/download/794734/intel-npu-driver-windows.html)

> **참고**: 드라이버가 없으면 자동으로 가장 느린 CPU 모드로 동작합니다.

---

## 팁 (Tip)
*   **전원 관리**: 변환 중에는 PC가 절전 모드로 들어가지 않도록 자동으로 설정됩니다. (완료 후 복구됨)
*   **문구 제거**: `removal queries.txt` 파일에 제거하고 싶은 반복 멘트를 적어두면 해당 쿼리가 포함된 문장을 결과에서 자동으로 삭제됩니다.

---

## 라이선스 (License)

이 프로젝트는 **MIT License**하에 배포됩니다.  
누구나 자유롭게 복제, 수정 및 배포할 수 있으며 상업적 목적으로도 사용할 수 있습니다.  
자세한 내용은 [LICENSE](LICENSE) 파일을 확인해 주세요.

## 개발자 정보 (Developer)

*   **개발자**: 박현준
*   **소속**: 충남대학교 공과대학 전파정보통신공학과(정보통신융합학부) 23학번
*   **연락처**: [rice202301996@o.cnu.ac.kr](mailto:rice202301996@o.cnu.ac.kr)
*   **제작일**: 2026년 1월
