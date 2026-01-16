import os

def get_avg_speed(log_path=None):
    if log_path is None:
        log_path = os.path.join(os.path.dirname(__file__), "stt_speed.log")

    if not os.path.exists(log_path):
        return None
    total_audio_len = 0
    total_duration = 0
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                try:
                    audio_len = float(parts[1])
                    duration = float(parts[2])
                    if duration > 0:
                        total_audio_len += audio_len
                        total_duration += duration
                except Exception:
                    continue
    if total_duration > 0:
        return total_audio_len / total_duration
    return None

def get_audio_duration(filepath):
    import subprocess
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of",
            "default=noprint_wrappers=1:nokey=1", filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        seconds = float(result.stdout.strip())
        return seconds
    except Exception:
        return None
    
from pydub import AudioSegment, silence

def trim_trailing_silence(input_path, output_path, silence_thresh=-40, min_silence_len=1000):
    """
    오디오 파일의 끝부분에 있는 무음 구간을 잘라냅니다.
    마지막 부분의 무음이 min_silence_len (ms)보다 길 경우에만 자릅니다.
    잘라냈으면 True, 아니면(또는 에러 발생 시) False를 반환합니다.
    """
    try:
        audio = AudioSegment.from_file(input_path)
        # Find non-silent ranges
        nonsilence = silence.detect_nonsilent(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh)
        if not nonsilence:
            return False
        # Get the last non-silent end
        start, end = nonsilence[0][0], nonsilence[-1][1]
        # If the last part is silence, trim it
        if end < len(audio):
            trimmed = audio[:end]
            trimmed.export(output_path, format=input_path.split('.')[-1])
            return True
        return False
    except Exception as e:
        print(f"[WARN] Failed to trim silence: {e}")
        return False

from optimum.intel import OVModelForSpeechSeq2Seq
from transformers import AutoProcessor, pipeline
import os
import torch
import glob
import time

# transformers 경고/안내 메시지 숨기기
import logging; logging.getLogger("transformers").setLevel(logging.ERROR)

# 모든 경고 무시
import warnings; warnings.filterwarnings("ignore")

# === 설정 ===
MODEL_ID = "openai/whisper-large-v3-turbo"

def main():
    # 1. 현재 폴더에서 audio/video 파일 모두 찾기
    print("현재 디렉토리에서 오디오/비디오 파일을 찾는 중입니다...")
    target_extensions = ["*.mp3", "*.mp4", "*.wav", "*.m4a"]
    files_dir = "files"
    results_dir = "results"
    files = []
    
    if not os.path.exists(files_dir):
        print(f"'{files_dir}' 디렉토리가 없습니다. 생성 중...")
        os.makedirs(files_dir)
        print(f"'{files_dir}' 디렉토리에 오디오/비디오 파일을 넣어주세요.")
        return

    if not os.path.exists(results_dir):
        print(f"'{results_dir}' 생성 중...")
        os.makedirs(results_dir)

    for ext in target_extensions:
        # files 폴더 내의 파일 검색
        search_pattern = os.path.join(files_dir, ext)
        files.extend(glob.glob(search_pattern))

    # 중복 제거 및 정렬 (혹시 모를 중복 방지)
    files = sorted(list(set(files)))

    if not files:
        print("현재 디렉토리에 오디오/비디오 파일이 없습니다.")
        return

    print(f"     발견된 파일: {len(files)}개")
    for f in files:
        print(f"   - {f}")
    print("\n" + "="*50)


    # 2. 모델 로드 (GPU → NPU → CPU 순서로 자동 fallback)
    print(f"[모델 로딩] Intel GPU → NPU → CPU 순서로 시도 중...")
    device_priority = ["GPU", "NPU", "CPU"]
    model = None
    last_error = None
    openvino_dir = "model/whisper-large-v3-turbo-openvino-int8"
    model_loaded = False
    for device in device_priority:
        try:
            print(f"  시도 중인 장치: {device}")
            # OpenVINO 변환 모델이 있으면 바로 로드, 없으면 변환 후 저장
            if os.path.exists(openvino_dir):
                model = OVModelForSpeechSeq2Seq.from_pretrained(openvino_dir, device_map=device)
                print(f"  {openvino_dir}에서 OpenVINO 모델 로드됨")
            else:
                model = OVModelForSpeechSeq2Seq.from_pretrained(
                    MODEL_ID,
                    export=True,
                    compile=False,
                    device_map=device,
                    load_in_8bit=True,
                )
                model.save_pretrained(openvino_dir)
                print(f"  OpenVINO 모델 변환 및 저장됨: {openvino_dir}")
            processor = AutoProcessor.from_pretrained(MODEL_ID)
            pipe = pipeline(
                "automatic-speech-recognition",
                model=model,
                tokenizer=processor.tokenizer,
                feature_extractor=processor.feature_extractor,
                max_new_tokens=128,
                chunk_length_s=5,
                batch_size=2,
                ignore_warning=True,
                use_fast=True,
            )
            print(f"  성공: 모델이 {device}에 로드되었습니다")
            model_loaded = True
            break
        except Exception as e:
            print(f"  {device}에서 실패: {e}")
            last_error = e
            model = None
    if not model_loaded:
        print(f"\n모든 장치에서 모델 로드 실패: {last_error}")
        return

    print("모델 로드 완료. 변환을 시작합니다.")
    print("="*50 + "\n")

    # 3. 파일 하나씩 순서대로 변환
    import subprocess
    import shutil
    for idx, filename in enumerate(files):
        file_base_name = os.path.splitext(os.path.basename(filename))[0]
        output_filename = os.path.join(results_dir, f"{file_base_name}.txt")
        
        print(f"\n[{idx+1}/{len(files)}] === 처리 중: {filename} ===")
        start_time = time.time()

        # 영상 말미 무음 구간 트리밍
        # 기본 입력 파일 설정
        input_for_pipe = filename

        # 영상 말미 무음 구간 트리밍
        ext = os.path.splitext(filename)[1].lower()
        temp_trimmed = None
        if ext in [".mp3", ".wav", ".m4a"]:
            temp_trimmed = os.path.join(results_dir, f"{file_base_name}_trimmed{ext}")
            trimmed = trim_trailing_silence(filename, temp_trimmed)
            if trimmed:
                print(f"     [TRIM] 끝부분 무음 구간 제거됨: {temp_trimmed}")
                input_for_pipe = temp_trimmed

        # (분석 전) 예상 소요 시간 계산 (현재 파일 기준)
        avg_speed = get_avg_speed()
        cur_dur = get_audio_duration(input_for_pipe)

        import datetime
        now = datetime.datetime.now()
        
        if cur_dur and cur_dur > 0:
            if avg_speed:
                est_time = cur_dur / avg_speed
                est_min = round(est_time / 60, 1) # 소수점 첫째자리까지 표시
                
                # 예상 종료 시간 (현재 파일)
                end_time = now + datetime.timedelta(seconds=int(est_time))
                end_time_str = end_time.strftime('%H:%M')
                print(f"     [ETA] 현재 파일: 약 {est_min}분 (종료 예정: {end_time_str})")
            else:
                # 평균 속도 데이터가 없을 경우 (첫 실행 등)
                print(f"     [ETA] 계산 중... (오디오 길이: {round(cur_dur/60, 1)}분)")
        else:
             print(f"     [ETA] Unknown (길이 확인 실패)")

        # mp4, m4a 등 비오디오 파일은 wav로 변환
        ext = os.path.splitext(filename)[1].lower()
        temp_wav = None
        # input_for_pipe는 위에서 설정됨 (trimmed or original)
        if ext in [".mp4", ".m4a"]:
            temp_wav = os.path.join(results_dir, f"{file_base_name}_temp.wav")
            cmd = [
                "ffmpeg", "-y", "-i", input_for_pipe,
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", temp_wav
            ]
            print(f"     [Step 1] 비디오를 wav로 추출 중...")
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if not os.path.exists(temp_wav):
                    print(f"     [Error] ffmpeg 실패: {result.stderr}")
                    raise RuntimeError(f"ffmpeg failed: {result.stderr}")
                print(f"     [Step 1] 오디오 추출됨: {temp_wav}")
                input_for_pipe = temp_wav
            except Exception as e:
                print(f"     [Error] {filename}에서 오디오 추출 실패: {e}\n")
                continue

        print(f"     [Step 2] 음성 텍스트 변환 실행 중...")
        try:
            # prompt_text를 token ids로 변환 로직 제거됨
            
            generate_kwargs = {
                "language": "korean",
            }
            result = pipe(input_for_pipe, generate_kwargs=generate_kwargs)
            print(f"     [Step 2] 변환 완료.")
            print(f"     [Step 3] 결과를 {output_filename}에 저장 중 ...")

            # 특정 query가 포함된 문장 모두 제거
            # 제거할 문구 파일에서 불러오기
            # src 폴더의 상위 폴더(배치 파일 있는 곳)에서 찾기
            query_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "removal queries.txt")
            query = []
            if os.path.exists(query_file):
                with open(query_file, "r", encoding="utf-8") as qf:
                    # 빈 줄이나 주석(#) 제외하고 읽기
                    query = []
                    for line in qf:
                        stripped = line.strip()
                        if not stripped:
                            continue
                        if stripped.startswith("#"):
                            continue
                        query.append(stripped)
            else:
                print(f"     [Warning] '{query_file}' 파일을 찾을 수 없습니다. 문장이 제거되지 않습니다.")

            def contains_any_keyword(sentence, query):
                return any(keyword in sentence for keyword in query)

            sentences = [s.strip() for s in result["text"].split('.') if not contains_any_keyword(s, query)]
            filtered_text = '. '.join(sentences).strip()
            with open(output_filename, "w", encoding="utf-8") as f:
                f.write(filtered_text)
            end_time = time.time()
            duration = end_time - start_time

            # 오디오 길이(초) 추출 (ffprobe 사용)
            audio_path = input_for_pipe
            audio_duration = get_audio_duration(audio_path)
            if audio_duration:
                log_line = f"{filename}\t{audio_duration:.2f}\t{duration:.2f}\n"
                log_path = os.path.join(os.path.dirname(__file__), "stt_speed.log")
                with open(log_path, "a", encoding="utf-8") as logf:
                    logf.write(log_line)
                print(f"     [Log] {audio_duration:.2f}초 / {duration:.2f}초 (기록됨)")
            else:
                print(f"     [Log] 오디오 길이를 가져오지 못했습니다 (기록 안 됨)")

            duration_m, duration_s = divmod(int(duration), 60)
            print(f"     [Log] Log 저장됨: {output_filename} (소요시간: {duration_m}분 {duration_s}초)\n")
        except Exception as e:
            print(f"     [Error] 변환 실패 ({filename}): {e}\n")
        finally:
            # 임시 wav 파일 삭제
            if temp_wav and os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                    print(f"     [Clean Up] 임시 wav 삭제됨: {temp_wav}")
                except Exception:
                    print(f"     [Warning] 임시 wav 삭제 실패: {temp_wav}")
            # 임시 trimmed 파일 삭제
            if 'temp_trimmed' in locals() and temp_trimmed and os.path.exists(temp_trimmed):
                try:
                    os.remove(temp_trimmed)
                    print(f"     [Clean Up] 임시 trimmed 파일 삭제됨: {temp_trimmed}")
                except Exception:
                    print(f"     [Warning] 임시 trimmed 파일 삭제 실패: {temp_trimmed}")

    print("="*50)
    print("모두 완료되었습니다.")

if __name__ == "__main__":
    main()