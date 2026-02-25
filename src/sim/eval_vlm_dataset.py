import argparse
import json
import random
import time
from pathlib import Path

import cv2

from src.edge.config import EdgeConfig
from src.edge.vlm_client import VLMClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate edge VLM on image folders (safe/danger).")
    parser.add_argument("--safe-dir", default="data/eval/safe", help="Folder with SAFE images")
    parser.add_argument("--danger-dir", default="data/eval/danger", help="Folder with DANGER images")
    parser.add_argument("--limit", type=int, default=0, help="Max images per class (0=all)")
    parser.add_argument("--shuffle", action="store_true", help="Shuffle evaluation order")
    parser.add_argument("--seed", type=int, default=42, help="Random seed when shuffle enabled")
    parser.add_argument("--save-json", default="", help="Optional output json file path")
    return parser.parse_args()


def collect_images(folder: Path, limit: int) -> list[Path]:
    if not folder.exists():
        return []
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    files = [p for p in sorted(folder.rglob("*")) if p.is_file() and p.suffix.lower() in exts]
    if limit > 0:
        return files[:limit]
    return files


def main() -> None:
    args = parse_args()
    safe_dir = Path(args.safe_dir)
    danger_dir = Path(args.danger_dir)

    safe_images = collect_images(safe_dir, args.limit)
    danger_images = collect_images(danger_dir, args.limit)

    if not safe_images and not danger_images:
        raise SystemExit("No images found. Put images in --safe-dir and/or --danger-dir first.")

    samples: list[tuple[Path, bool]] = [(p, False) for p in safe_images] + [(p, True) for p in danger_images]
    if args.shuffle:
        random.seed(args.seed)
        random.shuffle(samples)

    cfg = EdgeConfig.from_env()
    vlm = VLMClient(
        provider=cfg.vlm_provider,
        model=cfg.vlm_model,
        ollama_url=cfg.vlm_ollama_url,
        timeout_sec=cfg.vlm_timeout_sec,
        keep_alive=cfg.vlm_keep_alive,
        use_heuristic_fallback=cfg.vlm_use_heuristic_fallback,
        min_danger_score=cfg.vlm_min_danger_score,
        uncertain_as_safe=cfg.vlm_uncertain_as_safe,
        raw_log_enabled=cfg.vlm_raw_log_enabled,
        raw_log_path=cfg.vlm_raw_log_path,
    )

    tp = tn = fp = fn = 0
    latencies_ms: list[float] = []
    failures: list[dict[str, str]] = []

    for image_path, expected_danger in samples:
        frame = cv2.imread(str(image_path))
        if frame is None:
            failures.append({"image": str(image_path), "reason": "imread_failed"})
            continue

        start = time.perf_counter()
        pred_is_danger, _, confidence, meta = vlm.analyze_frame(frame)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        latencies_ms.append(elapsed_ms)

        if expected_danger and pred_is_danger:
            tp += 1
        elif expected_danger and not pred_is_danger:
            fn += 1
        elif (not expected_danger) and pred_is_danger:
            fp += 1
        else:
            tn += 1

        print(
            f"[{image_path.name}] expected={'DANGER' if expected_danger else 'SAFE'} "
            f"pred={'DANGER' if pred_is_danger else 'SAFE'} conf={confidence:.3f} "
            f"latency_ms={elapsed_ms:.1f} provider={meta.get('provider')}"
        )

    total = tp + tn + fp + fn
    fp_rate = (fp / (fp + tn) * 100.0) if (fp + tn) else 0.0
    tp_rate = (tp / (tp + fn) * 100.0) if (tp + fn) else 0.0
    avg_latency = (sum(latencies_ms) / len(latencies_ms)) if latencies_ms else 0.0

    summary = {
        "total": total,
        "safe_count": tn + fp,
        "danger_count": tp + fn,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "fp_rate_percent": round(fp_rate, 2),
        "tp_rate_percent": round(tp_rate, 2),
        "avg_latency_ms": round(avg_latency, 1),
        "min_latency_ms": round(min(latencies_ms), 1) if latencies_ms else 0.0,
        "max_latency_ms": round(max(latencies_ms), 1) if latencies_ms else 0.0,
        "failed_images": failures,
    }

    print("\n=== SUMMARY ===")
    for k, v in summary.items():
        if k == "failed_images":
            print(f"{k}: {len(v)}")
        else:
            print(f"{k}: {v}")

    if args.save_json:
        output = Path(args.save_json)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved summary JSON: {output}")


if __name__ == "__main__":
    main()
