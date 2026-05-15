from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from sqlmodel import Session, select

from backend.app.config import BASE_DIR
from backend.app.models import RegulationAttachment, RegulationRecord, RegulationTextSegment


SEED_PATH = BASE_DIR / "knowledge_base" / "regulations_seed.json"
MAX_WEB_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class WebRegulationSource:
    title: str
    text: str
    content_sha256: str
    content: bytes = b""
    content_type: str = ""


@dataclass(frozen=True)
class DownloadedAttachment:
    filename: str
    content: bytes
    content_type: str


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.body_parts: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text or self._skip_depth:
            return
        if self._in_title:
            self.title_parts.append(text)
            return
        self.body_parts.append(text)

    @property
    def title(self) -> str:
        return _clean_text(" ".join(self.title_parts))

    @property
    def body_text(self) -> str:
        return _clean_text("\n".join(self.body_parts))


def _clean_text(text: str) -> str:
    return "\n".join(line.strip() for line in re.split(r"[\r\n]+", text) if line.strip())


def _decode_web_bytes(raw: bytes, content_type: str) -> str:
    charset_match = re.search(r"charset=([\w-]+)", content_type, flags=re.IGNORECASE)
    encodings = [charset_match.group(1)] if charset_match else []
    encodings.extend(["utf-8", "gb18030"])
    for encoding in encodings:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def fetch_web_regulation(url: str) -> WebRegulationSource:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http and https regulation URLs can be imported")

    request = Request(url, headers={"User-Agent": "Mozilla/5.0 RegulationLibraryImporter/1.0"})
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read(MAX_WEB_BYTES + 1)
            content_type = response.headers.get("content-type", "")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ValueError(f"Unable to fetch regulation URL: {exc}") from exc

    if len(raw) > MAX_WEB_BYTES:
        raise ValueError("Regulation web page is larger than the 5 MB import limit")

    content_sha256 = hashlib.sha256(raw).hexdigest()
    html = _decode_web_bytes(raw, content_type)
    parser = _VisibleTextParser()
    parser.feed(html)
    text = parser.body_text
    if not text:
        raise ValueError("No readable text was extracted from the regulation URL")
    return WebRegulationSource(
        title=parser.title,
        text=text,
        content_sha256=content_sha256,
        content=raw,
        content_type=content_type,
    )


def download_attachment(url: str, filename: str = "", referer: str = "") -> DownloadedAttachment:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http and https attachment URLs can be imported")
    headers = {"User-Agent": "Mozilla/5.0 RegulationLibraryImporter/1.0"}
    if referer:
        headers["Referer"] = referer
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            content = response.read(MAX_WEB_BYTES + 1)
            content_type = response.headers.get("content-type", "")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ValueError(f"Unable to download regulation attachment: {exc}") from exc
    if len(content) > MAX_WEB_BYTES:
        raise ValueError("Regulation attachment is larger than the 5 MB import limit")
    resolved_filename = filename or Path(parsed.path).name or "regulation-attachment.bin"
    return DownloadedAttachment(
        filename=resolved_filename,
        content=content,
        content_type=content_type,
    )


def source_files_have_sha(source_files: list[dict]) -> bool:
    usable_files = [
        item
        for item in source_files
        if item.get("verification_usable", True) is not False
    ]
    return bool(usable_files) and all(str(item.get("sha256", "")).strip() for item in usable_files)


def has_usable_attachment(session: Session, regulation_id: int) -> bool:
    return bool(
        session.exec(
            select(RegulationAttachment).where(
                RegulationAttachment.regulation_id == regulation_id,
                RegulationAttachment.verification_usable == True,  # noqa: E712
                RegulationAttachment.sha256 != "",
                RegulationAttachment.stored_path != "",
                RegulationAttachment.download_status == "extracted",
                RegulationAttachment.segment_count > 0,
            )
        ).first()
    )


def refresh_regulation_text_summary(session: Session, regulation: RegulationRecord) -> None:
    segments = session.exec(
        select(RegulationTextSegment)
        .where(RegulationTextSegment.regulation_id == regulation.id)
        .order_by(RegulationTextSegment.id)
    ).all()
    preview_parts: list[str] = []
    for segment in segments:
        if len(" ".join(preview_parts)) < 500:
            preview_parts.append(segment.text[:500])
    regulation.segment_count = len(segments)
    regulation.text_preview = _clean_text("\n".join(preview_parts))[:700]
    session.add(regulation)


def write_regulation_segments(
    session: Session,
    regulation: RegulationRecord,
    segments: list[tuple[str, str]],
    attachment: RegulationAttachment | None = None,
) -> None:
    preview_parts: list[str] = []
    count = 0
    for locator, text in segments:
        cleaned = _clean_text(text)
        if not cleaned:
            continue
        session.add(
            RegulationTextSegment(
                regulation_id=regulation.id or 0,
                attachment_id=attachment.id if attachment else None,
                locator=locator,
                text=cleaned,
            )
        )
        if len(" ".join(preview_parts)) < 500:
            preview_parts.append(cleaned[:500])
        count += 1
    regulation.segment_count = count
    regulation.text_preview = _clean_text("\n".join(preview_parts))[:700]
    if attachment is not None:
        attachment.segment_count = count
        attachment.text_preview = regulation.text_preview
        attachment.download_status = "extracted"
        session.add(attachment)
    session.add(regulation)
    session.flush()
    refresh_regulation_text_summary(session, regulation)


def create_attachment(
    session: Session,
    regulation: RegulationRecord,
    *,
    filename: str,
    source_url: str = "",
    source_page_url: str = "",
    source_type: str,
    verification_usable: bool,
    sha256: str = "",
    stored_path: str = "",
    content_type: str = "",
    byte_size: int = 0,
    download_status: str = "metadata_only",
    download_error: str = "",
) -> RegulationAttachment:
    attachment = RegulationAttachment(
        regulation_id=regulation.id or 0,
        filename=filename,
        source_url=source_url,
        source_page_url=source_page_url,
        source_type=source_type,
        verification_usable=verification_usable,
        sha256=sha256,
        stored_path=stored_path,
        content_type=content_type,
        byte_size=byte_size,
        download_status=download_status,
        download_error=download_error,
    )
    session.add(attachment)
    session.flush()
    return attachment


def seed_source_file_attachments(
    session: Session,
    regulation: RegulationRecord,
    source_files: list[dict],
) -> None:
    if not regulation.id:
        session.flush()
    seed_urls = {str(item.get("url", "")) for item in source_files if item.get("url")}
    for existing in session.exec(
        select(RegulationAttachment).where(
            RegulationAttachment.regulation_id == regulation.id,
            RegulationAttachment.stored_path == "",
        )
    ).all():
        if existing.source_type in {"official_attachment", "reference_attachment"} and existing.source_url not in seed_urls:
            session.delete(existing)
    for source_file in source_files:
        url = str(source_file.get("url", ""))
        sha256 = str(source_file.get("sha256", ""))
        existing = session.exec(
            select(RegulationAttachment).where(
                RegulationAttachment.regulation_id == regulation.id,
                RegulationAttachment.source_url == url,
            )
        ).first()
        verification_usable = source_file.get("verification_usable", True) is not False
        source_type = "official_attachment" if verification_usable else "reference_attachment"
        filename = str(source_file.get("filename", "")) or Path(urlparse(url).path).name
        if existing is not None:
            if not existing.stored_path:
                existing.filename = filename
                existing.sha256 = sha256
                existing.source_page_url = regulation.official_url
                existing.source_type = source_type
                existing.verification_usable = verification_usable
                existing.download_status = existing.download_status or "metadata_only"
                session.add(existing)
            continue
        create_attachment(
            session,
            regulation,
            filename=filename,
            source_url=url,
            source_page_url=regulation.official_url,
            source_type=source_type,
            verification_usable=verification_usable,
            sha256=sha256,
            download_status="metadata_only",
        )


def seed_preset_regulations(session: Session) -> None:
    if not SEED_PATH.exists():
        return
    seeds = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    for seed in seeds:
        title = seed.get("title", "").strip()
        if not title:
            continue
        existing = session.exec(
            select(RegulationRecord).where(RegulationRecord.title == title)
        ).first()
        if existing is None and seed.get("reference_number"):
            existing = session.exec(
                select(RegulationRecord).where(
                    RegulationRecord.source_type == "preset",
                    RegulationRecord.reference_number == seed["reference_number"],
                )
            ).first()
        if existing is None:
            existing = RegulationRecord(**seed)
            session.add(existing)
            session.flush()
            seed_source_file_attachments(session, existing, seed.get("source_files", []))
            continue
        if existing.source_type != "preset" or existing.verification_status == "verified":
            continue
        for key, value in seed.items():
            if key in {"verification_status", "verified_by", "verified_at"}:
                continue
            setattr(existing, key, value)
        session.add(existing)
        session.flush()
        seed_source_file_attachments(session, existing, seed.get("source_files", []))
    session.commit()
