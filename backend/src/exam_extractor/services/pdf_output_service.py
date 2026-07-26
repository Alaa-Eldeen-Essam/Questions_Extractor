"""Small dependency-free PDF writer for text extraction artifacts."""

from __future__ import annotations

from pathlib import Path


def write_text_pdf(path: Path, text: str, *, title: str = "Extraction") -> None:
    """Write wrapped UTF-8 text as a readable, portable PDF.

    The built-in Helvetica font is intentionally used so the artifact works in
    the base Docker image without a PDF library. Characters unavailable in the
    standard PDF font are replaced; the original Unicode content remains in
    JSON and Markdown artifacts.
    """
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        value = paragraph.expandtabs(4)
        if not value:
            lines.append("")
            continue
        while len(value) > 96:
            split = value.rfind(" ", 0, 96)
            split = split if split > 0 else 96
            lines.append(value[:split])
            value = value[split:].lstrip()
        lines.append(value)
    page_lines = 48
    pages = [lines[index:index + page_lines] for index in range(0, max(1, len(lines)), page_lines)]
    objects: list[bytes] = []

    def add(value: str | bytes) -> int:
        objects.append(value.encode("latin-1", "replace") if isinstance(value, str) else value)
        return len(objects)

    font_id = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids: list[int] = []
    content_ids: list[int] = []
    for page in pages:
        commands = ["BT", "/F1 10 Tf", "54 760 Td"]
        for line in page:
            safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"({safe.encode('latin-1', 'replace').decode('latin-1')}) Tj")
            commands.append("0 -14 Td")
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1", "replace")
        content_ids.append(add(f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream"))
        page_ids.append(0)

    for index, content_id in enumerate(content_ids):
        page_ids[index] = add(f"<< /Type /Page /Parent PAGES_REF /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>")
    pages_id = add(f"<< /Type /Pages /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] /Count {len(page_ids)} >>")
    page_object_ids = list(page_ids)
    for index, page_id in enumerate(page_object_ids):
        objects[page_id - 1] = objects[page_id - 1].replace(b"PAGES_REF", f"{pages_id} 0 R".encode("ascii"))
    catalog_id = add(f"<< /Type /Catalog /Pages {pages_id} 0 R /ViewerPreferences << /DisplayDocTitle true >> >>")
    info_id = add(f"<< /Title ({title.replace('(', '[').replace(')', ']')}) >>")

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, value in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(value)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    output.extend(b"".join(f"{offset:010d} 00000 n \n".encode("ascii") for offset in offsets[1:]))
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R /Info {info_id} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    path.write_bytes(output)
