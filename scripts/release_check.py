#!/usr/bin/env python3
from __future__ import annotations

import compileall
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRITICAL_TESTS = [
    'tests/test_smoke_static.py',
    'tests/test_phase18_blindaje_monolito.py',
    'tests/test_phase18_puntos_6_7_locks_auditoria.py',
    'tests/test_phase18_puntos_9_10_tests_release.py',
]
CRITICAL_TEMPLATES = ['login.html', 'admin.html', 'captain.html', 'socio.html', 'closing_sheet.html']
CRITICAL_STATIC = ['style.css', 'app.js']


def result(name: str, ok: bool, detail: str):
    return {'name': name, 'ok': bool(ok), 'detail': detail}


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8', errors='ignore')


def check_versions():
    version = read(ROOT / 'VERSION.txt').strip()
    meta = json.loads(read(ROOT / 'software_metadata.json'))
    main = read(ROOT / 'main.py')
    out = []
    out.append(result('Versión en main.py', all([
        f'APP_VERSION = "{version}"' in main,
        f'APP_BUILD = "Fjord VI {version}"' in main,
        f'RELEASE_LABEL = "Fjord VI · v{version}"' in main,
    ]), version))
    out.append(result('software_metadata.json alineado', meta.get('version') == version and meta.get('release_label') == f'Fjord VI · v{version}' and meta.get('app_build') == f'Fjord VI {version}', meta.get('version','?')))
    out.append(result('README alineado', version in read(ROOT / 'README.md'), f'versión {version}'))
    out.append(result('render.yaml presente', (ROOT / 'render.yaml').exists(), 'OK'))
    out.append(result('DATABASE_URL previsto para producción', 'DATABASE_URL' in main, 'main.py valida/configura DATABASE_URL' if 'DATABASE_URL' in main else 'falta manejo de DATABASE_URL'))
    return out


def check_files():
    out=[]
    missing_tpl=[n for n in CRITICAL_TEMPLATES if not (ROOT/'templates'/n).exists()]
    missing_static=[n for n in CRITICAL_STATIC if not (ROOT/'static'/n).exists()]
    out.append(result('Templates críticos', not missing_tpl, 'OK' if not missing_tpl else ', '.join(missing_tpl)))
    out.append(result('Static críticos', not missing_static, 'OK' if not missing_static else ', '.join(missing_static)))
    out.append(result('requirements.txt presente', (ROOT/'requirements.txt').exists(), 'OK'))
    out.append(result('Procfile/start.sh presentes', (ROOT/'Procfile').exists() and (ROOT/'start.sh').exists(), 'OK'))
    out.append(result('Tests scaffold', (ROOT/'tests').exists(), 'pytest/smoke preparado'))
    out.append(result('Tests críticos de negocio', (ROOT/'tests'/'test_phase18_puntos_9_10_tests_release.py').exists(), 'mínimos de reservas/cierre/reapertura/roles/release'))
    out.append(result('Script externo de release', (ROOT/'scripts'/'release_check.py').exists(), 'python scripts/release_check.py'))
    return out


def check_cache():
    pycache = list(ROOT.rglob('__pycache__'))
    pyc = list(ROOT.rglob('*.pyc'))
    return [
        result('Sin __pycache__', not pycache, 'OK' if not pycache else str(pycache[:3])),
        result('Sin .pyc', not pyc, 'OK' if not pyc else str(pyc[:3])),
    ]


def check_compile():
    previous = getattr(sys, 'pycache_prefix', None)
    with tempfile.TemporaryDirectory(prefix='fjord_release_check_') as tmp:
        sys.pycache_prefix = tmp
        ok = compileall.compile_dir(str(ROOT), quiet=1, force=False, maxlevels=10)
    sys.pycache_prefix = previous
    return result('compileall OK', ok, 'python bytecode compilable' if ok else 'falló compileall')


def check_pytest():
    cmd = [sys.executable, '-m', 'pytest', '-q', *CRITICAL_TESTS]
    env = dict(os.environ)
    with tempfile.TemporaryDirectory(prefix='fjord_pytest_cache_') as tmp:
        env['PYTHONPATH'] = str(ROOT)
        env['PYTHONPYCACHEPREFIX'] = tmp
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=env)
    tail = (proc.stdout + '\n' + proc.stderr).strip()
    if len(tail) > 1200:
        tail = tail[-1200:]
    return result('Tests mínimos de negocio/release', proc.returncode == 0, tail or 'sin salida')


def run():
    rows=[]
    rows.extend(check_versions())
    rows.extend(check_files())
    rows.extend(check_cache())
    rows.append(check_compile())
    rows.append(check_pytest())
    ok = all(r['ok'] for r in rows)
    print('Fjord VI · release check automático')
    print(f'Root: {ROOT}')
    for r in rows:
        print(f"[{'OK' if r['ok'] else 'ERROR'}] {r['name']}: {r['detail']}")
    print(f"Resultado final: {'APTO' if ok else 'NO APTO'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(run())
