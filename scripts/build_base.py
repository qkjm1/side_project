#!/usr/bin/env python3
import argparse, sys
from pathlib import Path
from pipeline import build_base, ensure_dirs, check_ffmpeg

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--shot", required=True)
    p.add_argument("--base-fps", type=int, default=8)
    p.add_argument("--width", type=int, default=1920)
    p.add_argument("--height", type=int, default=1080)

    # ✅ 추가: 무음 플래그(기본 True)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--mute",    dest="mute", action="store_true",  default=True,  help="오디오 제거(기본값)")
    g.add_argument("--no-mute", dest="mute", action="store_false",                 help="오디오 유지")

    args = p.parse_args()

    shot_dir = Path.cwd() / "project" / args.shot
    check_ffmpeg()
    ensure_dirs(shot_dir)

    # ✅ 변경: mute 전달
    out = build_base(shot_dir, args.base_fps, args.width, args.height, mute=args.mute)
    print(f"베이스 비디오 생성 완료: {out}")

if __name__ == "__main__":
    main()
