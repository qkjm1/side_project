#!/usr/bin/env python3
import argparse, math, os, subprocess, sys, shutil
from pathlib import Path
from typing import Optional

def run(cmd, cwd=None):
    print(f"[cmd] {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        sys.exit(result.returncode)

def which(name: str) -> Optional[str]:
    return shutil.which(name)

def check_ffmpeg():
    if not which("ffmpeg"):
        print("ERROR: ffmpeg가 설치되어 있지 않습니다. README.md의 설치 방법을 참고하세요.", file=sys.stderr)
        sys.exit(1)

def ensure_dirs(shot_dir: Path):
    for d in ["work", "out"]:
        (shot_dir / d).mkdir(parents=True, exist_ok=True)

# --- 기존 ---
# def build_base(shot_dir: Path, base_fps: int, width: int, height: int) -> Path:

# --- 변경 ---
def build_base(shot_dir: Path, base_fps: int, width: int, height: int, mute: bool = True) -> Path:
    scene_txt = shot_dir / "timing" / "scene.txt"
    out_path  = shot_dir / "work" / f"base_{base_fps}fps.mp4"

    # (기존에 쓰던 scale/pad 필터)
    vf = f"scale={width}:-2:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(scene_txt),
        "-vf", vf,
        "-r", str(base_fps),
        "-pix_fmt", "yuv420p",
    ]
    if mute:
        cmd += ["-an"]              # ✅ 오디오 제거

    cmd += [str(out_path)]

    # run(cmd) 같은 실행 부분은 기존 그대로 유지
    # ...
    return out_path

def compute_exp(base_fps: int, target_fps: int) -> int:
    if base_fps >= target_fps:
        return 0
    return math.ceil(math.log2(target_fps / base_fps))

def rife_interpolate(shot_dir: Path, exp: int, rife_dir: Path, tta: bool=False, uhd: bool=False, scale: float=1.0):
    work = shot_dir / "work"
    base_video = max(work.glob("base_*fps.mp4"), key=os.path.getmtime, default=None)
    if base_video is None:
        print("ERROR: work/에 base_*fps.mp4 가 없습니다. 먼저 Build Base를 실행하세요.", file=sys.stderr)
        sys.exit(1)
    input_fps = int(base_video.stem.split("_")[1].replace("fps",""))
    out_fps = input_fps * (2 ** exp)
    out_path = work / f"rife_{out_fps}fps.mp4"

    inf_py = rife_dir / "inference_video.py"
    if not inf_py.exists():
        print(f"ERROR: {inf_py} 를 찾을 수 없습니다. Practical-RIFE가 제대로 클론/설치되었는지 확인하세요.", file=sys.stderr)
        sys.exit(1)

    cmd = [sys.executable, str(inf_py), "--video", str(base_video), "--exp", str(exp), "--output", str(out_path)]
    if tta:
        cmd += ["--tta", "1"]
    if uhd:
        cmd += ["--uhd"]
    if scale != 1.0:
        cmd += ["--scale", str(scale)]
    run(cmd)
    return out_path, out_fps

def finalize(shot_dir: Path, target_fps: int):
    work = shot_dir / "work"
    out_dir = shot_dir / "out"
    rife_video = max(work.glob("rife_*fps.mp4"), key=os.path.getmtime, default=None)
    if rife_video is None:
        print("ERROR: work/에 rife_*fps.mp4 가 없습니다. 먼저 RIFE Interpolate를 실행하세요.", file=sys.stderr)
        sys.exit(1)
    out_path = out_dir / f"final_{target_fps}fps.mp4"
    cmd = ["ffmpeg", "-y", "-i", str(rife_video), "-r", str(target_fps), "-pix_fmt", "yuv420p", str(out_path)]
    run(cmd)
    return out_path

def main():
    parser = argparse.ArgumentParser(description="RIFE 파이프라인 (키프레임→베이스→보간→최종)")
    parser.add_argument("--shot", required=True, help="샷 폴더 이름 (예: shot_001)")
    parser.add_argument("--base-fps", type=int, default=8)
    parser.add_argument("--target-fps", type=int, default=24)
    parser.add_argument("--exp", default="auto", help="RIFE exp (auto 또는 정수)")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--rife-dir", default="Practical-RIFE")
    parser.add_argument("--tta", type=int, default=0)
    parser.add_argument("--uhd", type=int, default=0)
    parser.add_argument("--scale", type=float, default=1.0)

    args = parser.parse_args()
    ws = Path.cwd()
    shot_dir = ws / "project" / args.shot
    rife_dir = ws / args.rife_dir

    check_ffmpeg()
    ensure_dirs(shot_dir)

    print("== 1) 베이스 비디오 생성 ==")
    base_video = build_base(shot_dir, args.base_fps, args.width, args.height)
    print(f"   -> {base_video}")

    if args.exp == "auto":
        exp = compute_exp(args.base_fps, args.target_fps)
    else:
        exp = int(args.exp)
    print(f"== 2) RIFE 보간 (exp={exp}) ==")
    rife_video, out_fps = rife_interpolate(shot_dir, exp, rife_dir, tta=bool(args.tta), uhd=bool(args.uhd), scale=args.scale)
    print(f"   -> {rife_video} ({out_fps}fps)")

    print(f"== 3) 최종 {args.target_fps}fps 리샘플 ==")
    final_video = finalize(shot_dir, args.target_fps)
    print(f"   -> {final_video}")
    print("완료!")

if __name__ == "__main__":
    main()
