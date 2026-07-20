import json
import sys
from pathlib import Path

from faster_whisper import WhisperModel


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: python transcribe_local.py VIDEO [VIDEO ...]")

    model = WhisperModel("base.en", device="cuda", compute_type="float16")
    for raw_path in sys.argv[1:]:
        path = Path(raw_path)
        print(f"Transcribing {path.name}", flush=True)
        segments, info = model.transcribe(
            str(path),
            language="en",
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=True,
            word_timestamps=True,
        )
        rows = []
        for segment in segments:
            rows.append(
                {
                    "start": round(segment.start, 3),
                    "end": round(segment.end, 3),
                    "text": segment.text.strip(),
                    "words": [
                        {
                            "start": round(word.start, 3),
                            "end": round(word.end, 3),
                            "word": word.word,
                        }
                        for word in (segment.words or [])
                    ],
                }
            )
            if len(rows) % 25 == 0:
                print(f"  {rows[-1]['end']:.0f}s", flush=True)

        output = {
            "video": path.name,
            "language": info.language,
            "duration": info.duration,
            "segments": rows,
        }
        out_path = path.with_suffix(".whisper.json")
        out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {out_path.name} ({len(rows)} segments)", flush=True)


if __name__ == "__main__":
    main()
