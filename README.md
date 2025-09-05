# VSCode RIFE 워크플로 스타터

이 템플릿은 VSCode에서 **키프레임 → 저fps 비디오 → RIFE 보간 → 최종 24fps** 파이프라인을 버튼 몇 번으로 돌릴 수 있게 구성되어 있습니다.

## 사전 요구사항
- **FFmpeg** 설치
  - Windows: PowerShell에서 `winget install Gyan.FFmpeg`
  - macOS: `brew install ffmpeg`
  - Linux: 배포판 패키지 매니저 이용 (예: `sudo apt install ffmpeg`)
- **Git** 설치 (Practical-RIFE 클론용)
- **NVIDIA GPU** 사용자라면 CUDA 12.1용 Torch 권장 (tasks에 버튼 준비)

## 설치 & 최초 세팅 (VSCode)
1. 이 폴더를 VSCode로 엽니다.
2. 명령 팔레트(⇧⌘P / Ctrl+Shift+P) → **Tasks: Run Task**
3. 순서대로 실행:
   - **Create venv**
   - **Install Torch (CUDA 12.1)**  (mac의 경우 CPU 버전 설치됨)
   - **Install requirements**
   - **Clone Practical-RIFE**
4. Python 인터프리터가 `.venv`로 잡혀 있는지 확인합니다.

## 사용법 (샷 처리)
폴더 구조(예시):
```
project/
  shot_001/
    keyframes/            # 0001.png, 0002.png ...
    timing/scene.txt      # ffmpeg concat demuxer 규칙
    work/
    out/
```
`project/shot_001/timing/scene.txt` 예시:
```
file 'keyframes/0001.png'
duration 0.40
file 'keyframes/0002.png'
duration 0.60
file 'keyframes/0003.png'
duration 0.40
file 'keyframes/0003.png'
```

### 전체 파이프라인 실행
Tasks에서 **Run Full Pipeline**을 실행하고 프롬프트에 따라 입력값(shot_001, base fps, exp=auto 등)을 넣습니다.

### 단계별 실행
- **Step: Build Base Video** → 저fps 베이스 생성
- **Step: RIFE Interpolate** → RIFE로 중간 프레임 보간
- **Step: Finalize 24fps** → 최종 fps로 리샘플

## 팁
- exp 자동 계산: `exp = ceil(log2(target_fps / base_fps))`
- 큰 포즈 점프/가림 이슈는 중간 키프레임 추가가 가장 효과적
- VRAM이 부족하면 `--scale 0.5` → 업스케일러(예: Real-ESRGAN)로 복구

## 경로 규칙
- RIFE 디렉터리는 워크스페이스 루트의 `Practical-RIFE` 로 가정합니다. 다른 위치면 스크립트 실행 시 `--rife-dir` 로 지정하세요.



## 추가적인것

Files:
- scripts/pipeline_plus.py   (Hybrid pipeline entrypoint)
- scripts/kling_runner.py    (Replicate->Kling caller + downloader)
- requirements.txt           (added: replicate, requests, watchdog)

Install:
pip install -r requirements.txt
export REPLICATE_API_TOKEN=YOUR_TOKEN

Run (Kling + RIFE post):
python scripts/pipeline_plus.py --shot shot_001 --engine kling --post rife --kling-prompt "your prompt"

Run (RIFE only):
python scripts/pipeline_plus.py --shot shot_001 --engine rife
