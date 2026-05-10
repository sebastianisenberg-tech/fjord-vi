from pathlib import Path

def test_version_1167():
    main = Path("main.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "1.16.9"' in main

def test_captain_operational_metrics():
    html = Path("templates/captain.html").read_text(encoding="utf-8")
    assert "Ocupación" in html
    assert "Reservas procesadas" in html
    assert "A bordo" in html

def test_protocolar_single_badge_captain():
    html = Path("templates/captain.html").read_text(encoding="utf-8")
    assert "protoOnlyV1167" in html
    assert "{% else %}<span class=\"badgeTipo" in html

def test_closing_summary_clarity():
    html = Path("templates/closing_sheet.html").read_text(encoding="utf-8")
    assert "Ausentes con cargo" in html
    assert "Reservas procesadas" in html
    assert "sheetGroupCardV1167" in html
