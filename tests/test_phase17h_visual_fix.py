from pathlib import Path

def test_version_unified():
    assert Path("VERSION.txt").read_text().strip() == "1.16.9"
    main = Path("main.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "1.16.9"' in main

def test_header_key_hidden_css():
    css = Path("static/style.css").read_text(encoding="utf-8")
    assert '.topbar a[href="/account/password"]' in css
    assert "display: none !important" in css
    assert ".captainMiniKeyPillV1166" in css

def test_protocolar_text_clean():
    captain = Path("templates/captain.html").read_text(encoding="utf-8")
    assert "Invitación institucional" in captain
    assert "Sin cargo permanente" not in captain

def test_empty_badges_hidden():
    css = Path("static/style.css").read_text(encoding="utf-8")
    assert ".badgeTipo:empty" in css
