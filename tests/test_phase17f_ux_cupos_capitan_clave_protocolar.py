from pathlib import Path

def test_version_1165():
    main = Path("main.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "1.16.11"' in main

def test_socio_capacity_words():
    html = Path("templates/socio.html").read_text(encoding="utf-8")
    assert "Ocupación total" in html
    assert "Cupos libres" in html
    assert "Plazas disponibles" not in html

def test_socio_password_compact():
    html = Path("templates/socio.html").read_text(encoding="utf-8")
    assert "socioKeyPillV1165" in html
    assert "Clave" in html
    assert "accountPasswordLink" not in html

def test_captain_invited_of():
    html = Path("templates/captain.html").read_text(encoding="utf-8")
    assert "Invitado de" in html
    assert "captainResponsibleTraceV1165" in html

def test_protocolar_clean_sheet():
    html = Path("templates/closing_sheet.html").read_text(encoding="utf-8")
    assert "Participación protocolar · Sin cargo" not in html
