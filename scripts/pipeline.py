#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, math, os, subprocess, sys, shutil, time
from pathlib import Path
from typing import Optional

# ----------------------------
# 공통 유틸
# ----------------------------
def run(cmd, cwd=None, check=True):
    """명령 실행. check=False면 실패해도 예외를 던지지 않고 CompletedProcess 반환."""
    print(f"[cmd] {' '.join(map(str, cmd))}")
    return subprocess.run(cmd, cwd=cwd, check=check)

def which(name: str) -> Optional[str]:
    return shutil.which(name)

def check_ffmpeg():
    if not which("ffmpeg"):
        print("ERROR: ffmpeg가 설치되어 있지 않습니다. README.md의 설치 방법을 참고하세요.", file=sys.stderr)
        sys.exit(1)

def ensure_dirs(shot_dir: Path):
    for d in ["work", "out", "timing", "keyframes"]:
        (shot_dir / d).mkdir(parents=True, exist_ok=True)

# ----------------------------
# 1) 베이스 생성
# ----------------------------
def build_base(
    shot_dir: Path,
    base_fps: int,
    width: int,
    height: int,
    mute: bool = True
) -> Path:
    """
    timing/scene.txt가 있으면 concat demuxer로, 없으면 keyframes/000*.png를 1/N fps로 묶어서
    work/base_{base_fps}fps.mp4를 만든다.
    """
    scene_txt = shot_dir / "timing" / "scene.txt"
    key_glob  = shot_dir / "keyframes" / "000*.png"
    out_path  = shot_dir / "work" / f"base_{base_fps}fps.mp4"

    # 원본 종횡비 보존, 지정 해상도 중앙 패딩, SAR=1, 8bit 4:2:0
    vf = (
        f"scale={width}:-2:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
        "setsar=1,format=yuv420p"
    )

    if scene_txt.exists():
        # scene.txt: concat demuxer 포맷이어야 함.
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(scene_txt),
            "-vf", vf,
            "-r", str(base_fps),
        ]
    else:
        # 키프레임 폴백
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(base_fps),
            "-pattern_type", "glob", "-i", str(key_glob),
            "-vf", vf,
        ]

    if mute:
        cmd += ["-an"]  # 무음 강제

    cmd += ["-pix_fmt", "yuv420p", str(out_path)]
    run(cmd, check=True)
    return out_path

# ----------------------------
# 2) 보간 파라미터
# ----------------------------
def compute_exp(base_fps: int, target_fps: int) -> int:
    if base_fps >= target_fps:
        return 0
    return math.ceil(math.log2(target_fps / base_fps))

# ----------------------------
# 3) RIFE 보간
# ----------------------------
def rife_interpolate(
    shot_dir: Path,
    exp: int,
    rife_dir: Path,
    tta: bool=False,
    uhd: bool=False,
    scale: float=1.0
):
    work = shot_dir / "work"
    # 가장 최신 base_*fps.mp4 선택
    base_candidates = sorted(work.glob("base_*fps.mp4"), key=os.path.getmtime)
    base_video = base_candidates[-1] if base_candidates else None
    if base_video is None:
        print("ERROR: work/에 base_*fps.mp4 가 없습니다. 먼저 베이스를 생성하세요.", file=sys.stderr)
        sys.exit(1)

    # base_XXfps 로부터 XX 추출
    try:
        input_fps = int(base_video.stem.split("_")[1].replace("fps", ""))
    except Exception:
        # 실패 시 기본 1fps 가정
        input_fps = 1

    out_fps  = input_fps * (2 ** exp)
    out_path = work / f"rife_{out_fps}fps.mp4"
    noa_path = work / f"rife_{out_fps}fps_noaudio.mp4"  # Practical-RIFE가 실패 시 남기는 파일명

    inf_py = rife_dir / "inference_video.py"
    model_dir = rife_dir / "train_log"
    if not inf_py.exists():
        print(f"ERROR: {inf_py} 를 찾을 수 없습니다. Practical-RIFE가 올바르게 존재하는지 확인하세요.", file=sys.stderr)
        sys.exit(1)
    if not model_dir.exists():
        print(f"ERROR: {model_dir} 를 찾을 수 없습니다. RIFE 모델(train_log)이 필요합니다.", file=sys.stderr)
        sys.exit(1)

    cmd = [
        sys.executable, str(inf_py),
        "--video",  str(base_video),
        "--exp",    str(exp),
        "--model",  str(model_dir),
        "--output", str(out_path),
    ]
    if tta:
        cmd += ["--tta", "1"]
    if uhd:
        cmd += ["--UHD"]
    if scale != 1.0:
        cmd += ["--scale", str(scale)]

    # RIFE는 오디오 병합 단계에서 실패해도 비디오(_noaudio)를 만들어 두고 0/비0 종료를 할 수 있다.
    # 실패를 무시(check=False)하고, 산출물 존재 여부로 판단한다.
    run(cmd, check=False)

    # 산출물 정리: _noaudio가 있으면 표준 이름으로 교체
    if noa_path.exists():
        try:
            noa_path.replace(out_path)
        except Exception:
            # 같은 파일시스템이 아닐 때 대비
            shutil.move(str(noa_path), str(out_path))

    if not out_path.exists():
        print("ERROR: RIFE 보간 산출물이 보이지 않습니다. 위 로그를 확인하세요.", file=sys.stderr)
        sys.exit(1)

    return out_path, out_fps

# ----------------------------
# 4) 최종 렌더
# ----------------------------
def finalize(shot_dir: Path, target_fps: int, speed: float = 1.0, crf: int = 17, preset: str = "slow"):
    """
    setpts={speed}*PTS 로 재생속도/길이를 조절하고 최종 target_fps로 리샘플.
    항상 무음(-an)으로 출력.
    """
    work = shot_dir / "work"
    out_dir = shot_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    rife_candidates = sorted(work.glob("rife_*fps.mp4"), key=os.path.getmtime)
    rife_video = rife_candidates[-1] if rife_candidates else None
    if rife_video is None:
        print("ERROR: work/에 rife_*fps.mp4 가 없습니다. 먼저 RIFE 보간을 실행하세요.", file=sys.stderr)
        sys.exit(1)

    out_path = out_dir / f"final_{target_fps}fps.mp4"
    vf = f"setpts={speed}*PTS,fps={target_fps}" if speed != 1.0 else f"fps={target_fps}"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(rife_video),
        "-vf", vf,
        "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
        "-pix_fmt", "yuv420p",
        "-an",  # 항상 무음
        str(out_path),
    ]
    run(cmd, check=True)
    return out_path

# ----------------------------
# 5) 감시 모드 (옵션)
# ----------------------------
def watch_and_build(root: Path, shot: str, **kwargs):
    """
    keyframes/*.png 또는 timing/scene.txt 변경 시 자동으로 전체 파이프라인 실행.
    """
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        print("watch 모드를 사용하려면 `pip install watchdog` 후 다시 시도하세요.", file=sys.stderr)
        sys.exit(1)

    shot_dir = root / "project" / shot
    key_dir  = shot_dir / "keyframes"
    timing   = shot_dir / "timing"

    # 최초 1회 빌드
    build_pipeline(root, shot, **kwargs)

    class Handler(FileSystemEventHandler):
        _last = 0.0
        def on_any_event(self, event):
            if event.is_directory:
                return
            # 디바운스 0.6s
            now = time.time()
            if now - self._last < 0.6:  # 너무 잦은 이벤트 묶어 처리
                return
            self._last = now
            print(f"🔁 변경 감지: {event.src_path}")
            try:
                build_pipeline(root, shot, **kwargs)
            except subprocess.CalledProcessError:
                print("⚠️ 빌드 실패. 로그를 확인하세요.")

    obs = Observer()
    h = Handler()
    for d in [key_dir, timing]:
        d.mkdir(parents=True, exist_ok=True)
        obs.schedule(h, str(d), recursive=False)
    print(f"👀 감시 시작: {key_dir}, {timing}  (Ctrl+C로 종료)")
    obs.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()

# ----------------------------
# 6) 파이프라인 실행
# ----------------------------
def build_pipeline(
    root: Path,
    shot: str,
    base_fps: int,
    target_fps: int,
    width: int,
    height: int,
    rife_dir: Path,
    exp: Optional[int] = None,
    tta: bool = False,
    uhd: bool = False,
    scale: float = 1.0,
    speed: float = 1.0,
):
    shot_dir = root / "project" / shot
    ensure_dirs(shot_dir)

    print("== 1) 베이스 비디오 생성 ==")
    base_video = build_base(shot_dir, base_fps, width, height, mute=True)
    print(f"   -> {base_video}")

    exp_val = compute_exp(base_fps, target_fps) if exp is None else int(exp)
    print(f"== 2) RIFE 보간 (exp={exp_val}) ==")
    rife_video, out_fps = rife_interpolate(
        shot_dir, exp_val, rife_dir, tta=tta, uhd=uhd, scale=scale
    )
    print(f"   -> {rife_video} ({out_fps}fps)")

    print(f"== 3) 최종 {target_fps}fps 렌더 ==")
    final_video = finalize(shot_dir, target_fps, speed=speed)
    print(f"   -> {final_video}")
    print("✅ 완료!")

# ----------------------------
# main
# ----------------------------
def main():
    parser = argparse.ArgumentParser(description="RIFE 파이프라인 (키프레임→베이스→보간→최종)")
    parser.add_argument("--shot", required=True, help="샷 폴더 이름 (예: shot_001)")
    parser.add_argument("--base-fps", type=int, default=1)
    parser.add_argument("--target-fps", type=int, default=24)
    parser.add_argument("--exp", default="auto", help="RIFE exp (auto 또는 정수)")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--rife-dir", default="Practical-RIFE")
    parser.add_argument("--tta", type=int, default=0)
    parser.add_argument("--uhd", type=int, default=0)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--speed", type=float, default=1.5, help="setpts 배수(예: 1.5)")
    parser.add_argument("--watch", action="store_true", help="키프레임/scene.txt 변경 자동 감시")

    args = parser.parse_args()
    ws = Path.cwd()
    shot_dir = ws / "project" / args.shot
    rife_dir = ws / args.rife_dir

    check_ffmpeg()
    ensure_dirs(shot_dir)

    exp_val = None if args.exp == "auto" else int(args.exp)

    if args.watch:
        watch_and_build(
            ws, args.shot,
            base_fps=args.base_fps,
            target_fps=args.target_fps,
            width=args.width, height=args.height,
            rife_dir=rife_dir,
            exp=exp_val,
            tta=bool(args.tta),
            uhd=bool(args.uhd),
            scale=args.scale,
            speed=args.speed,
        )
    else:
        build_pipeline(
            ws, args.shot,
            base_fps=args.base_fps,
            target_fps=args.target_fps,
            width=args.width, height=args.height,
            rife_dir=rife_dir,
            exp=exp_val,
            tta=bool(args.tta),
            uhd=bool(args.uhd),
            scale=args.scale,
            speed=args.speed,
        )

if __name__ == "__main__":
    main()
