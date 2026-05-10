from pathlib import Path

def test_version_1154_unified():
    main = Path("main.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "1.16.0"' in main
    assert 'APP_BUILD = "Fjord VI 1.16.0"' in main

def test_robust_txt_downloads_present():
    main = Path("main.py").read_text(encoding="utf-8")
    assert 'def admin_operational_status_txt' in main
    assert 'def admin_phase9_txt' in main
    assert 'def admin_architecture_txt' in main
    assert 'ERROR PARCIAL' in main
    assert 'try:\n        log_activity' in main

def test_template_download_labels():
    html = Path("templates/admin.html").read_text(encoding="utf-8")
    assert 'Descargar estado operativo TXT' in html
    assert 'Descargar operación humana TXT' in html
    assert 'Descargar mapa técnico TXT' in html
