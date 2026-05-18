from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")


def test_smtp_policy_is_explicit():
    assert "def notification_event_policy" in MAIN
    assert '"invitado_en_espera_socio": {"timing": "diferido"' in MAIN
    assert '"embarque_estado_socio": {"timing": "diferido", "replaceable": True' in MAIN
    assert '"cierre_liquidacion_admin": {"timing": "diferido", "replaceable": False, "final": True' in MAIN
    assert '"resumen_cierre_socio": {"timing": "diferido", "replaceable": True, "final": True' in MAIN


def test_smtp_queue_has_retry_and_expiry_guards():
    assert "def smtp_retry_max_attempts" in MAIN
    assert "def smtp_pending_expiry_hours" in MAIN
    assert "def expire_stale_notification_queue" in MAIN
    assert "def cancel_over_retry_limit" in MAIN
    assert "recover_notification_queue_after_restart" in MAIN
    assert "NotificationQueue.attempts < max_attempts" in MAIN
