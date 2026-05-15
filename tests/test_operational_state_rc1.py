from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
STATE = (ROOT / "app" / "reliability" / "operational_state.py").read_text(encoding="utf-8")


def test_operational_state_module_is_authority_for_real_states():
    assert "OUTING_OPEN_STATES" in STATE
    assert "RESERVATION_ACTIVE_STATUSES" in STATE
    assert "ALLOWED_OUTING_TRANSITIONS" in STATE
    assert "ALLOWED_RESERVATION_TRANSITIONS" in STATE


def test_main_uses_guarded_state_setters_on_critical_paths():
    assert "from app.reliability import operational_state as op_state" in MAIN
    assert "def set_reservation_status_guarded" in MAIN
    assert "def set_outing_status_guarded" in MAIN
    assert 'set_reservation_status_guarded(r, "Lista de espera")' in MAIN
    assert "set_reservation_status_guarded(chosen, default_reservation_status(outing, chosen))" in MAIN
    assert 'set_outing_status_guarded(outing, "Embarque cerrado")' in MAIN
    assert 'set_outing_status_guarded(outing, "En reservas")' in MAIN


def test_close_has_precommit_invariant_guard_before_sheet():
    sheet_pos = MAIN.index("sheet = create_closing_sheet(db, outing, reservations, user.name)")
    guard_pos = MAIN.index('assert_operational_invariants_or_raise(db, outing, reservations, context="cierre final")')
    assert guard_pos < sheet_pos
