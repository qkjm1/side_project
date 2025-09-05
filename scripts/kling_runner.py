
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kling (via Replicate) image->video runner.
Requires: REPLICATE_API_TOKEN in environment.
"""
from pathlib import Path
import os, sys, requests

def generate_kling_video(start_image: Path, prompt: str, duration: int = 5, aspect_ratio: str = "16:9",
                         negative_prompt: str = "", model: str = None) -> str:
    try:
        import replicate
    except Exception:
        print("ERROR: `replicate` 패키지가 필요합니다. `pip install replicate requests`", file=sys.stderr)
        raise

    model = model or os.environ.get("KLING_MODEL", "kwaivgi/kling-v1.6-pro")
    client = replicate.Client()  # uses REPLICATE_API_TOKEN

    with open(start_image, "rb") as f:
        output_url = client.run(
            model,
            input={
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "start_image": f,
                "duration": int(duration),
                "aspect_ratio": aspect_ratio,
            },
        )
    return output_url

def download(url: str, out_path: Path):
    r = requests.get(url, stream=True)
    r.raise_for_status()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as fo:
        for chunk in r.iter_content(chunk_size=1024*1024):
            if chunk:
                fo.write(chunk)
    return out_path
