import json
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: python retime_ocr.py INPUT_JSON OUTPUT_JSON FPS")
    source = Path(sys.argv[1])
    target = Path(sys.argv[2])
    fps = float(sys.argv[3])
    rows = json.loads(source.read_text(encoding="utf-8"))
    for row in rows:
        row["timestamp"] = round(int(Path(row["frame"]).stem) / fps, 3)
    target.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Retimed {target} at {fps:g} fps")


if __name__ == "__main__":
    main()
