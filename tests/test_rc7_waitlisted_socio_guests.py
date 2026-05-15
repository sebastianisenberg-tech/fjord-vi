from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
SOCIO = (ROOT / "templates" / "socio.html").read_text(encoding="utf-8")


def test_rc7_waitlisted_socio_can_add_guests_to_waitlist():
    assert "can_add_guest = bool(self_reservation and (reservation_is_active(self_reservation) or is_waitlisted(self_reservation)))" in MAIN
    assert "responsible_waitlisted = bool(self_row and is_waitlisted(self_row))" in MAIN
    assert "guest_must_waitlist = bool(full_capacity or responsible_waitlisted)" in MAIN
    assert "En lista de espera asociada al socio titular" in MAIN


def test_rc7_socio_template_allows_invite_when_self_waitlisted():
    assert "not can_add_guest" in SOCIO
    assert "not closed and can_add_guest" in SOCIO
    assert "Tu reserva titular está en espera" in SOCIO
    assert "Agregar a lista de espera" in SOCIO
