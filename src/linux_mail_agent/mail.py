"""IMAP/SMTP operations used by both the MCP server and the CLI."""

from __future__ import annotations

import imaplib
import os
import re
import smtplib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage, Message
from email.parser import BytesParser
from email.policy import default
from email.utils import formataddr, make_msgid, parsedate_to_datetime
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from .config import MailConfig
from .text import body_from_message, preview

MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


class MailError(ValueError):
    """Raised for user-facing email operation errors."""


def _parse_mailbox_list(lines: Iterable[bytes]) -> List[str]:
    """Extract mailbox names from imaplib LIST responses."""
    names: List[str] = []
    pattern = re.compile(r'"((?:[^"\\]|\\.)*)"\s*$')
    for line in lines:
        if not line:
            continue
        text = line.decode("utf-8", "replace")
        match = pattern.search(text)
        if match:
            names.append(match.group(1).replace('\\"', '"').replace("\\\\", "\\"))
        else:
            # Last token without quotes is a mailbox name too.
            tokens = text.split()
            if tokens:
                names.append(tokens[-1])
    return names


def normalize_imap_date(value: str) -> str:
    """Convert ISO YYYY-MM-DD or IMAP 'd-MMM-yyyy' to IMAP date format."""
    value = value.strip()
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
        return dt.strftime("%d-%b-%Y")
    except ValueError:
        pass
    try:
        dt = datetime.strptime(value, "%d-%b-%Y")
        return dt.strftime("%d-%b-%Y")
    except ValueError:
        pass
    raise MailError(
        f"Invalid date {value!r}; use YYYY-MM-DD or DD-Mon-YYYY (e.g. 2026-08-01)."
    )


def build_search_criteria(
    from_addr: Optional[str] = None,
    to_addr: Optional[str] = None,
    subject: Optional[str] = None,
    body: Optional[str] = None,
    since: Optional[str] = None,
    before: Optional[str] = None,
    unseen_only: bool = False,
) -> List[str]:
    """Build an IMAP SEARCH criteria list."""
    criteria: List[str] = []
    if from_addr:
        criteria += ["FROM", f'"{from_addr}"']
    if to_addr:
        criteria += ["TO", f'"{to_addr}"']
    if subject:
        criteria += ["SUBJECT", f'"{subject}"']
    if body:
        criteria += ["BODY", f'"{body}"']
    if since:
        criteria += ["SINCE", normalize_imap_date(since)]
    if before:
        criteria += ["BEFORE", normalize_imap_date(before)]
    if unseen_only:
        criteria += ["UNSEEN"]
    if not criteria:
        criteria = ["ALL"]
    return criteria


def _parse_flags(raw_flags: bytes) -> dict:
    flags = raw_flags.decode("utf-8", "replace")
    lowered = flags.lower()
    return {
        "seen": "\\seen" in lowered,
        "answered": "\\answered" in lowered,
        "flagged": "\\flagged" in lowered,
        "draft": "\\draft" in lowered,
        "recent": "\\recent" in lowered,
        "raw": flags,
    }


def _header(msg: Message, name: str) -> str:
    value = msg.get(name, "")
    return value if isinstance(value, str) else str(value)


@dataclass(slots=True)
class MailClient:
    """High-level mail operations with one connection per operation."""

    config: MailConfig

    def _connect_imap(self) -> imaplib.IMAP4:
        cfg = self.config
        try:
            if cfg.imap_ssl:
                conn = imaplib.IMAP4_SSL(cfg.imap_host, cfg.imap_port, timeout=cfg.timeout)
            else:
                conn = imaplib.IMAP4(cfg.imap_host, cfg.imap_port, timeout=cfg.timeout)
            conn.login(cfg.imap_user, cfg.imap_password)
            return conn
        except Exception as exc:  # pragma: no cover - network errors vary
            raise MailError(f"IMAP connection failed: {exc}") from exc

    def _ensure_writable(self) -> None:
        if self.config.read_only:
            raise MailError("Mail account is in read-only mode (MAIL_READ_ONLY=true).")

    def _ensure_recipients_allowed(
        self,
        to: Sequence[str],
        cc: Optional[Sequence[str]],
        bcc: Optional[Sequence[str]],
    ) -> None:
        """Refuse to send if any recipient is outside the MAIL_ALLOWED_TO allowlist."""
        allowed = self.config.allowed_to
        if not allowed:
            return
        normalized = {a.lower() for a in allowed}
        offenders = [
            addr
            for addr in list(to) + list(cc or []) + list(bcc or [])
            if addr.strip().lower() not in normalized
        ]
        if offenders:
            raise MailError(
                "Recipient(s) not in MAIL_ALLOWED_TO allowlist: "
                + ", ".join(offenders)
            )

    def _select(self, conn: imaplib.IMAP4, mailbox: str, readonly: bool = True) -> None:
        try:
            typ, data = conn.select(mailbox, readonly=readonly)
            if typ != "OK":
                raise MailError(f"Could not select mailbox {mailbox!r}: {data!r}")
        except imaplib.IMAP4.error as exc:
            raise MailError(f"Could not select mailbox {mailbox!r}: {exc}") from exc

    def list_folders(self) -> List[str]:
        conn = self._connect_imap()
        try:
            typ, data = conn.list()
            if typ != "OK":
                raise MailError(f"LIST failed: {data!r}")
            return _parse_mailbox_list(data or [])
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def search_uids(
        self,
        mailbox: str = "INBOX",
        from_addr: Optional[str] = None,
        to_addr: Optional[str] = None,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        since: Optional[str] = None,
        before: Optional[str] = None,
        unseen_only: bool = False,
    ) -> List[str]:
        conn = self._connect_imap()
        try:
            self._select(conn, mailbox, readonly=True)
            criteria = build_search_criteria(
                from_addr=from_addr,
                to_addr=to_addr,
                subject=subject,
                body=body,
                since=since,
                before=before,
                unseen_only=unseen_only,
            )
            typ, data = conn.uid("search", None, *criteria)
            if typ != "OK":
                raise MailError(f"SEARCH failed: {data!r}")
            if not data or not data[0]:
                return []
            return data[0].decode("ascii", "replace").split()
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def list_emails(
        self,
        mailbox: str = "INBOX",
        limit: int = 20,
        from_addr: Optional[str] = None,
        to_addr: Optional[str] = None,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        since: Optional[str] = None,
        before: Optional[str] = None,
        unseen_only: bool = False,
    ) -> List[dict]:
        """Return a lightweight summary of the most recent matching emails."""
        uids = self.search_uids(
            mailbox=mailbox,
            from_addr=from_addr,
            to_addr=to_addr,
            subject=subject,
            body=body,
            since=since,
            before=before,
            unseen_only=unseen_only,
        )
        if not uids:
            return []

        selected = uids[-limit:] if limit > 0 else uids
        conn = self._connect_imap()
        try:
            self._select(conn, mailbox, readonly=True)
            results: List[dict] = []
            for uid in selected:
                try:
                    typ, data = conn.uid(
                        "fetch",
                        uid,
                        "(BODY.PEEK[HEADER.FIELDS (FROM TO CC SUBJECT DATE MESSAGE-ID)] "
                        "BODY.PEEK[TEXT]<0.512> FLAGS)",
                    )
                    if typ != "OK":
                        # Some servers dislike partial BODY[TEXT] fetches; fall
                        # back to header-only summaries.
                        typ, data = conn.uid(
                            "fetch",
                            uid,
                            "(BODY.PEEK[HEADER.FIELDS (FROM TO CC SUBJECT DATE MESSAGE-ID)] FLAGS)",
                        )
                        if typ != "OK":
                            continue
                    header_bytes = b""
                    body_bytes = b""
                    flags_raw = b""
                    for item in data:
                        if isinstance(item, tuple):
                            label = item[0].decode("utf-8", "replace").upper() if isinstance(item[0], bytes) else ""
                            if "HEADER.FIELDS" in label:
                                header_bytes = item[1] if isinstance(item[1], bytes) else b""
                            elif "BODY[TEXT]" in label:
                                body_bytes = item[1] if isinstance(item[1], bytes) else b""
                        elif isinstance(item, bytes):
                            text = item.decode("utf-8", "replace")
                            if "FLAGS" in text.upper():
                                flags_raw = item
                    msg = BytesParser(policy=default).parsebytes(header_bytes or b"")
                    body_text = body_bytes.decode("utf-8", "replace")
                    results.append(
                        {
                            "uid": uid,
                            "mailbox": mailbox,
                            "subject": _header(msg, "Subject"),
                            "from": _header(msg, "From"),
                            "to": _header(msg, "To"),
                            "date": _header(msg, "Date"),
                            "message_id": _header(msg, "Message-ID"),
                            "flags": _parse_flags(flags_raw),
                            "preview": preview(body_text, 200),
                        }
                    )
                except Exception:
                    # Never let one broken message hide the whole mailbox.
                    continue
            return results
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def read_email(self, mailbox: str, uid: str, mark_seen: bool = False) -> dict:
        """Return a full email with body and attachment metadata."""
        conn = self._connect_imap()
        try:
            self._select(conn, mailbox, readonly=not mark_seen)
            if mark_seen:
                self._ensure_writable()
                try:
                    conn.uid("store", uid, "+FLAGS", "(\\Seen)")
                except Exception:
                    pass
            typ, data = conn.uid("fetch", uid, "(RFC822 FLAGS)")
            if typ != "OK":
                raise MailError(f"Failed to fetch UID {uid} from {mailbox!r}: {data!r}")
            raw = b""
            flags_raw = b""
            for item in data:
                if isinstance(item, tuple):
                    raw = item[1] if isinstance(item[1], bytes) else b""
                elif isinstance(item, bytes):
                    if "FLAGS" in item.decode("utf-8", "replace").upper():
                        flags_raw = item
            if not raw:
                raise MailError(f"UID {uid} not found in {mailbox!r}")
            msg = BytesParser(policy=default).parsebytes(raw)
            body = body_from_message(msg)
            return {
                "uid": uid,
                "mailbox": mailbox,
                "subject": _header(msg, "Subject"),
                "from": _header(msg, "From"),
                "to": _header(msg, "To"),
                "cc": _header(msg, "Cc"),
                "date": _header(msg, "Date"),
                "message_id": _header(msg, "Message-ID"),
                "in_reply_to": _header(msg, "In-Reply-To"),
                "references": _header(msg, "References"),
                "flags": _parse_flags(flags_raw),
                "text": body["text"],
                "html": body["html"],
                "attachments": body["attachments"],
            }
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def save_attachment(
        self,
        mailbox: str,
        uid: str,
        attachment_index: Optional[int] = None,
        filename: Optional[str] = None,
        save_dir: Optional[str] = None,
    ) -> dict:
        """Save one attachment to disk and return its path."""
        conn = self._connect_imap()
        try:
            self._select(conn, mailbox, readonly=True)
            typ, data = conn.uid("fetch", uid, "(RFC822)")
            if typ != "OK":
                raise MailError(f"Failed to fetch UID {uid} from {mailbox!r}: {data!r}")
            raw = b""
            for item in data:
                if isinstance(item, tuple):
                    raw = item[1] if isinstance(item[1], bytes) else b""
                    break
            if not raw:
                raise MailError(f"UID {uid} not found in {mailbox!r}")
            msg = BytesParser(policy=default).parsebytes(raw)
            candidates = []
            for part in msg.walk():
                if part.is_multipart():
                    continue
                part_filename = part.get_filename()
                content_disposition = str(part.get("Content-Disposition", "")).lower()
                if part_filename or "attachment" in content_disposition:
                    candidates.append(part)
            if attachment_index is not None:
                if attachment_index < 0 or attachment_index >= len(candidates):
                    raise MailError(
                        f"Attachment index {attachment_index} out of range (0..{max(len(candidates)-1,0)})"
                    )
                part = candidates[attachment_index]
            elif filename:
                matches = [p for p in candidates if p.get_filename() == filename]
                if not matches:
                    raise MailError(f"No attachment named {filename!r} in UID {uid}")
                part = matches[0]
            else:
                if not candidates:
                    raise MailError(f"UID {uid} has no attachments")
                part = candidates[0]

            payload = part.get_payload(decode=True) or b""
            out_dir = Path(save_dir) if save_dir else self.config.attachment_dir
            out_dir.mkdir(parents=True, exist_ok=True)
            safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", part.get_filename() or "attachment")
            out_path = out_dir / f"{uid}_{safe_name}"
            out_path.write_bytes(payload)
            return {
                "path": str(out_path),
                "filename": part.get_filename() or safe_name,
                "size": len(payload),
                "content_type": part.get_content_type(),
            }
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def mark_seen(self, mailbox: str, uid: str, seen: bool = True) -> dict:
        return self._store_flags(mailbox, uid, "\\Seen", add=seen)

    def mark_flagged(self, mailbox: str, uid: str, flagged: bool = True) -> dict:
        return self._store_flags(mailbox, uid, "\\Flagged", add=flagged)

    def _store_flags(self, mailbox: str, uid: str, flag: str, add: bool) -> dict:
        self._ensure_writable()
        conn = self._connect_imap()
        try:
            self._select(conn, mailbox, readonly=False)
            operation = "+FLAGS" if add else "-FLAGS"
            typ, data = conn.uid("store", uid, operation, f"({flag})")
            if typ != "OK":
                raise MailError(f"Failed to update flags for UID {uid}: {data!r}")
            return {"uid": uid, "mailbox": mailbox, "flag": flag, "set": add, "ok": True}
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def move_email(self, mailbox: str, uid: str, destination: str) -> dict:
        self._ensure_writable()
        conn = self._connect_imap()
        try:
            self._select(conn, mailbox, readonly=False)
            # IMAP MOVE is nicer, but fall back to COPY + STORE + EXPUNGE.
            typ, data = conn.uid("move", uid, destination)
            if typ == "OK":
                return {"uid": uid, "from": mailbox, "to": destination, "ok": True}
            typ, data = conn.uid("copy", uid, destination)
            if typ != "OK":
                raise MailError(f"COPY failed for UID {uid}: {data!r}")
            conn.uid("store", uid, "+FLAGS", "(\\Deleted)")
            conn.expunge()
            return {"uid": uid, "from": mailbox, "to": destination, "ok": True}
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def delete_email(self, mailbox: str, uid: str) -> dict:
        self._ensure_writable()
        conn = self._connect_imap()
        try:
            self._select(conn, mailbox, readonly=False)
            typ, data = conn.uid("store", uid, "+FLAGS", "(\\Deleted)")
            if typ != "OK":
                raise MailError(f"Failed to mark UID {uid} as deleted: {data!r}")
            conn.expunge()
            return {"uid": uid, "mailbox": mailbox, "deleted": True}
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    # ------------------------------------------------------------------ SMTP
    def send_email(
        self,
        to: Sequence[str],
        subject: str,
        body: str = "",
        cc: Optional[Sequence[str]] = None,
        bcc: Optional[Sequence[str]] = None,
        html: Optional[str] = None,
        attachments: Optional[Sequence[str]] = None,
        reply_to: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
    ) -> dict:
        """Send a plain/HTML email with optional file attachments."""
        self.config.require_smtp()
        self._ensure_writable()
        if not to:
            raise MailError("At least one recipient is required in 'to'.")
        self._ensure_recipients_allowed(to, cc, bcc)

        msg = EmailMessage()
        if body:
            msg.set_content(body)
        if html:
            if body:
                msg.add_alternative(html, subtype="html")
            else:
                msg.set_content(html, subtype="html")

        from_addr = self.config.effective_from
        msg["From"] = formataddr((self.config.from_name, from_addr)) if self.config.from_name else from_addr
        msg["To"] = ", ".join(to)
        if cc:
            msg["Cc"] = ", ".join(cc)
        if bcc:
            msg["Bcc"] = ", ".join(bcc)
        msg["Subject"] = subject
        msg["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
        msg["Message-ID"] = make_msgid(domain=from_addr.split("@")[-1] if "@" in from_addr else "localhost")
        if reply_to:
            msg["Reply-To"] = reply_to
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
        if references:
            msg["References"] = references

        for path in attachments or []:
            path = os.path.expanduser(path)
            if not os.path.isfile(path):
                raise MailError(f"Attachment file not found: {path}")
            with open(path, "rb") as fh:
                payload = fh.read()
            maintype, subtype = _guess_mime(path)
            msg.add_attachment(
                payload,
                maintype=maintype,
                subtype=subtype,
                filename=os.path.basename(path),
            )

        self._smtp_send(msg, to, cc, bcc)
        return {
            "ok": True,
            "to": list(to),
            "cc": list(cc or []),
            "bcc": list(bcc or []),
            "subject": subject,
            "attachments": list(attachments or []),
        }

    def reply_email(
        self,
        mailbox: str,
        uid: str,
        body: str,
        reply_all: bool = False,
        attachments: Optional[Sequence[str]] = None,
    ) -> dict:
        original = self.read_email(mailbox, uid)
        subject = original["subject"]
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        # Best-effort recipients for reply/reply-all.
        from_header = original["from"]
        to_header = original["to"]
        cc_header = original.get("cc") or ""
        recipients = _address_list(from_header)
        cc_list = _address_list(cc_header) if reply_all else []
        if reply_all:
            for addr in _address_list(to_header):
                if addr not in recipients:
                    recipients.append(addr)
        if not recipients:
            raise MailError("Could not determine a reply address from the original email.")
        refs = " ".join(x for x in [original.get("in_reply_to", ""), original.get("references", "")] if x)
        return self.send_email(
            to=recipients,
            cc=cc_list,
            subject=subject,
            body=body,
            attachments=attachments,
            in_reply_to=original.get("message_id"),
            references=refs,
        )

    def forward_email(
        self,
        mailbox: str,
        uid: str,
        to: Sequence[str],
        body: str,
        attachments: Optional[Sequence[str]] = None,
    ) -> dict:
        original = self.read_email(mailbox, uid)
        subject = original["subject"]
        if not subject.lower().startswith("fwd:"):
            subject = f"Fwd: {subject}"
        quoted = _quote_original(original)
        full_body = f"{body}\n\n{quoted}" if body else quoted
        return self.send_email(
            to=to,
            subject=subject,
            body=full_body,
            attachments=attachments,
            in_reply_to=original.get("message_id"),
        )

    def _smtp_send(
        self,
        msg: EmailMessage,
        to: Sequence[str],
        cc: Optional[Sequence[str]],
        bcc: Optional[Sequence[str]],
    ) -> None:
        cfg = self.config
        host = cfg.effective_smtp_host
        recipients = list(to) + list(cc or []) + list(bcc or [])
        try:
            if cfg.smtp_ssl:
                smtp = smtplib.SMTP_SSL(host, cfg.smtp_port, timeout=cfg.timeout)
            else:
                smtp = smtplib.SMTP(host, cfg.smtp_port, timeout=cfg.timeout)
                if cfg.smtp_starttls:
                    smtp.ehlo()
                    smtp.starttls()
                    smtp.ehlo()
            smtp.login(cfg.imap_user, cfg.imap_password)
            smtp.send_message(msg, to_addrs=recipients)
            smtp.quit()
        except Exception as exc:  # pragma: no cover - SMTP errors vary
            raise MailError(f"SMTP send failed: {exc}") from exc


def _guess_mime(path: str) -> Tuple[str, str]:
    import mimetypes

    mime, _ = mimetypes.guess_type(path)
    if mime:
        main, _, sub = mime.partition("/")
        return main, sub
    return "application", "octet-stream"


def _address_list(value: str) -> List[str]:
    """Extract email addresses from a raw From/To/Cc header."""
    from email.utils import getaddresses

    pairs = getaddresses([value])
    return [addr for _, addr in pairs if addr]


def _quote_original(original: dict) -> str:
    lines = []
    lines.append(f"---------- Original message ----------")
    lines.append(f"From: {original['from']}")
    lines.append(f"Date: {original['date']}")
    lines.append(f"Subject: {original['subject']}")
    lines.append("")
    lines.append(original.get("text") or "")
    return "\n".join(lines)
