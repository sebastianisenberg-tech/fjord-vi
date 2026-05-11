from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
SCRIPT = (ROOT / "scripts" / "release_check.py").read_text(encoding="utf-8")


def test_release_check_rows_include_business_tests_and_external_script():
    assert 'Tests críticos de negocio' in MAIN
    assert 'Script externo de release' in MAIN
    assert 'python scripts/release_check.py' in MAIN


def test_captain_diagnostic_covers_minimum_business_rules():
    for marker in [
        'Socio ausente con cargo arrastra invitados comunes',
        'No embarca/sin cargo por Capitán arrastra invitados sin cargo',
        'Institucional fuera de cascada económica',
        'Reasignado pasa al nuevo responsable',
        'La ficha debe tener una única versión vigente por cierre',
    ]:
        assert marker in MAIN


def test_release_script_checks_expected_items():
    for marker in [
        'compileall.compile_dir',
        'tests/test_smoke_static.py',
        'tests/test_phase18_blindaje_monolito.py',
        'tests/test_phase18_puntos_6_7_locks_auditoria.py',
        'tests/test_phase18_puntos_9_10_tests_release.py',
        'tests/test_phase18_reapertura_reasignacion_fix.py',
        'software_metadata.json',
        'README.md',
        'render.yaml',
        '__pycache__',
        '*.pyc',
        'DATABASE_URL',
    ]:
        assert marker in SCRIPT


def test_release_script_exists_and_is_documented():
    assert (ROOT / 'scripts' / 'release_check.py').exists()
    checklist = (ROOT / 'RELEASE_CHECKLIST.md').read_text(encoding='utf-8')
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')
    assert 'python scripts/release_check.py' in checklist
    assert 'python scripts/release_check.py' in readme
