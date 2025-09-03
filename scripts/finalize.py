#!/usr/bin/env python3
import argparse
from pathlib import Path
from pipeline import finalize, ensure_dirs

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--shot", required=True)
    p.add_argument("--target-fps", type=int, default=24)
    args = p.parse_args()
    shot_dir = Path.cwd() / "project" / args.shot
    ensure_dirs(shot_dir)
    out = finalize(shot_dir, args.target_fps)
    print(f"최종 비디오 생성 완료: {out}")

if __name__ == "__main__":
    main()
