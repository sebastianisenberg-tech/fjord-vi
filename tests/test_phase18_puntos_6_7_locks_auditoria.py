from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / 'main.py').read_text(encoding='utf-8', errors='ignore')


def test_lock_and_audit_hooks_present():
    assert 'lock' in MAIN.lower()
    assert 'audit' in MAIN.lower()
