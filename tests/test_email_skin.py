from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")


def test_email_skin_generates_html_alternative_only_at_smtp_send():
    assert "msg.add_alternative(build_notification_html_email" in MAIN
    assert "RC8 Email Skin: HTML visual sin tocar endpoints" in MAIN


def test_email_skin_keeps_queue_email_lightweight():
    queue_start = MAIN.index("def queue_email(")
    queue_end = MAIN.index("RETRYABLE_NOTIFICATION_STATUSES", queue_start)
    block = MAIN[queue_start:queue_end]
    assert "build_notification_html_email" not in block
    assert "add_alternative" not in block
