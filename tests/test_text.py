from email.message import EmailMessage

from linux_mail_agent.text import body_from_message, html_to_text, preview


def test_html_to_text():
    html = "<html><body><h1>Hello</h1><p>World &amp; more</p></body></html>"
    text = html_to_text(html)
    assert "Hello" in text
    assert "World & more" in text


def test_preview_truncates():
    assert preview("a" * 300) == "a" * 199 + "…"
    assert preview("short") == "short"


def test_body_from_message_plain_and_html():
    msg = EmailMessage()
    msg.set_content("plain body")
    msg.add_alternative("<b>html body</b>", subtype="html")
    body = body_from_message(msg)
    assert body["text"] == "plain body"
    assert body["html"] == "<b>html body</b>"
    assert body["attachments"] == []


def test_body_from_message_attachment():
    msg = EmailMessage()
    msg.set_content("body")
    msg.add_attachment(b"data", maintype="text", subtype="plain", filename="a.txt")
    body = body_from_message(msg)
    assert body["attachments"] == [
        {"filename": "a.txt", "content_type": "text/plain", "size": 4}
    ]
