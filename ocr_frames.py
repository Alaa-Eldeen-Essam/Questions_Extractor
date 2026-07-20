import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def one(path: Path):
    result = subprocess.run(
        ["tesseract", str(path), "stdout", "--psm", "6"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        timestamp = int(path.stem) / 1000
    except ValueError:
        timestamp = None
    text = " ".join(line.strip() for line in result.stdout.splitlines() if line.strip())
    return {"frame": path.name, "timestamp": timestamp, "text": text}


def main() -> None:
    if len(sys.argv) not in (3, 4):
        raise SystemExit("usage: python ocr_frames.py FRAME_DIR OUTPUT_JSON [INTERVAL_SECONDS]")
    frame_dir = Path(sys.argv[1])
    output = Path(sys.argv[2])
    interval = float(sys.argv[3]) if len(sys.argv) == 4 else None
    paths = sorted(frame_dir.glob("*.jpg"))
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(one, paths))
    if interval is not None:
        for index, row in enumerate(rows):
            row["timestamp"] = round(index * interval, 3)
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {output} ({len(rows)} frames)")


if __name__ == "__main__":
    main()
