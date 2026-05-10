from pathlib import Path

def test_version_1164():
    main = Path("main.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "1.16.9"' in main

def test_captain_guest_responsible_visible():
    html = Path("templates/captain.html").read_text(encoding="utf-8")
    assert "captainResponsibleTraceV1164" in html
    assert "Invitado de" in html
    assert "socio presente" in html
    assert "socio no presente / revisar reasignación" in html

def test_responsible_fields_in_backend_context():
    main = Path("main.py").read_text(encoding="utf-8")
    assert 'v["responsible_member_no"]' in main
    assert 'v["responsible_is_present"]' in main
