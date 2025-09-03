#!/usr/bin/env python3
import argparse
from pathlib import Path
from pipeline import rife_interpolate, compute_exp, ensure_dirs

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--shot", required=True)
    p.add_argument("--exp", default="auto")
    p.add_argument("--rife-dir", default="Practical-RIFE")
    p.add_argument("--tta", type=int, default=0)
    p.add_argument("--uhd", type=int, default=0)
    p.add_argument("--scale", type=float, default=1.0)
    p.add_argument("--base-fps", type=int, default=8)  # auto 계산용 보조
    p.add_argument("--target-fps", type=int, default=24)
    args = p.parse_args()

    ws = Path.cwd()
    shot_dir = ws / "project" / args.shot
    ensure_dirs(shot_dir)

    exp = compute_exp(args.base_fps, args.target_fps) if args.exp == "auto" else int(args.exp)
    out, outfps = rife_interpolate(shot_dir, exp, ws / args.rife_dir, tta=bool(args.tta), uhd=bool(args.uhd), scale=args.scale)
    print(f"RIFE 보간 완료: {out} ({outfps}fps)")

if __name__ == "__main__":
    main()
