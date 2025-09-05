#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Replicate의 WAN I2V(Fast) 호출 → mp4 저장
환경변수: REPLICATE_API_TOKEN
"""

import argparse, sys, requests
from pathlib import Path
from typing import cast

def main():
    p = argparse.ArgumentParser(description="WAN 2.2 I2V (Replicate) runner")
    p.add_argument("--image", required=True, help="입력 이미지 경로 (png/jpg)")
    p.add_argument("--prompt", required=True, help="텍스트 설명")
    p.add_argument("--num-frames", type=int, default=121, help="프레임 수(≈5초@24fps)")
    p.add_argument("--resolution", default="720p", choices=["480p","720p"], help="출력 해상도")
    p.add_argument("--out", default="project/shot_001/work/wan_out.mp4", help="출력 mp4 경로")
    args = p.parse_args()

    try:
        import replicate
        from replicate.exceptions import ReplicateError
    except Exception:
        print("ERROR: `replicate` 패키지가 필요합니다. `pip install replicate requests`", file=sys.stderr)
        sys.exit(1)

    model_ref = "wan-video/wan-2.2-i2v-fast"

    # 실행
    try:
        with open(args.image, "rb") as f:
            url = cast(str, replicate.run(
                model_ref,
                input={
                    "prompt": args.prompt,
                    "image": f,
                    "num_frames": int(args.num_frames),
                    "resolution": args.resolution,
                },
                use_file_output=False,  # URL 문자열 반환
            ))
    except ReplicateError as e:
        msg = str(e)
        if "Insufficient credit" in msg or "402" in msg:
            print(
                "ERR_WAN_CREDIT: Replicate 크레딧이 부족합니다.\n"
                "- Billing에서 충전 후 재실행하세요.\n"
                "- 무료로 계속하려면 RIFE 파이프라인으로 전환:\n"
                "  python scripts/pipeline_plus.py --shot shot_001 --engine rife --base-fps 8 --target-fps 24",
                file=sys.stderr
            )
            sys.exit(2)
        raise

    # 다운로드
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, stream=True); r.raise_for_status()
    with open(out_path, "wb") as fo:
        for ch in r.iter_content(1024 * 1024):
            if ch: fo.write(ch)
    print("saved:", out_path)

if __name__ == "__main__":
    main()
