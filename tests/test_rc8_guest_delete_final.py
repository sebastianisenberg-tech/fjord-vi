from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_socio_guest_menu_is_simple_and_individual():
    html = (ROOT / "templates" / "socio.html").read_text(encoding="utf-8")
    assert "/socio/cancel_guest/{{r.id}}" in html
    assert "Eliminar invitado" in html
    assert "Editar datos" in html
    assert "Cerrar" in html
    # El menú del socio no debe ofrecer acciones operativas de capitán/admin.
    assert "Registrar reserva incumplida" not in html
    assert "Marcar institucional" not in html
    assert "Quitar institucional" not in html

def test_individual_guest_route_does_not_cascade_dependents():
    code = (ROOT / "main.py").read_text(encoding="utf-8")
    start = code.index('@app.post("/socio/cancel_guest/{rid}")')
    end = code.index('@app.post("/socio/cancel/{rid}")')
    route = code[start:end]
    assert "can_user_manage_guest_record" in route
    assert "baja individual de invitado" in route
    assert "responsible_user_id == user.id" not in route
    assert "dependientes" not in route
    assert "dni != user.dni" not in route

def test_guest_menus_close_like_single_dropdown():
    html = (ROOT / "templates" / "socio.html").read_text(encoding="utf-8")
    assert "details.guestMenuV123[open]" in html
    assert "other !== d" in html
    assert "other.open = false" in html
