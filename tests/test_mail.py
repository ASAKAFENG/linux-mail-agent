import pytest

from linux_mail_agent.config import MailConfig
from linux_mail_agent.mail import MailClient, MailError


def _client(read_only: bool = True) -> MailClient:
    cfg = MailConfig(
        imap_host="imap.example.com",
        imap_user="me@example.com",
        imap_password="secret",
        smtp_host="smtp.example.com",
        read_only=read_only,
    )
    return MailClient(cfg)


def test_read_only_blocks_send_before_network():
    with pytest.raises(MailError, match="read-only"):
        _client(read_only=True).send_email(
            to=["to@example.com"],
            subject="hi",
            body="hello",
        )


def test_read_only_blocks_flag_change_before_network():
    with pytest.raises(MailError, match="read-only"):
        _client(read_only=True).mark_seen("INBOX", "123")


def test_writable_client_passes_initial_checks():
    # No exception here means the read-only guard was not triggered; the
    # operation will fail later trying to connect to the fake host.
    client = _client(read_only=False)
    with pytest.raises(Exception) as exc_info:
        client.send_email(
            to=["to@example.com"],
            subject="hi",
            body="hello",
        )
    assert "read-only" not in str(exc_info.value).lower()


def _client_allowlisted(*addresses: str) -> MailClient:
    cfg = MailConfig(
        imap_host="imap.example.com",
        imap_user="me@example.com",
        imap_password="secret",
        smtp_host="smtp.example.com",
        read_only=False,
        allowed_to=tuple(addresses),
    )
    return MailClient(cfg)


def test_allowlist_blocks_outside_recipient():
    client = _client_allowlisted("me@example.com")
    with pytest.raises(MailError, match="MAIL_ALLOWED_TO"):
        client.send_email(
            to=["stranger@example.com"],
            subject="hi",
            body="hello",
        )


def test_allowlist_blocks_cc_outside_allowlist():
    client = _client_allowlisted("me@example.com")
    with pytest.raises(MailError, match="MAIL_ALLOWED_TO"):
        client.send_email(
            to=["me@example.com"],
            cc=["sneaky@example.com"],
            subject="hi",
            body="hello",
        )


def test_allowlist_allows_whitelisted_recipient():
    # Allowlisted recipient passes the guard; then fails on the fake SMTP host.
    client = _client_allowlisted("me@example.com")
    with pytest.raises(Exception) as exc_info:
        client.send_email(
            to=["Me@Example.com"],
            subject="hi",
            body="hello",
        )
    assert "MAIL_ALLOWED_TO" not in str(exc_info.value)
