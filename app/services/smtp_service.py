import json
import smtplib
from email.mime.text import MIMEText
from pathlib import Path
from datetime import datetime

SETTINGS_FILE = Path("smtp_settings.json")
EXAMPLE_SETTINGS_FILE = Path("smtp_settings.example.json")
LOG_FILE = Path("smtp_delivery_log.jsonl")

def load_smtp_settings():
    path = SETTINGS_FILE if SETTINGS_FILE.exists() else EXAMPLE_SETTINGS_FILE
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}

def _effective_recipient(to_email, cfg):
    original_to = to_email
    test_mode = bool(cfg.get("smtp_test_mode", True))
    if test_mode and cfg.get("smtp_force_redirect_in_test", True):
        to_email = cfg.get("smtp_test_recipient_email") or cfg.get("smtp_test_redirect_email") or to_email
    return original_to, to_email, test_mode

def _decorate_subject(subject, cfg, test_mode):
    if test_mode and cfg.get("smtp_test_prefix_subject", True) and not subject.startswith("[TEST Fjord VI]"):
        return "[TEST Fjord VI] " + subject
    return subject

def _decorate_body(body_html, original_to, effective_to, test_mode):
    if not test_mode:
        return body_html
    aviso = f"""
    <div style="border:1px solid #f59e0b;background:#fffbeb;color:#7c2d12;padding:12px;border-radius:10px;margin-bottom:14px;font-family:Arial,sans-serif;font-size:13px;">
      <strong>MODO PRUEBA SMTP ACTIVO</strong><br>
      Destinatario original: {original_to}<br>
      Redirigido a: {effective_to}<br>
      Ningún socio real recibe este correo durante la prueba.
    </div>
    """
    return aviso + body_html

def _log(event, subject, original_to, effective_to, status, error=None, test_mode=True):
    row = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "event": event,
        "subject": subject,
        "original_to": original_to,
        "effective_to": effective_to,
        "status": status,
        "error": error,
        "test_mode": test_mode
    }
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

def send_email(subject, body_html, to_email, event="manual_test"):
    cfg = load_smtp_settings()
    original_to, effective_to, test_mode = _effective_recipient(to_email, cfg)
    subject = _decorate_subject(subject, cfg, test_mode)
    body_html = _decorate_body(body_html, original_to, effective_to, test_mode)

    if not cfg.get("smtp_enabled", False):
        _log(event, subject, original_to, effective_to, "blocked_smtp_disabled", None, test_mode)
        return {"ok": False, "reason": "smtp_disabled", "original_to": original_to, "effective_to": effective_to, "test_mode": test_mode}

    msg = MIMEText(body_html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = cfg.get("smtp_from_email")
    msg["To"] = effective_to

    try:
        server = smtplib.SMTP(cfg.get("smtp_host"), int(cfg.get("smtp_port", 587)), timeout=20)
        if cfg.get("smtp_tls", True):
            server.starttls()
        server.login(cfg.get("smtp_username"), cfg.get("smtp_password"))
        server.sendmail(cfg.get("smtp_from_email"), [effective_to], msg.as_string())
        server.quit()
        _log(event, subject, original_to, effective_to, "sent", None, test_mode)
        return {"ok": True, "original_to": original_to, "effective_to": effective_to, "test_mode": test_mode}
    except Exception as e:
        _log(event, subject, original_to, effective_to, "failed", str(e), test_mode)
        return {"ok": False, "error": str(e), "original_to": original_to, "effective_to": effective_to, "test_mode": test_mode}

def send_test_email(subject, body_html, to_email):
    return send_email(subject, body_html, to_email, event="email_prueba")
