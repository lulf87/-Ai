from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory


def _clean(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def extract_text_segments(path: Path) -> list[tuple[str, str]]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        text = _clean(path.read_text(encoding="utf-8"))
        return [("全文", text)] if text else []
    if suffix == ".docx":
        return _extract_docx(path)
    if suffix == ".doc":
        return _extract_doc(path)
    if suffix == ".pdf":
        return _extract_pdf(path)
    raise ValueError(f"Unsupported document format: {suffix}")


def _extract_docx(path: Path) -> list[tuple[str, str]]:
    from docx import Document

    document = Document(path)
    sections: list[tuple[str, str]] = []
    current_heading = "正文"
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        text = _clean("\n".join(buffer))
        if text:
            sections.append((current_heading, text))
        buffer = []

    for paragraph in document.paragraphs:
        content = paragraph.text.strip()
        if not content:
            continue
        style = paragraph.style.name if paragraph.style else ""
        if "Heading" in style or "标题" in style:
            flush()
            current_heading = content
        else:
            buffer.append(content)
    flush()
    return sections


def _extract_pdf(path: Path) -> list[tuple[str, str]]:
    import fitz

    segments: list[tuple[str, str]] = []
    with fitz.open(path) as document:
        for index, page in enumerate(document, start=1):
            text = _clean(page.get_text())
            if text:
                segments.append((f"第{index}页", text))
    return segments


def _extract_doc(path: Path) -> list[tuple[str, str]]:
    text = _legacy_doc_to_text(path)
    cleaned = _clean(text)
    return [("全文", cleaned)] if cleaned else []


def _legacy_doc_to_text(path: Path) -> str:
    textutil = shutil.which("textutil")
    if textutil:
        result = subprocess.run(
            [textutil, "-convert", "txt", "-stdout", str(path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        with TemporaryDirectory() as output_dir:
            subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--convert-to",
                    "txt:Text",
                    "--outdir",
                    output_dir,
                    str(path),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
            converted = next(Path(output_dir).glob("*.txt"), None)
            if converted is None:
                raise ValueError("Legacy .doc conversion did not produce a text file")
            return converted.read_text(encoding="utf-8", errors="replace")

    raise ValueError("Legacy .doc extraction requires textutil or LibreOffice/soffice")
