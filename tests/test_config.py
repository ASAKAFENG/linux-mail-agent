import pytest

from linux_mail_agent.config import MailConfig, load_config
from linux_mail_agent.mail import build_search_criteria, normalize_imap_date


def test_config_from_env_requires_credentials():
    with pytest.raises(ValueError):
        MailConfig.from_env({})


def test_config_defaults():
    cfg = MailConfig.from_env(
        {
            "MAIL_IMAP_HOST": "imap.example.com",
            "MAIL_IMAP_USER": "me@example.com",
            "MAIL_IMAP_PASSWORD": "secret",
        }
    )
    assert cfg.imap_port == 993
    assert cfg.imap_ssl is True
    assert cfg.smtp_host is None
    assert cfg.effective_smtp_host == "imap.example.com"
    assert cfg.effective_from == "me@example.com"
    assert cfg.public_status()["configured"]


def test_config_read_only():
    cfg = MailConfig.from_env(
        {
            "MAIL_IMAP_HOST": "imap.example.com",
            "MAIL_IMAP_USER": "me@example.com",
            "MAIL_IMAP_PASSWORD": "secret",
            "MAIL_READ_ONLY": "true",
        }
    )
    assert cfg.read_only is True
    assert cfg.public_status()["read_only"] is True


def test_config_allowed_to_parsed():
    cfg = MailConfig.from_env(
        {
            "MAIL_IMAP_HOST": "imap.example.com",
            "MAIL_IMAP_USER": "me@example.com",
            "MAIL_IMAP_PASSWORD": "secret",
            "MAIL_ALLOWED_TO": "me@example.com, other@example.com",
        }
    )
    assert cfg.allowed_to == ("me@example.com", "other@example.com")
    assert cfg.public_status()["allowed_to"] == ["me@example.com", "other@example.com"]


def test_config_allowed_to_unset_is_none():
    cfg = MailConfig.from_env(
        {
            "MAIL_IMAP_HOST": "imap.example.com",
            "MAIL_IMAP_USER": "me@example.com",
            "MAIL_IMAP_PASSWORD": "secret",
        }
    )
    assert cfg.allowed_to is None
    assert cfg.public_status()["allowed_to"] is None


def test_config_smtp_ssl_port_auto():
    cfg = MailConfig.from_env(
        {
            "MAIL_IMAP_HOST": "imap.example.com",
            "MAIL_IMAP_USER": "me@example.com",
            "MAIL_IMAP_PASSWORD": "secret",
            "MAIL_SMTP_HOST": "smtp.example.com",
            "MAIL_SMTP_SSL": "true",
        }
    )
    assert cfg.smtp_port == 465
    assert cfg.smtp_ssl is True


def test_normalize_imap_date():
    assert normalize_imap_date("2026-08-01") == "01-Aug-2026"
    assert normalize_imap_date("1-Aug-2026") == "01-Aug-2026"
    with pytest.raises(ValueError):
        normalize_imap_date("not-a-date")


def test_build_search_criteria():
    criteria = build_search_criteria(
        from_addr="alice@example.com",
        unseen_only=True,
        since="2026-08-01",
    )
    assert criteria == ["FROM", '"alice@example.com"', "SINCE", "01-Aug-2026", "UNSEEN"]
    assert build_search_criteria() == ["ALL"]
