"""MCP server exposing Linux email access to AI agents.

Run with:
    mailagent serve
    # or directly:
    python -m linux_mail_agent.serve
"""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from .config import load_config
from .mail import MailClient, MailError


def create_server(name: str = "linux-mail-agent") -> FastMCP:
    mcp = FastMCP(
        name,
        instructions=(
            "Linux email gateway. Tools talk to the configured IMAP/SMTP account. "
            "Always pass UIDs returned by mail_list/mail_search to read/move/delete. "
            "Do not expose the password or other secrets in tool results."
        ),
    )

    def client() -> MailClient:
        return MailClient(load_config())

    @mcp.tool()
    def mail_check_config() -> dict:
        """Check the current account configuration (never returns secrets)."""
        try:
            cfg = load_config()
            return cfg.public_status()
        except Exception as exc:
            return {"configured": False, "error": str(exc)}

    @mcp.tool()
    def mail_list_folders() -> list[str]:
        """List IMAP mailboxes/folders (e.g. INBOX, Sent, Archive)."""
        return client().list_folders()

    @mcp.tool()
    def mail_list(
        mailbox: str = "INBOX",
        limit: int = 20,
        unseen_only: bool = False,
        from_addr: Optional[str] = None,
        to_addr: Optional[str] = None,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        since: Optional[str] = None,
        before: Optional[str] = None,
    ) -> list[dict]:
        """List recent emails in a mailbox.

        Args:
            mailbox: IMAP mailbox name, e.g. "INBOX".
            limit: Maximum number of messages to return (newest first).
            unseen_only: Only return unread messages.
            from_addr: Filter by sender address/substring.
            to_addr: Filter by recipient address/substring.
            subject: Filter by subject substring.
            body: Filter by body substring.
            since: Only messages since YYYY-MM-DD (or DD-Mon-YYYY).
            before: Only messages before YYYY-MM-DD (or DD-Mon-YYYY).
        """
        return client().list_emails(
            mailbox=mailbox,
            limit=limit,
            unseen_only=unseen_only,
            from_addr=from_addr,
            to_addr=to_addr,
            subject=subject,
            body=body,
            since=since,
            before=before,
        )

    @mcp.tool()
    def mail_search(
        query: str,
        mailbox: str = "INBOX",
        limit: int = 20,
    ) -> list[dict]:
        """Search email subjects and bodies for a free-text query."""
        return client().list_emails(
            mailbox=mailbox,
            limit=limit,
            subject=query,
            body=query,
        )

    @mcp.tool()
    def mail_read(mailbox: str, uid: str, mark_seen: bool = False) -> dict:
        """Read a full email by UID. Set mark_seen=True to also mark it as read."""
        return client().read_email(mailbox=mailbox, uid=uid, mark_seen=mark_seen)

    @mcp.tool()
    def mail_mark_seen(mailbox: str, uid: str) -> dict:
        """Mark an email as read."""
        return client().mark_seen(mailbox=mailbox, uid=uid, seen=True)

    @mcp.tool()
    def mail_mark_unseen(mailbox: str, uid: str) -> dict:
        """Mark an email as unread."""
        return client().mark_seen(mailbox=mailbox, uid=uid, seen=False)

    @mcp.tool()
    def mail_move(mailbox: str, uid: str, destination: str) -> dict:
        """Move an email to another mailbox."""
        return client().move_email(mailbox=mailbox, uid=uid, destination=destination)

    @mcp.tool()
    def mail_delete(mailbox: str, uid: str) -> dict:
        """Delete (expunge) an email from a mailbox."""
        return client().delete_email(mailbox=mailbox, uid=uid)

    @mcp.tool()
    def mail_save_attachment(
        mailbox: str,
        uid: str,
        attachment_index: Optional[int] = None,
        filename: Optional[str] = None,
        save_dir: Optional[str] = None,
    ) -> dict:
        """Save an email attachment to local disk and return its path.

        Specify either attachment_index (0-based) or filename; if neither is
        given, the first attachment is saved.
        """
        return client().save_attachment(
            mailbox=mailbox,
            uid=uid,
            attachment_index=attachment_index,
            filename=filename,
            save_dir=save_dir,
        )

    @mcp.tool()
    def mail_send(
        to: list[str],
        subject: str,
        body: str = "",
        cc: Optional[list[str]] = None,
        bcc: Optional[list[str]] = None,
        html: Optional[str] = None,
        attachments: Optional[list[str]] = None,
        reply_to: Optional[str] = None,
    ) -> dict:
        """Send a new email.

        Args:
            to: Recipient email addresses.
            subject: Email subject.
            body: Plain-text body.
            cc: CC recipients.
            bcc: BCC recipients.
            html: Optional HTML body (added as an alternative part).
            attachments: Local file paths to attach.
            reply_to: Optional Reply-To address.
        """
        return client().send_email(
            to=to,
            subject=subject,
            body=body,
            cc=cc,
            bcc=bcc,
            html=html,
            attachments=attachments,
            reply_to=reply_to,
        )

    @mcp.tool()
    def mail_reply(
        mailbox: str,
        uid: str,
        body: str,
        reply_all: bool = False,
        attachments: Optional[list[str]] = None,
    ) -> dict:
        """Reply to an email by UID. The agent provides the reply body."""
        return client().reply_email(
            mailbox=mailbox,
            uid=uid,
            body=body,
            reply_all=reply_all,
            attachments=attachments,
        )

    @mcp.tool()
    def mail_forward(
        mailbox: str,
        uid: str,
        to: list[str],
        body: str = "",
        attachments: Optional[list[str]] = None,
    ) -> dict:
        """Forward an email by UID to new recipients."""
        return client().forward_email(
            mailbox=mailbox,
            uid=uid,
            to=to,
            body=body,
            attachments=attachments,
        )

    return mcp


def main(transport: str = "stdio") -> None:
    mcp = create_server()
    mcp.run(transport=transport)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
