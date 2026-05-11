from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
TPL = (ROOT / "templates" / "captain.html").read_text(encoding="utf-8")


def test_waitlist_can_be_reactivated_by_captain_when_slot_exists():
    assert "def captain_can_activate_waitlisted_reservation" in MAIN
    assert "def captain_activate_waitlisted_reservation" in MAIN
    assert "Promovido manualmente desde lista de espera por capitán" in MAIN
    assert 'if value not in ("Por confirmar", "Presente")' in MAIN


def test_reassign_no_longer_blocks_waitlist_rows_and_can_revive_them():
    assert 'was_waitlisted = is_waitlisted(r)' in MAIN
    assert 'captain_activate_waitlisted_reservation(db, outing, r)' in MAIN
    assert 'reactivado desde espera' in MAIN


def test_promote_waitlist_requires_responsible_still_operational_after_reopen():
    assert 'responsible_row.attendance not in ("Presente", "Por confirmar")' in MAIN
    assert 'solo se promueven invitados cuyo socio responsable' in MAIN


def test_captain_template_exposes_waitlist_actions_after_reopen():
    assert "captain_can_activate_from_waitlist" in MAIN
    assert "Subir desde espera / dejar pendiente" in TPL
    assert "or r.attendance == 'No embarca'" in TPL
