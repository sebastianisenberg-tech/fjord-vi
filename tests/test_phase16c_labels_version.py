from pathlib import Path

def test_version_unified_1152():
    main = Path("main.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "1.16.4"' in main
    assert 'APP_BUILD = "Fjord VI 1.16.4"' in main
    assert 'RELEASE_LABEL = "Fjord VI · v1.16.4"' in main

def test_system_technical_button_labels():
    html = Path("templates/admin.html").read_text(encoding="utf-8")
    assert "Health técnico JSON" in html
    assert "Release check TXT" in html
    assert "Descargar diagnóstico ZIP" in html
    assert "no es una pantalla visual" in html
