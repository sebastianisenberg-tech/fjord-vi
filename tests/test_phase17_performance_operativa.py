from pathlib import Path

def test_version_1160_unified():
    main = Path("main.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "1.16.5"' in main
    assert 'APP_BUILD = "Fjord VI 1.16.5"' in main

def test_performance_policy_endpoint_exists():
    main = Path("main.py").read_text(encoding="utf-8")
    assert "/admin/performance_policy.json" in main
    assert "operational_performance_middleware" in main

def test_anti_double_touch_js_exists():
    js = Path("static/app.js").read_text(encoding="utf-8")
    assert "anti doble toque" in js.lower() or "anti doble" in js.lower()
    assert "fjordOperationalGuardInstalled" in js
    assert "SUBMIT_LOCK_MS" in js

def test_performance_doc_exists():
    assert Path("docs/PERFORMANCE_OPERATIVA_1_16_0.md").exists()
