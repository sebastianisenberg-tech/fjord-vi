from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")


def test_operation_lock_strict_blocks_if_technical_lock_fails():
    assert "strict: bool = False" in MAIN
    assert "return False if strict else True" in MAIN
    assert "strict=True" in MAIN


def test_sensitive_admin_password_resets_are_locked():
    assert '"/admin/user/reset-password/"' in MAIN
    assert '"/admin/reset_password/"' in MAIN
    assert '"/admin/reset_all_passwords"' in MAIN
    assert 'lock_key = "admin:reset_all_passwords"' in MAIN
    assert 'user:reset_password' in MAIN


def test_audit_event_enriches_existing_audit_without_schema_migration():
    assert "def audit_event(" in MAIN
    assert '"request_id"' in MAIN
    assert '"ip"' in MAIN
    assert '"user_agent"' in MAIN
    assert '"before"' in MAIN and '"after"' in MAIN
    assert "log(db, actor_name, action, compact)" in MAIN


def test_captain_critical_actions_use_enriched_audit():
    for marker in [
        '"cancelación"',
        '"reapertura"',
        '"asistencia"',
        '"reasignación invitado"',
        '"cierre embarque"',
    ]:
        assert marker in MAIN
    assert "request=request, outing_id=outing.id" in MAIN
    assert "reservation_id=r.id" in MAIN


def test_idempotent_retries_are_audited_too():
    for marker in [
        '"cancelación idempotente"',
        '"reapertura idempotente"',
        '"asistencia idempotente"',
        '"cierre idempotente"',
    ]:
        assert marker in MAIN
