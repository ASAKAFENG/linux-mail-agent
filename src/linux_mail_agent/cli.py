"""Command-line interface for linux-mail-agent.

The CLI is useful for humans, cron jobs, and shell-based agents. It outputs
JSON by default so it can be piped into other tools.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, List, Optional, Sequence

from .config import load_config
from .mail import MailClient, MailError


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _csv_list(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mailagent",
        description="Linux email agent: IMAP/SMTP access for humans and AI agents.",
    )
    parser.add_argument("--env-file", help="Path to an optional .env file.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_serve = sub.add_parser("serve", help="Run the MCP server for AI agents.")
    p_serve.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport (default: stdio).",
    )
    sub.add_parser("check", help="Check configuration (no secrets printed).")
    sub.add_parser("folders", help="List IMAP mailboxes/folders.")

    p_list = sub.add_parser("list", help="List recent emails.")
    p_list.add_argument("--mailbox", default="INBOX")
    p_list.add_argument("--limit", type=int, default=20)
    p_list.add_argument("--unseen-only", action="store_true")
    p_list.add_argument("--from", dest="from_addr")
    p_list.add_argument("--to", dest="to_addr")
    p_list.add_argument("--subject")
    p_list.add_argument("--body")
    p_list.add_argument("--since")
    p_list.add_argument("--before")

    p_search = sub.add_parser("search", help="Search emails by text.")
    p_search.add_argument("query")
    p_search.add_argument("--mailbox", default="INBOX")
    p_search.add_argument("--limit", type=int, default=20)

    p_show = sub.add_parser("show", help="Read a full email by UID.")
    p_show.add_argument("mailbox")
    p_show.add_argument("uid")
    p_show.add_argument("--mark-seen", action="store_true")

    p_send = sub.add_parser("send", help="Send an email.")
    p_send.add_argument("--to", required=True, help="Comma-separated recipients")
    p_send.add_argument("--subject", required=True)
    p_send.add_argument("--body", default="")
    p_send.add_argument("--html")
    p_send.add_argument("--cc")
    p_send.add_argument("--bcc")
    p_send.add_argument("--attachment", action="append", default=[])
    p_send.add_argument("--reply-to")

    p_reply = sub.add_parser("reply", help="Reply to an email by UID.")
    p_reply.add_argument("mailbox")
    p_reply.add_argument("uid")
    p_reply.add_argument("--body", required=True)
    p_reply.add_argument("--all", action="store_true", dest="reply_all")
    p_reply.add_argument("--attachment", action="append", default=[])

    p_fwd = sub.add_parser("forward", help="Forward an email by UID.")
    p_fwd.add_argument("mailbox")
    p_fwd.add_argument("uid")
    p_fwd.add_argument("--to", required=True)
    p_fwd.add_argument("--body", default="")
    p_fwd.add_argument("--attachment", action="append", default=[])

    p_mark_seen = sub.add_parser("mark-seen", help="Mark an email as read.")
    p_mark_seen.add_argument("mailbox")
    p_mark_seen.add_argument("uid")

    p_mark_unseen = sub.add_parser("mark-unseen", help="Mark an email as unread.")
    p_mark_unseen.add_argument("mailbox")
    p_mark_unseen.add_argument("uid")

    p_move = sub.add_parser("move", help="Move an email to another mailbox.")
    p_move.add_argument("mailbox")
    p_move.add_argument("uid")
    p_move.add_argument("destination")

    p_delete = sub.add_parser("delete", help="Delete an email.")
    p_delete.add_argument("mailbox")
    p_delete.add_argument("uid")

    p_attach = sub.add_parser("attachment", help="Save an attachment from an email.")
    p_attach.add_argument("mailbox")
    p_attach.add_argument("uid")
    p_attach.add_argument("--index", type=int)
    p_attach.add_argument("--filename")
    p_attach.add_argument("--save-dir")

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            # Imported here so `mailagent --help` stays fast without MCP.
            from .server import main as serve_main

            serve_main(transport=args.transport)
            return 0

        cfg = load_config(args.env_file)
        client = MailClient(cfg)

        if args.command == "check":
            _print_json(cfg.public_status())
        elif args.command == "folders":
            _print_json(client.list_folders())
        elif args.command == "list":
            _print_json(
                client.list_emails(
                    mailbox=args.mailbox,
                    limit=args.limit,
                    unseen_only=args.unseen_only,
                    from_addr=args.from_addr,
                    to_addr=args.to_addr,
                    subject=args.subject,
                    body=args.body,
                    since=args.since,
                    before=args.before,
                )
            )
        elif args.command == "search":
            _print_json(
                client.list_emails(
                    mailbox=args.mailbox,
                    limit=args.limit,
                    subject=args.query,
                    body=args.query,
                )
            )
        elif args.command == "show":
            _print_json(client.read_email(args.mailbox, args.uid, mark_seen=args.mark_seen))
        elif args.command == "send":
            _print_json(
                client.send_email(
                    to=_csv_list(args.to) or [],
                    subject=args.subject,
                    body=args.body,
                    html=args.html,
                    cc=_csv_list(args.cc),
                    bcc=_csv_list(args.bcc),
                    attachments=args.attachment,
                    reply_to=args.reply_to,
                )
            )
        elif args.command == "reply":
            _print_json(
                client.reply_email(
                    mailbox=args.mailbox,
                    uid=args.uid,
                    body=args.body,
                    reply_all=args.reply_all,
                    attachments=args.attachment,
                )
            )
        elif args.command == "forward":
            _print_json(
                client.forward_email(
                    mailbox=args.mailbox,
                    uid=args.uid,
                    to=_csv_list(args.to) or [],
                    body=args.body,
                    attachments=args.attachment,
                )
            )
        elif args.command == "mark-seen":
            _print_json(client.mark_seen(args.mailbox, args.uid, seen=True))
        elif args.command == "mark-unseen":
            _print_json(client.mark_seen(args.mailbox, args.uid, seen=False))
        elif args.command == "move":
            _print_json(client.move_email(args.mailbox, args.uid, args.destination))
        elif args.command == "delete":
            _print_json(client.delete_email(args.mailbox, args.uid))
        elif args.command == "attachment":
            _print_json(
                client.save_attachment(
                    mailbox=args.mailbox,
                    uid=args.uid,
                    attachment_index=args.index,
                    filename=args.filename,
                    save_dir=args.save_dir,
                )
            )
        else:  # pragma: no cover
            parser.print_help()
            return 2
        return 0
    except (MailError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
