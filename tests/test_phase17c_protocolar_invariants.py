from pathlib import Path

def test_version_1162_unified():
    main = Path("main.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "1.16.5"' in main
    assert 'APP_BUILD = "Fjord VI 1.16.5"' in main

def test_protocolar_charge_invariants():
    main = Path("main.py").read_text(encoding="utf-8")
    assert "if is_protocolar(r):\n        return 0.0" in main
    assert "Protocolar no depende del socio que lo cargó" in main
    assert "Protocolar no embarcado · Sin cargo" in main
    assert "Protocolar no confirmado al cierre · Sin cargo" in main

def test_protocolar_not_blocked_by_responsible_absent():
    main = Path("main.py").read_text(encoding="utf-8")
    assert 'canonical_kind(r.kind) in ("invitado", "hijo_menor") and not is_protocolar(r)' in main
    assert "if is_protocolar(r):\n            continue" in main

def test_captain_protocolar_visual_independent():
    html = Path("templates/captain.html").read_text(encoding="utf-8")
    assert "independiente del socio que lo cargó · sin cargo" in html
    assert "not reservation_views.get(r.id).protocolar and captain_responsible_options" in html
