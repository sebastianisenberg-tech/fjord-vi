from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_required_files_exist():
    required = [
        "main.py",
        "requirements.txt",
        "Dockerfile",
        "VERSION.txt",
        "software_metadata.json",
        "templates/login.html",
        "templates/admin.html",
        "templates/socio.html",
        "templates/captain.html",
        "static/style.css",
        "static/app.js",
        "app/__init__.py",
    ]
    missing = [name for name in required if not (ROOT / name).exists()]
    assert not missing, f"Missing required files: {missing}"


def test_version_unified():
    version = (ROOT / "VERSION.txt").read_text().strip()
    main = (ROOT / "main.py").read_text()
    assert f'APP_VERSION = "{version}"' in main
    assert f'Fjord VI {version}' in main


def test_no_python_cache_expected_in_release():
    forbidden = list(ROOT.rglob("__pycache__")) + list(ROOT.rglob("*.pyc"))
    assert not forbidden, f"Python cache files should not be shipped: {forbidden[:5]}"
