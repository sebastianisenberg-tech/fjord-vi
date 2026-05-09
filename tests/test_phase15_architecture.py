from pathlib import Path
import importlib

ROOT = Path(__file__).resolve().parents[1]


def test_phase15_modules_exist():
    required = [
        "app/core/errors.py",
        "app/core/logging_config.py",
        "app/core/settings.py",
        "app/repositories/__init__.py",
        "app/repositories/users.py",
        "app/repositories/reservations.py",
        "app/repositories/outings.py",
        "app/repositories/activity.py",
        "app/middleware/__init__.py",
        "app/services/operations.py",
        "docs/FASE_15_ARQUITECTURA_ERRORES_SERVICES.md",
    ]
    missing = [p for p in required if not (ROOT / p).exists()]
    assert not missing


def test_app_errors_are_typed():
    errors = importlib.import_module("app.core.errors")
    exc = errors.BusinessRuleAppError("Regla bloqueada", code="rule_blocked")
    assert exc.code == "rule_blocked"
    assert exc.status_code == 409
    assert "Regla bloqueada" in errors.render_app_error_html(exc, request_id="test")


def test_settings_load_without_env_crash():
    settings = importlib.import_module("app.core.settings")
    loaded = settings.load_settings("1.15.3")
    assert loaded.app_version == "1.15.3"
    assert loaded.session_max_age_seconds > 0


def test_version_unified():
    assert (ROOT / "VERSION.txt").read_text().strip() == "1.15.3"
    main_text = (ROOT / "main.py").read_text()
    assert 'APP_VERSION = "1.15.3"' in main_text
    assert 'APP_BUILD = "Fjord VI 1.15.3"' in main_text
