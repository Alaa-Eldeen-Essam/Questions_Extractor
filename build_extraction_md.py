import difflib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent

VIDEOS = [
    {
        "id": "4sylHoD5tMM",
        "url": "https://www.youtube.com/watch?v=4sylHoD5tMM",
        "ocr": "4sylHoD5tMM.retimed.ocr.json",
        "frames": "inspection/scene_4syl_low",
        "audio": "4sylHoD5tMM.whisper.json",
        "duration": "2:15:40",
        "visual_mode": "questions",
    },
    {
        "id": "85_ZD_3A_x0",
        "url": "https://www.youtube.com/watch?v=85_ZD_3A_x0",
        "ocr": "85_ZD_3A_x0.interval.ocr.json",
        "frames": "inspection/interval_85",
        "audio": "85_ZD_3A_x0.whisper.json",
        "duration": "40:00",
        "visual_mode": "slides",
    },
    {
        "id": "XCXSibE8ibc",
        "url": "https://www.youtube.com/watch?v=XCXSibE8ibc",
        "ocr": "XCXSibE8ibc.retimed.ocr.json",
        "frames": "inspection/scene_XCXS_all",
        "audio": "XCXSibE8ibc.whisper.json",
        "duration": "1:13:46",
        "visual_mode": "questions",
    },
    {
        "id": "GEPQgVRuoII",
        "url": "https://www.youtube.com/watch?v=GEPQgVRuoII",
        "ocr": "GEPQgVRuoII.retimed.ocr.json",
        "frames": "inspection/scene_GEP_all",
        "audio": "GEPQgVRuoII.whisper.json",
        "duration": "1:17:46",
        "visual_mode": "questions",
    },
]


def clean(text: str) -> str:
    text = text.replace("Amazon $3", "Amazon S3")
    text = text.replace("Amazon $3", "Amazon S3")
    text = text.replace("MLA-CO1", "MLA-C01").replace("MLA-COI", "MLA-C01")
    text = text.replace("â€™", "'").replace("â€œ", '"').replace("â€", '"')
    text = text.replace("â€“", "-").replace("Â©", "©").replace("Â", "")
    text = re.sub(r"https?://\S+|www\.\S+", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" -|\t")
    return text


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower().replace("amazon $3", "amazon s3"))


def stamp(seconds: float) -> str:
    total = max(0, int(seconds or 0))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def load_rows(video):
    rows = json.loads((ROOT / video["ocr"]).read_text(encoding="utf-8"))
    cleaned = []
    for row in rows:
        text = clean(row.get("text", ""))
        if len(text) < 55:
            continue
        cleaned.append({**row, "text": text})
    return sorted(cleaned, key=lambda x: x.get("timestamp") or 0)


def dedup_rows(rows, mode):
    chosen = []
    for row in rows:
        current = norm(row["text"])
        if len(current) < 45:
            continue
        duplicate = False
        for previous in reversed(chosen[-5:]):
            if row["timestamp"] - previous["timestamp"] > (75 if mode == "slides" else 100):
                break
            score = difflib.SequenceMatcher(None, current, norm(previous["text"])).ratio()
            if score >= 0.88:
                duplicate = True
                if len(row["text"]) > len(previous["text"]):
                    chosen[-1] = row
                break
        if not duplicate:
            chosen.append(row)
    return chosen


def question_number(text):
    match = re.search(r"(?<![A-Za-z0-9])(\d{1,3})\)\s", text)
    return int(match.group(1)) if match else None


def audio_cue(segments, start, end):
    selected = []
    for segment in segments:
        seg_start = segment.get("start", 0)
        seg_end = segment.get("end", seg_start)
        if seg_end <= start or seg_start >= end:
            continue
        if seg_end - seg_start > 60:
            continue
        text = clean(segment.get("text", ""))
        if len(text) < 20:
            continue
        low = text.lower()
        if any(
            key in low
            for key in (
                "correct answer",
                "right answer",
                "answer is",
                "the answer",
                "because",
                "therefore",
                "best solution",
                "should use",
                "use amazon",
                "use sage",
                "use aws",
                "this option",
                "the reason",
                "which means",
            )
        ):
            selected.append(f"{stamp(seg_start)} — {text}")
    if not selected:
        return "No reliable answer/explanation audio cue was detected in this interval."
    return " ".join(selected[:3])[:900]


def frame_link(video, row):
    return f"{video['frames']}/{row['frame']}"


def make_records(video, rows):
    rows = dedup_rows(rows, video["visual_mode"])
    records = []
    seen_numbers = set()
    for row in rows:
        number = question_number(row["text"]) if video["visual_mode"] == "questions" else None
        if number is not None and number in seen_numbers:
            continue
        if number is not None:
            seen_numbers.add(number)
        records.append({**row, "number": number})
    return records


def main():
    out = [
        "# AWS MLA-C01 exam-prep video extraction",
        "",
        "> This Markdown study guide combines timed speech recognition, on-screen OCR, and direct links to sampled video frames. Spoken content is presented as concise answer/explanation cues rather than a word-for-word transcript; the frame links preserve the visual evidence for review. OCR may contain minor recognition errors, especially in small fonts or animated answer overlays.",
        "",
        "## Source coverage",
        "",
        "| Video | Duration | Visual source | Audio source |",
        "|---|---:|---|---|",
    ]
    loaded = []
    for video in VIDEOS:
        info = json.loads((ROOT / f"{video['id']}.info.json").read_text(encoding="utf-8"))
        rows = load_rows(video)
        records = make_records(video, rows)
        audio = json.loads((ROOT / video["audio"]).read_text(encoding="utf-8"))["segments"]
        loaded.append((video, info, records, audio))
        out.append(
            f"| [{video['id']}]({video['url']}) — {clean(info.get('title', video['id'])).replace('|', '-')} | {video['duration']} | {len(records)} retained visual records | {len(audio)} timed speech segments |"
        )

    out += [
        "",
        "## How to use this guide",
        "",
        "- Start with the question/slide records and try to answer before reading the answer cue.",
        "- Open the linked frame whenever the OCR is uncertain; it is the actual sampled visual and includes diagrams, tables, answer markers, and layout context.",
        "- Repeated question slides and countdown overlays are collapsed when their text is substantially the same.",
        "",
    ]

    for video, info, records, audio in loaded:
        out += [
            f"## {clean(info.get('title', video['id']))}",
            "",
            f"Source: [{video['url']}]({video['url']})  ",
            f"Duration: {video['duration']}",
            "",
        ]
        if video["visual_mode"] == "slides":
            out += [
                "This video reveals its practice questions and answer choices primarily on-screen; the speech track contains an introduction and closing rather than a full spoken explanation for each question.",
                "",
            ]
        for index, record in enumerate(records):
            start = record.get("timestamp") or 0
            next_start = records[index + 1].get("timestamp") if index + 1 < len(records) else start + 90
            label = f"Question {record['number']}" if record.get("number") else f"Visual slide {index + 1}"
            out += [
                f"### {label} — {stamp(start)}",
                "",
                f"**Visual frame:** [{record['frame']}]({frame_link(video, record)})",
                "",
                "**On-screen extraction:**",
                "",
                record["text"],
                "",
                "**Spoken answer/explanation cue:**",
                "",
                audio_cue(audio, start, max(next_start, start + 15)),
                "",
            ]
        out += ["---", ""]

    out += [
        "## Accuracy notes",
        "",
        "- The first two videos had no YouTube English captions, so their audio was transcribed locally.",
        "- The downloadable caption tracks for the third and fourth links were identical and ended early; local transcription was used to cover the remaining runtime.",
        "- Small or animated slide text can be misread by OCR. When an option, AWS service name, or answer letter matters, verify it against the linked frame and the adjacent audio cue.",
    ]
    (ROOT / "exam_prep_extraction.md").write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote exam_prep_extraction.md ({len(out)} lines)")


if __name__ == "__main__":
    main()
