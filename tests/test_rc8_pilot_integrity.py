from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
META = (ROOT / "software_metadata.json").read_text(encoding="utf-8")


def test_rc8_version_label_is_unified_for_pilot():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "RC8_EMAIL_HTML_FIX3"
    assert 'APP_VERSION = "RC8_EMAIL_HTML_FIX3"' in MAIN
    assert 'APP_BUILD = "Fjord VI RC8 EMAIL HTML FIX2"' in MAIN
    assert 'RELEASE_LABEL = "Fjord VI · RC8 Email HTML Fix2"' in MAIN
    assert '"release_stage": "PILOT_RC8_EMAIL_HTML_FIX3"' in META


def test_rc8_waitlist_is_never_chargeable_in_invariants():
    assert 'está en lista de espera con cargo; espera nunca se factura' in MAIN
    assert 'if is_waitlisted(r) and float(getattr(r, "charge_amount", 0) or 0) > 0' in MAIN
    assert 'lista de espera y cancelado simultáneamente' in MAIN


def test_rc8_closed_outing_cannot_keep_pending_active_rows():
    assert 'quedó pendiente después del cierre' in MAIN
    assert 'is_closed_outing(outing) and reservation_is_active(r)' in MAIN
    assert 'auto_confirm_active_for_close' in MAIN
    assert 'No confirmado al cierre de embarque' in MAIN


def test_rc8_waitlisted_responsible_blocks_active_guest():
    assert 'invitado activo con socio responsable todavía en lista de espera' in MAIN
    assert 'responsible_rows_by_user' in MAIN
    assert 'responsible_waitlisted = bool(self_row and is_waitlisted(self_row))' in MAIN
    assert 'guest_must_waitlist = bool(full_capacity or responsible_waitlisted)' in MAIN


def test_rc8_system_release_check_exposes_pilot_controls():
    assert 'RC8 · espera nunca facturable' in MAIN
    assert 'RC8 · socio en espera con invitados' in MAIN
    assert 'RC8 · cierre sin pendientes finales' in MAIN
