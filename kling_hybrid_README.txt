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