from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8", errors="ignore")
SOCIO = (ROOT / "templates" / "socio.html").read_text(encoding="utf-8", errors="ignore")
ADMIN = (ROOT / "templates" / "admin.html").read_text(encoding="utf-8", errors="ignore")


def test_guest_edit_and_replace_routes_present():
    assert '/socio/guest/update/' in MAIN
    assert '/socio/guest/replace/' in MAIN
    assert 'can_edit_guest_data' in MAIN
    assert 'cancel_guest_reservation_with_policy' in MAIN


def test_outing_delete_route_present():
    assert '/admin/delete_outing' in MAIN
    assert 'BORRAR SALIDA' in MAIN


def test_templates_expose_actions():
    assert '/socio/guest/update/' in SOCIO
    assert '/socio/guest/replace/' in SOCIO
    assert '/admin/delete_outing' in ADMIN
