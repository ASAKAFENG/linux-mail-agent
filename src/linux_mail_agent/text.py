"""Small email text utilities (no external parser dependencies)."""

from __future__ import annotations

import html as html_lib
import re
from html.parser import HTMLParser
from typing import List, Tuple


class _TextExtractor(HTMLParser):
    """Convert simple HTML to readable plain text."""

    BLOCK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip_depth += 1
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._skip_depth = max(0, self._skip_depth - 1)
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.parts.append(data)

    def text(self) -> str:
        raw = "".join(self.parts)
        # Collapse more than two newlines into two, then trim each line.
        lines = [ln.strip() for ln in re.split(r"\n+", raw)]
        return "\n".join(ln for ln in lines if ln).strip()


def html_to_text(html: str) -> str:
    """Best-effort HTML to text conversion."""
    extractor = _TextExtractor()
    try:
        extractor.feed(html)
        extractor.close()
    except Exception:
        return re.sub(r"<[^>]+>", "", html_lib.unescape(html))
    return extractor.text()


def decode_payload(part: object) -> str:
    """Decode an email part payload to a str without crashing on unknown CTE."""
    from email.message import Message

    msg = part if isinstance(part, Message) else None
    payload = msg.get_payload(decode=True) if msg is not None else None
    if payload is None:
        payload = part.get_payload() if hasattr(part, "get_payload") else b""
        if isinstance(payload, list):
            return ""
        if isinstance(payload, str):
            return payload
    charset = part.get_content_charset() or "utf-8"
    for enc in (charset, "utf-8", "latin-1"):
        try:
            return payload.decode(enc, errors="replace")
        except (LookupError, UnicodeDecodeError):
            continue
    return payload.decode("utf-8", errors="replace")


def body_from_message(msg: object) -> dict:
    """Return {'text': str, 'html': str|None, 'attachments': list} from EmailMessage."""
    from email.message import Message

    text_parts: List[str] = []
    html_parts: List[str] = []
    attachments = []

    for part in msg.walk() if isinstance(msg, Message) else []:
        if part.is_multipart():
            continue
        content_disposition = str(part.get("Content-Disposition", "")).lower()
        filename = part.get_filename()
        if filename or "attachment" in content_disposition:
            payload = part.get_payload(decode=True)
            if payload is None:
                payload = b""
            attachments.append(
                {
                    "filename": filename or "attachment",
                    "content_type": part.get_content_type(),
                    "size": len(payload),
                }
            )
            continue
        content_type = part.get_content_type()
        if content_type == "text/plain":
            text_parts.append(decode_payload(part))
        elif content_type == "text/html":
            html_parts.append(decode_payload(part))

    text = "\n".join(text_parts).strip()
    html = "\n".join(html_parts).strip() or None

    if not text and html:
        text = html_to_text(html)

    return {"text": text, "html": html, "attachments": attachments}


def preview(text: str, limit: int = 200) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
