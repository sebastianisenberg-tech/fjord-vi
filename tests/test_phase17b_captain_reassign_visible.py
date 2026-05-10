from pathlib import Path

def test_version_1161_unified():
    main = Path("main.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "1.16.3"' in main
    assert 'APP_BUILD = "Fjord VI 1.16.3"' in main

def test_captain_reassign_visible():
    html = Path("templates/captain.html").read_text(encoding="utf-8")
    assert "captainInlineReassignV1161" in html
    assert "Reasignar invitado" in html
    assert "/captain/reassign/{{r.id}}" in html
    assert "captain_responsible_options" in html

def test_captain_reassign_backend_still_present():
    main = Path("main.py").read_text(encoding="utf-8")
    assert '@app.post("/captain/reassign/{rid}")' in main
    assert "def captain_reassign_guest" in main
