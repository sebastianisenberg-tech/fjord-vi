from pathlib import Path

def test_version_1163():
    main = Path("main.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "1.16.4"' in main

def test_protocolar_traceability_ui():
    html = Path("templates/captain.html").read_text(encoding="utf-8")
    assert "captainProtocolarTraceV1163" in html
    assert "Designado por:" in html
    assert "Motivo / etiqueta:" in html

def test_protocolar_cancel_reason_trace():
    main = Path("main.py").read_text(encoding="utf-8")
    assert "Protocolar designado por:" in main
