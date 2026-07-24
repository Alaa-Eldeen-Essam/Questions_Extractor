"""Small dependency-free Word document renderer for extraction artifacts."""

from __future__ import annotations

import struct
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape

from ..config import PipelineConfig
from ..models.frames import FrameEvidence, OCRResult
from ..models.questions import QuestionRecord
from ..models.sources import SourceMetadata
from ..models.transcripts import Transcript


EMU_PER_INCH = 914_400
MAX_WIDTH = int(6.25 * EMU_PER_INCH)
MAX_HEIGHT = int(4.75 * EMU_PER_INCH)


def _text(value: object) -> str:
    return escape(str(value))


def _paragraph(value: object = "", *, style: str | None = None, bold: bool = False) -> str:
    style_xml = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    run_properties = "<w:rPr><w:b/></w:rPr>" if bold else ""
    return f'<w:p>{style_xml}<w:r>{run_properties}<w:t xml:space="preserve">{_text(value)}</w:t></w:r></w:p>'


def _heading(value: object, level: int = 1) -> str:
    return _paragraph(value, style=f"Heading{min(3, max(1, level))}")


def _stamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def _image_size(path: Path) -> tuple[int, int]:
    """Read dimensions for common frame formats without an image dependency."""
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if data.startswith(b"\xff\xd8"):
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            index += 2
            if marker in {0xD8, 0xD9}:
                continue
            if index + 2 > len(data):
                break
            length = struct.unpack(">H", data[index:index + 2])[0]
            if marker in set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0)):
                if index + 7 <= len(data):
                    height, width = struct.unpack(">HH", data[index + 3:index + 7])
                    return width, height
            index += max(2, length)
    return 16, 9


def _scaled_extent(path: Path) -> tuple[int, int]:
    width, height = _image_size(path)
    scale = min(MAX_WIDTH / max(width, 1), MAX_HEIGHT / max(height, 1), 1.0)
    return max(1, int(width * scale)), max(1, int(height * scale))


def _image_paragraph(relationship: str, name: str, width: int, height: int, document_id: int) -> str:
    return f'''<w:p><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">
<wp:extent cx="{width}" cy="{height}"/><wp:docPr id="{document_id}" name="{_text(name)}"/>
<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
<pic:pic><pic:nvPicPr><pic:cNvPr id="{document_id}" name="{_text(name)}"/><pic:cNvPicPr/></pic:nvPicPr>
<pic:blipFill><a:blip r:embed="{relationship}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{width}" cy="{height}"/></a:xfrm>
<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>
</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'''


def _document_xml(body: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"
 xmlns:v="urn:schemas-microsoft-com:vml"
 xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
 xmlns:w10="urn:schemas-microsoft-com:office:word"
 xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml"
 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" mc:Ignorable="w14 wp14">
 <w:body>{body}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body>
</w:document>'''


def _content_types(image_extensions: set[str]) -> str:
    image_types = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}
    defaults = ''.join(
        f'<Default Extension="{extension}" ContentType="{image_types[extension]}"/>'
        for extension in sorted(image_extensions)
    )
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>{defaults}
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>'''


def _styles_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:sz w:val="22"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:rPr><w:b/><w:sz w:val="27"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>
</w:styles>'''


def write_docx(
    path: Path,
    metadata: SourceMetadata,
    transcript: Transcript,
    frames: list[FrameEvidence],
    ocr: list[OCRResult],
    questions: list[QuestionRecord],
    config: PipelineConfig,
    warnings: list[str],
) -> None:
    """Write a self-contained Word study document using only the standard library."""
    body: list[str] = [_heading(metadata.title or metadata.source.value, 1)]
    source = "[redacted]" if config.privacy.redact_source else metadata.source.value
    body.extend(
        [
            _paragraph(f"Source: {source}"),
            _paragraph(f"Type: {metadata.source.kind.value}"),
            _paragraph(f"Captions: {metadata.has_captions}"),
            _heading("Warnings", 2),
        ]
    )
    if warnings:
        body.extend(_paragraph(f"- {warning}") for warning in warnings)
    else:
        body.append(_paragraph("- None"))

    body.append(_heading("Question bank", 2))
    if questions:
        for index, question in enumerate(questions, start=1):
            body.append(_heading(f"{index}. {question.prompt}", 3))
            body.extend(_paragraph(f"{option.label}. {option.text}") for option in question.options)
            if question.answer:
                body.append(_paragraph(f"Answer: {question.answer}", bold=True))
            if question.explanation:
                body.append(_paragraph(f"Explanation: {question.explanation}"))
            body.extend(_paragraph(f"Warning: {warning}") for warning in question.warnings)
    else:
        body.append(_paragraph("No question records were detected."))

    body.append(_heading("Speech timeline", 2))
    if transcript.segments:
        body.extend(_paragraph(f"[{_stamp(item.start_seconds)}] {item.text}") for item in transcript.segments)
    else:
        body.append(_paragraph("No transcript was available."))

    body.append(_heading("Visual evidence", 2))
    ocr_by_path = {str(result.frame.path.resolve()): result for result in ocr}
    relationships: list[tuple[str, Path]] = []
    image_id = 1
    for frame in frames:
        body.append(_heading(f"Frame {_stamp(frame.timestamp_seconds)}", 3))
        result = ocr_by_path.get(str(frame.path.resolve()))
        if result and result.text:
            body.append(_paragraph(f"OCR: {result.text}"))
        if frame.path.is_file() and frame.path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            relationship = f"rId{image_id}"
            width, height = _scaled_extent(frame.path)
            body.append(_image_paragraph(relationship, frame.path.name, width, height, image_id))
            relationships.append((relationship, frame.path))
            image_id += 1

    document = _document_xml("".join(body))
    root_relationships = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''
    document_relationships = ['''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>''']
    image_extensions: set[str] = set()
    for relationship, image_path in relationships:
        extension = image_path.suffix.lower().lstrip(".")
        image_extensions.add(extension)
        document_relationships.append(
            f'<Relationship Id="{relationship}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{image_path.name}"/>'
        )
    document_relationships.append("</Relationships>")

    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types(image_extensions))
        archive.writestr("_rels/.rels", root_relationships)
        archive.writestr("word/document.xml", document)
        archive.writestr("word/styles.xml", _styles_xml())
        archive.writestr("word/_rels/document.xml.rels", "".join(document_relationships))
        for _, image_path in relationships:
            archive.write(image_path, f"word/media/{image_path.name}")
