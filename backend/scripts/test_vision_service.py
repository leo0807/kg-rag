"""
scripts/test_vision_service.py
测试 VisionService MLX 本地模式

用法（在 backend/ 目录下）：
    .venv/bin/python scripts/test_vision_service.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
except Exception:
    pass

from src.core.logging import setup_logging
setup_logging()

IMAGE = "uploads/images/CPS2041_page8_img0.png"

def run_task(svc, task: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"task = {task}  |  image = {Path(IMAGE).name}")
    print("─" * 60)
    t0 = time.time()
    try:
        result = svc.analyze_image(IMAGE, task)
        elapsed = time.time() - t0
        print(f"✓ {elapsed:.1f}s")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        elapsed = time.time() - t0
        print(f"✗ {elapsed:.1f}s  {e}")

if __name__ == "__main__":
    from src.services.vision_service import VisionService
    svc = VisionService()
    print(f"VisionService mode = {svc._mode}")
    print(f"Providers: {[p.name for p in svc._providers]}")

    run_task(svc, "figure")
    run_task(svc, "table")
    run_task(svc, "formula")
