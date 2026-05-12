from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / 'main.py').read_text(encoding='utf-8', errors='ignore')


def test_release_flags_expected_paths_exist_in_code():
    assert 'Tests scaffold' in MAIN
    assert 'Tests críticos de negocio' in MAIN
    assert 'Script externo de release' in MAIN


def test_responsible_reassignment_schema_present():
    assert 'original_responsible_user_id' in MAIN
    assert 'reservation_reassignments' in MAIN
