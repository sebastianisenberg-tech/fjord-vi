from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
ADMIN = (ROOT / "templates/admin.html").read_text(encoding="utf-8")


def test_rc2_retry_only_for_failed_or_expired():
    assert 'RETRYABLE_NOTIFICATION_STATUSES = {"failed", "expired"}' in MAIN
    assert "def notification_is_retryable" in MAIN
    assert "reintento_bloqueado" in MAIN
    assert "q.status in communications.retryable_statuses" in ADMIN
    assert "No reintentar" in ADMIN


def test_rc2_operational_cancelled_state_and_expiry():
    assert 'cancelled_operational' in MAIN
    assert 'row.status = "expired"' in MAIN
    assert "cancel_notification_row" in MAIN
    assert "obsoleto" in ADMIN


def test_rc2_emails_have_actor_timestamp_and_guest_summary():
    assert "Registrado por: {{actor}}" in MAIN
    assert "Momento de registro: {{momento_operativo}}" in MAIN
    assert "guest_reservation_summary_for_email" in MAIN
    assert "Resumen operativo actual de tus invitados asociados" in MAIN
