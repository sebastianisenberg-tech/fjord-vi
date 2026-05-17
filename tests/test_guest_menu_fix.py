from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
SOCIO = (ROOT / "templates/socio.html").read_text(encoding="utf-8")

def test_guest_delete_uses_individual_route_not_general_cancel():
    assert '@app.post("/socio/remove_guest/{rid}")' in MAIN
    assert 'def remove_guest_individual' in MAIN
    assert 'Invitado eliminado por socio' in MAIN
    assert 'r.dni == user.dni' in MAIN
    assert 'action="/socio/remove_guest/{{r.id}}"' in SOCIO
    assert 'Eliminar solo este invitado' in SOCIO
    assert 'guestMenuCloseV1' in SOCIO

def test_guest_menu_closes_other_menus_and_outside_click():
    assert 'details.guestMenuV123[open]' in SOCIO
    assert "other !== menu" in SOCIO
    assert "!ev.target.closest('details.guestMenuV123')" in SOCIO
