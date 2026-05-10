from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_phase13_docs_present():
    assert (ROOT / "docs" / "FASE_13_SEGURIDAD_TESTS_OBSERVABILIDAD.md").exists()
    assert (ROOT / "docs" / "TEST_PLAN.md").exists()


def test_security_observability_modules_present():
    assert (ROOT / "app" / "core" / "observability.py").exists()
    assert (ROOT / "app" / "core" / "validators.py").exists()


def test_version_unified_text_files():
    assert (ROOT / "VERSION.txt").read_text().strip() == "1.16.1"
    main = (ROOT / "main.py").read_text()
    assert 'APP_VERSION = "1.16.1"' in main
    assert 'APP_BUILD = "Fjord VI 1.16.1"' in main
    assert 'RELEASE_LABEL = "Fjord VI · v1.16.1"' in main


def test_admin_security_endpoints_declared():
    main = (ROOT / "main.py").read_text()
    assert '/admin/security_status.json' in main
    assert '/admin/observability.json' in main
