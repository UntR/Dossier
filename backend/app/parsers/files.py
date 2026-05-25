from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree


def parse_import_file(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md"}:
        return data.decode("utf-8")
    if suffix == ".docx":
        return parse_docx(data)
    raise ValueError("unsupported file type")


def parse_docx(data: bytes) -> str:
    with zipfile.ZipFile(BytesIO(data)) as archive:
        xml_files = [archive.read(name) for name in docx_text_part_names(archive.namelist())]
    paragraphs = []
    for xml_data in xml_files:
        paragraphs.extend(xml_paragraphs(xml_data))
    return "\n".join(paragraphs)


def docx_text_part_names(names: list[str]) -> list[str]:
    parts = ["word/document.xml"] if "word/document.xml" in names else []
    parts.extend(sorted(name for name in names if name.startswith("word/header") and name.endswith(".xml")))
    parts.extend(sorted(name for name in names if name.startswith("word/footer") and name.endswith(".xml")))
    for exact_name in ("word/footnotes.xml", "word/endnotes.xml", "word/comments.xml"):
        if exact_name in names:
            parts.append(exact_name)
    return parts


def xml_paragraphs(xml_data: bytes) -> list[str]:
    root = ElementTree.fromstring(xml_data)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for paragraph in root.findall(".//w:p", namespace):
        text = paragraph_text(paragraph)
        if text:
            paragraphs.append(text)
    return paragraphs


def paragraph_text(paragraph: ElementTree.Element) -> str:
    parts = []
    for node in paragraph.iter():
        if node.tag == word_tag("t"):
            parts.append(node.text or "")
        elif node.tag == word_tag("tab"):
            parts.append("\t")
        elif node.tag == word_tag("br"):
            parts.append("\n")
    return "".join(parts)


def word_tag(name: str) -> str:
    return f"{{http://schemas.openxmlformats.org/wordprocessingml/2006/main}}{name}"
