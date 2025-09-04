#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, subprocess, sys
from pathlib import Path

def sh(cmd):
    print("[cmd]", " ".join(map(str, cmd)), flush=True)
    subprocess.run(cmd, check=True)

def run_pipeline(shot: str):
    # 파이프라인 실행 (베이스→RIFE→최종)
    sh([sys.executable, "scripts/pipeline.py", "--shot", shot])

def latest_final(out_dir: Path, target_fps: int):
    # 우선 final_<fps>fps.mp4를 찾고, 없으면 out 디렉토리의 최신 final_*.mp4 사용
    candidate = out_dir / f"final_{target_fps}fps.mp4"
    if candidate.exists():
        return candidate
    finals = sorted(out_dir.glob("final_*fps.mp4"), key=lambda p: p.stat().st_mtime)
    return finals[-1] if finals else None

def make_pingpong_from_video(src: Path, dst: Path, fps: int, duration_sec: float, crf=17, preset="slow", tune="animation"):
    # 앞(정방향) + 뒤(역재생, 첫 프레임 1장 제거) → concat → 정확히 duration으로 트림
    fc = (
        "[0:v]split[fwd][revsrc];"
        "[revsrc]reverse,setpts=PTS-STARTPTS,trim=start_frame=1[rev];"
        "[fwd][rev]concat=n=2:v=1:a=0,"
        "scale=iw:ih:flags=lanczos,setsar=1,format=yuv420p,"
        f"trim=duration={duration_sec}"
    )
    sh([
        "ffmpeg","-y","-i", str(src),
        "-filter_complex", fc,
        "-r", str(fps), "-c:v","libx264","-preset", preset,"-crf", str(crf), "-tune", tune,
        str(dst)
    ])

def main():
    ap = argparse.ArgumentParser(description="final_*fps.mp4 → 6초 핑퐁(1→2→1)")
    ap.add_argument("--shot", required=True)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--duration", type=float, default=6.0)
    ap.add_argument("--crf", type=int, default=17)
    ap.add_argument("--preset", default="slow")
    ap.add_argument("--tune", default="animation")
    ap.add_argument("--skip-pipeline", action="store_true")
    args = ap.parse_args()

    project = Path("project") / args.shot
    out_dir = project / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_mp4 = out_dir / f"{args.shot}_pingpong_{int(args.duration)}s.mp4"

    if not args.skip_pipeline:
        print("[1/3] Run pipeline")
        run_pipeline(args.shot)

    print("[2/3] Find final video")
    src = latest_final(out_dir, args.fps)
    if not src:
        print("ERROR: final_*fps.mp4 를 찾을 수 없습니다. pipeline을 먼저 돌려 주세요.", file=sys.stderr)
        sys.exit(2)
    print(f"  -> {src}")

    print("[3/3] Build ping-pong")
    make_pingpong_from_video(src, out_mp4, fps=args.fps, duration_sec=args.duration, crf=args.crf, preset=args.preset, tune=args.tune)
    print(f"Done ✅  → {out_mp4}")

if __name__ == "__main__":
    main()
