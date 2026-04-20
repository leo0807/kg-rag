"""
scripts/test_drawing_analyzer.py
测试 drawing_analyzer 对 CPS1220 图片的分析质量

用法（在 backend/ 目录下）：
    python scripts/test_drawing_analyzer.py
    python scripts/test_drawing_analyzer.py --doc CPS1220 --limit 5
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# 加载 .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
except Exception:
    pass

from src.core.logging import setup_logging
setup_logging()


def main():
    parser = argparse.ArgumentParser(description="测试图纸分析器")
    parser.add_argument("--doc",   default="CPS1220", help="文档 ID 前缀过滤")
    parser.add_argument("--limit", type=int, default=0, help="最多分析几张，0=全部")
    args = parser.parse_args()

    image_dir = Path("uploads/images")
    if not image_dir.exists():
        print(f"目录不存在: {image_dir}")
        sys.exit(1)

    # 找到匹配的图片文件（仅取简短 doc_id 格式，如 CPS1220_pageX_imgY）
    pattern = f"{args.doc}_page*.png"
    images  = sorted(image_dir.glob(pattern))
    images += sorted(image_dir.glob(f"{args.doc}_page*.jpeg"))
    images += sorted(image_dir.glob(f"{args.doc}_page*.jpg"))

    if not images:
        # 也尝试带后缀名的 doc_id
        images = sorted(image_dir.glob(f"{args.doc}*.png"))
        images += sorted(image_dir.glob(f"{args.doc}*.jpeg"))

    if not images:
        print(f"未找到匹配图片: uploads/images/{args.doc}_page*")
        sys.exit(1)

    if args.limit:
        images = images[:args.limit]

    print(f"\n找到 {len(images)} 张图片，开始分析...\n{'─' * 60}")

    from src.services.drawing_analyzer import analyze_drawing

    succeeded = 0
    failed    = 0
    results   = []

    for i, img_path in enumerate(images, start=1):
        print(f"[{i:2d}/{len(images)}] {img_path.name} ...", end=" ", flush=True)
        t0 = time.time()
        try:
            result = analyze_drawing(str(img_path), "", args.doc)
            elapsed = time.time() - t0
            is_drawing = result.get("is_drawing", False)
            summary    = result.get("summary", "")[:80]
            ann_count  = len(result.get("annotations", []))
            print(f"✓ {elapsed:.1f}s  is_drawing={is_drawing}  annotations={ann_count}")
            print(f"   caption: {summary or '（无描述）'}")
            succeeded += 1
            results.append({"path": str(img_path), "result": result})
        except Exception as e:
            elapsed = time.time() - t0
            print(f"✗ {elapsed:.1f}s  {e}")
            failed += 1

    print(f"\n{'─' * 60}")
    print(f"完成：成功 {succeeded}，失败 {failed}，共 {len(images)} 张")

    # 输出第一张成功图片的完整分析结果
    if results:
        print(f"\n── 第一张图片完整分析结果 ({Path(results[0]['path']).name}) ──")
        print(json.dumps(results[0]["result"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
