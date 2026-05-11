from pathlib import Path

def test_version_1153_unified():
    main = Path("main.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "1.16.11"' in main
    assert 'APP_BUILD = "Fjord VI 1.16.11"' in main
    assert 'RELEASE_LABEL = "Fjord VI · v1.16.11"' in main

def test_diagnostic_zip_endpoint_exists():
    main = Path("main.py").read_text(encoding="utf-8")
    assert "/admin/diagnostic.zip" in main
    assert "zipfile.ZipFile" in main
    assert "06_actividad_reciente.csv" in main
    assert "07_auditoria_reciente.csv" in main

def test_system_checks_feedback_exists():
    html = Path("templates/admin.html").read_text(encoding="utf-8")
    assert "Cargando checks..." in html
    assert "Checks completos cargados" in html
    assert "/admin/diagnostic.zip" in html
    assert "Al tocar “Cargar checks completos”" in html
