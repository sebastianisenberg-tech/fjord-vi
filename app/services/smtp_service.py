
import json
import smtplib
from email.mime.text import MIMEText
from pathlib import Path

SETTINGS_FILE = Path("smtp_settings.example.json")

def load_smtp_settings():
    if SETTINGS_FILE.exists():
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    return {}

def send_test_email(subject, body_html, to_email):
    cfg = load_smtp_settings()

    # TEST MODE redirect
    if cfg.get("smtp_test_mode", True):
        to_email = cfg.get("smtp_test_redirect_email", to_email)

    msg = MIMEText(body_html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = cfg.get("smtp_from_email")
    msg["To"] = to_email

    server = smtplib.SMTP(cfg.get("smtp_host"), cfg.get("smtp_port"))
    if cfg.get("smtp_tls", True):
        server.starttls()

    server.login(
        cfg.get("smtp_username"),
        cfg.get("smtp_password")
    )

    server.sendmail(
        cfg.get("smtp_from_email"),
        [to_email],
        msg.as_string()
    )

    server.quit()

    return {
        "ok": True,
        "sent_to": to_email,
        "test_mode": cfg.get("smtp_test_mode", True)
    }
