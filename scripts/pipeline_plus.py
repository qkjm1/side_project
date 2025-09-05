
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, os, sys, subprocess
from pathlib import Path

# Reuse functions from the original pipeline
from pipeline import ensure_dirs, check_ffmpeg, rife_interpolate, compute_exp

def sh(cmd):
    print("[cmd]", " ".join(map(str, cmd)), flush=True)
    subprocess.run(cmd, check=True)

def latest_one(dirpath: Path, pattern: str):
    files = sorted(dirpath.glob(pattern), key=os.path.getmtime)
    return files[-1] if files else None

def convert_video_to_base(src: Path, dst: Path, base_fps: int):
    dst.parent.mkdir(parents=True, exist_ok=True)
    sh(["ffmpeg", "-y",
        "-i", str(src),
        "-vf", f"fps={base_fps},scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1,format=yuv420p",
        "-an",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        str(dst)])

def finalize_from(src: Path, out: Path, target_fps: int, speed: float = 1.0, crf: int = 17, preset: str = "slow"):
    out.parent.mkdir(parents=True, exist_ok=True)
    sh(["ffmpeg", "-y",
        "-i", str(src),
        "-filter:v", f"setpts={speed}*PTS",
        "-r", str(target_fps),
        "-an",  # always mute
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        str(out)])

def main():
    p = argparse.ArgumentParser(description="Hybrid pipeline with Kling + (optional) RIFE")
    p.add_argument("--shot", required=True)
    # Kling options
    p.add_argument("--engine", choices=["kling","rife"], default="kling")
    p.add_argument("--post", choices=["none","rife"], default="rife")
    p.add_argument("--kling-prompt", default="")
    p.add_argument("--kling-negative", default="")
    p.add_argument("--kling-duration", type=int, default=5)
    p.add_argument("--kling-aspect", default="16:9")
    p.add_argument("--kling-start-image", default="")
    # RIFE/base/final common options
    p.add_argument("--base-fps", type=int, default=8)
    p.add_argument("--target-fps", type=int, default=24)
    p.add_argument("--rife-dir", default="Practical-RIFE")
    p.add_argument("--exp", default="auto")
    p.add_argument("--tta", type=int, default=0)
    p.add_argument("--uhd", type=int, default=0)
    p.add_argument("--scale", type=float, default=1.0)
    p.add_argument("--speed", type=float, default=1.0)
    args = p.parse_args()

    ws = Path.cwd()
    shot_dir = ws / "project" / args.shot
    ensure_dirs(shot_dir)
    check_ffmpeg()

    work = shot_dir / "work"
    out_dir = shot_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.engine == "rife":
        # Simply call original pipeline via subprocess for compatibility
        cmd = [sys.executable, "scripts/pipeline.py",
               "--shot", args.shot,
               "--base-fps", str(args.base_fps),
               "--target-fps", str(args.target_fps),
               "--exp", str(args.exp),
               "--rife-dir", args.rife_dir,
               "--tta", str(args.tta),
               "--uhd", str(args.uhd),
               "--scale", str(args.scale),
               "--speed", str(args.speed)]
        subprocess.run(cmd, check=True)
        print("✅ Done (RIFE pipeline)")
        return

    # === Kling path ===
    # pick start image
    start_img = Path(args.kling_start_image) if args.kling_start_image else None
    if start_img is None:
        candidates = sorted(list((shot_dir / "keyframes").glob("*.png")) +
                            list((shot_dir / "keyframes").glob("*.jpg")) +
                            list((shot_dir / "keyframes").glob("*.jpeg")))
        if not candidates:
            print("ERROR: keyframes/에 이미지가 없습니다. --kling-start-image 로 지정하세요.", file=sys.stderr)
            sys.exit(2)
        start_img = candidates[0]

    print("== 1) Kling 생성 ==")
    from kling_runner import generate_kling_video, download
    url = generate_kling_video(start_img, args.kling_prompt, duration=args.kling_duration,
                               aspect_ratio=args.kling_aspect, negative_prompt=args.kling_negative)
    kling_mp4 = work / f"kling_{int(args.kling_duration)}s.mp4"
    download(url, kling_mp4)
    print("   ->", kling_mp4)

    # Convert to base for RIFE compatibility
    base_mp4 = work / f"base_{args.base_fps}fps.mp4"
    print("== 2) Kling → base 변환 ==")
    convert_video_to_base(kling_mp4, base_mp4, base_fps=args.base_fps)
    print("   ->", base_mp4)

    # Optional RIFE post
    src_for_final = kling_mp4
    if args.post == "rife":
        exp = None if args.exp == "auto" else int(args.exp)
        if exp is None:
            # derive exp from target fps guess
            def compute_exp(base_fps, target_fps):
                # simple compute: minimum n s.t. base_fps * 2^n >= target_fps
                n = 0
                cur = base_fps
                while cur < target_fps and n < 10:
                    n += 1
                    cur *= 2
                return n
            exp = compute_exp(args.base_fps, args.target_fps)
        print(f"== 3) RIFE 보간 (exp={exp}) ==")
        rife_out, rife_fps = rife_interpolate(shot_dir, exp, ws / args.rife_dir,
                                              tta=bool(args.tta), uhd=bool(args.uhd), scale=args.scale)
        print("   ->", rife_out, f"({rife_fps}fps)")
        src_for_final = rife_out

    print(f"== 최종 {args.target_fps}fps 렌더 ==")
    final_mp4 = out_dir / f"final_{args.target_fps}fps.mp4"
    finalize_from(src_for_final, final_mp4, target_fps=args.target_fps, speed=args.speed)
    print("   ->", final_mp4)
    print("✅ 완료!")

if __name__ == "__main__":
    main()
