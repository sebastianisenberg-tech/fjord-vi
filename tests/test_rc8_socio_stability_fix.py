from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
SOCIO = (ROOT / "templates" / "socio.html").read_text(encoding="utf-8")
APPJS = (ROOT / "static" / "app.js").read_text(encoding="utf-8")


def test_guest_cancel_cannot_cascade_group():
    assert 'selected_kind = canonical_kind(r.kind)' in MAIN
    assert 'selected_kind == "socio" and r.dni == user.dni' in MAIN
    assert 'jamás\n    # debe cancelar el grupo ni borrar otros invitados' in MAIN


def test_socio_forms_use_native_redirect_not_ajax_fetch():
    assert "document.body.classList.contains('socioApp')" in APPJS
    assert 'POST nativo + redirect server-side' in APPJS


def test_socio_guest_menu_is_strict():
    block_start = SOCIO.index('{% elif v.waitlisted or v.active %}')
    block_end = SOCIO.index('{% else %}', block_start)
    block = SOCIO[block_start:block_end]
    assert 'Editar datos' in block
    assert 'Eliminar invitado' in block
    assert 'Cerrar' in block
    assert 'Marcar institucional' not in block
    assert 'Quitar institucional' not in block
    assert 'Reincorporar' not in block
    assert 'Registrar reserva incumplida' not in block


def test_socio_submit_unlocks_after_error_or_bfcache():
    assert "setTimeout(function(){buttons.forEach" in SOCIO
    assert "window.addEventListener('pageshow'" in SOCIO
    assert 'closeGuestMenu' in SOCIO
