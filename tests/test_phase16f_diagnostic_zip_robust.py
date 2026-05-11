from pathlib import Path

def test_version_1155_unified():
    main = Path("main.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "1.16.11"' in main
    assert 'APP_BUILD = "Fjord VI 1.16.11"' in main

def test_diagnostic_zip_robust():
    main = Path("main.py").read_text(encoding="utf-8")
    assert 'def admin_diagnostic_zip' in main
    assert '09_ERRORES.txt' in main
    assert 'ERROR_ZIP_VACIO.txt' in main
    assert 'filename=fjord_vi_diagnostico_{APP_VERSION}.zip' in main
    assert 'try:\n        log_activity' in main
