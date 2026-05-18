from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")


def test_version_rc8_unified():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "3.9.0-OPERATIONAL-RC1"
    assert 'APP_VERSION = "3.9.0-OPERATIONAL-RC1"' in MAIN
    assert 'APP_BUILD = APP_VERSION' in MAIN
    assert 'RELEASE_LABEL = APP_VERSION' in MAIN


def test_waitlist_single_recompute_entrypoint_exists():
    assert "def recompute_waitlist_for_salida" in MAIN
    assert "enforce_responsible_dependency" in MAIN
    assert "enforce_capacity" in MAIN
    assert "promote_waitlist" in MAIN
    assert "validate_outing_operational_invariants" in MAIN


def test_release_check_exposes_hardening_controls():
    assert "Política operativa de envíos" in MAIN
    assert "Retry SMTP limitado" in MAIN
    assert "Expiración de pendientes SMTP" in MAIN
    assert "Tests críticos de negocio" in MAIN
