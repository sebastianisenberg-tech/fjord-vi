from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
SOCIO = (ROOT / "templates" / "socio.html").read_text(encoding="utf-8")


def test_rc8_socio_actions_are_semantically_split():
    assert '@app.post("/socio/delete_guest/{rid}")' in MAIN
    assert '@app.post("/socio/cancel_self/{rid}")' in MAIN
    assert '@app.post("/socio/leave_waitlist/{rid}")' in MAIN
    assert 'def _promote_after_socio_capacity_release' in MAIN


def test_rc8_delete_guest_does_not_call_general_recompute_dependency():
    block = MAIN.split('@app.post("/socio/delete_guest/{rid}")', 1)[1].split('@app.post("/socio/leave_waitlist/{rid}")', 1)[0]
    assert 'can_user_manage_guest_record' in block
    assert 'recompute_waitlist_for_salida' not in block
    assert '_promote_after_socio_capacity_release' in block
    assert 'dependientes' not in block


def test_rc8_cancel_self_is_the_only_socio_action_that_cascades_dependents():
    cancel_self = MAIN.split('@app.post("/socio/cancel_self/{rid}")', 1)[1].split('@app.post("/socio/cancel/{rid}")', 1)[0]
    delete_guest = MAIN.split('@app.post("/socio/delete_guest/{rid}")', 1)[1].split('@app.post("/socio/leave_waitlist/{rid}")', 1)[0]
    assert 'dependientes = db.query(Reservation)' in cancel_self
    assert 'dependientes = db.query(Reservation)' not in delete_guest


def test_rc8_template_uses_explicit_socio_endpoints():
    assert '/socio/delete_guest/{{r.id}}' in SOCIO
    assert '/socio/cancel_self/{{self_reservation.id}}' in SOCIO
    assert '/socio/leave_waitlist/{{self_reservation.id}}' in SOCIO
    assert 'Registrar reserva incumplida' not in SOCIO
