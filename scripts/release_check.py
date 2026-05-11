#!/usr/bin/env python3
from __future__ import annotations

import compileall
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRITICAL_TEMPLATES = [
    "login.html",
    "socio.html",
    "admin.html",
    "captain.html",
    "change_password.html",
    "session_required.html",
]
CRITICAL_STATIC = ["style.css", "app.js"]
CRITICAL_TESTS = [
    "tests/test_smoke_static.py",
    "tests/test_phase18_blindaje_monolito.py",
    "tests/test_phase18_puntos_6_7_locks_auditoria.py",
    "tests/test_phase18_puntos_9_10_tests_release.py",
]
SKIP_DIRS = {".git", ".pytest_cache", "venv", ".venv", "node_modules"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _result(name: str, ok: bool, detail: str) -> dict:
    return {"name": name, "ok": bool(ok), "detail": detail}


def version_consistency_checks() -> list[dict]:
    rows: list[dict] = []
    version = _read(ROOT / "VERSION.txt").strip()
    main = _read(ROOT / "main.py")
    readme = _read(ROOT / "README.md")
    render_yaml = _read(ROOT / "render.yaml")
    metadata = json.loads(_read(ROOT / "software_metadata.json"))

    main_version = f'APP_VERSION = "{version}"' in main
    app_build = f'APP_BUILD = "Fjord VI {version}"' in main
    release_label = f'RELEASE_LABEL = "Fjord VI · v{version}"' in main
    rows.append(_result("Versión en main.py", main_version and app_build and release_label, version))

    md_ok = (
        metadata.get("version") == version
        and metadata.get("release_label") == f"Fjord VI · v{version}"
        and metadata.get("app_build") == f"Fjord VI {version}"
    )
    rows.append(_result("software_metadata.json alineado", md_ok, metadata.get("version", "sin version")))

    readme_ok = f"Fjord VI {version}" in readme and version in readme
    rows.append(_result("README alineado", readme_ok, f"versión {version}"))

    render_ok = "render.yaml" in str(ROOT / "render.yaml") and "APP_ENV" in render_yaml
    rows.append(_result("render.yaml presente", render_ok, "APP_ENV configurado" if render_ok else "revisar render.yaml"))

    dburl_ok = "DATABASE_URL" in main
    rows.append(_result("DATABASE_URL previsto para producción", dburl_ok, "main.py valida/configura DATABASE_URL" if dburl_ok else "falta manejo de DATABASE_URL"))
    return rows


def file_checks() -> list[dict]:
    rows: list[dict] = []
    missing_tpl = [name for name in CRITICAL_TEMPLATES if not (ROOT / "templates" / name).exists()]
    missing_static = [name for name in CRITICAL_STATIC if not (ROOT / "static" / name).exists()]
    rows.append(_result("Templates críticos", not missing_tpl, "OK" if not missing_tpl else ", ".join(missing_tpl)))
    rows.append(_result("Static críticos", not missing_static, "OK" if not missing_static else ", ".join(missing_static)))
    rows.append(_result("requirements.txt presente", (ROOT / "requirements.txt").exists(), "OK"))
    rows.append(_result("Procfile/start.sh presentes", (ROOT / "Procfile").exists() and (ROOT / "start.sh").exists(), "OK"))
    return rows


def cache_checks() -> list[dict]:
    rows: list[dict] = []
    pycache = [p for p in ROOT.rglob("__pycache__") if not any(part in SKIP_DIRS for part in p.parts)]
    pyc = [p for p in ROOT.rglob("*.pyc") if not any(part in SKIP_DIRS for part in p.parts)]
    rows.append(_result("Sin __pycache__", not pycache, "OK" if not pycache else str(pycache[:5])))
    rows.append(_result("Sin .pyc", not pyc, "OK" if not pyc else str(pyc[:5])))
    return rows


def compile_check() -> dict:
    previous_prefix = getattr(sys, "pycache_prefix", None)
    with tempfile.TemporaryDirectory(prefix="fjord_release_check_") as tmp:
        sys.pycache_prefix = tmp
        ok = compileall.compile_dir(
            str(ROOT),
            force=False,
            quiet=1,
            maxlevels=10,
            rx=re.compile(r"/(?:\.git|\.pytest_cache|__pycache__|venv|\.venv|node_modules)/"),
        )
    sys.pycache_prefix = previous_prefix
    return _result("compileall OK", ok, "python bytecode compilable" if ok else "falló compileall")


def pytest_check() -> dict:
    cmd = [sys.executable, "-m", "pytest", "-q", *CRITICAL_TESTS]
    env = dict(**__import__("os").environ)
    with tempfile.TemporaryDirectory(prefix="fjord_pytest_cache_") as tmp:
        env["PYTHONPYCACHEPREFIX"] = tmp
        env["PYTHONPATH"] = str(ROOT)
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=env)
    tail = (proc.stdout + "\n" + proc.stderr).strip()
    if len(tail) > 1200:
        tail = tail[-1200:]
    return _result("Tests mínimos de negocio/release", proc.returncode == 0, tail or "sin salida")


def run() -> int:
    rows: list[dict] = []
    rows.extend(version_consistency_checks())
    rows.extend(file_checks())
    rows.extend(cache_checks())
    rows.append(compile_check())
    rows.append(pytest_check())

    ok = all(r["ok"] for r in rows)
    print("Fjord VI · release check automático")
    print(f"Root: {ROOT}")
    for row in rows:
        mark = "OK" if row["ok"] else "ERROR"
        print(f"[{mark}] {row['name']}: {row['detail']}")
    print(f"Resultado final: {'APTO' if ok else 'NO APTO'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(run())
