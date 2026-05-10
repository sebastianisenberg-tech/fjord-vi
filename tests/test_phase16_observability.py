from pathlib import Path

def test_health_routes_present():
    content = Path("main.py").read_text(encoding="utf-8")
    assert "/health/live" in content
    assert "/health/ready" in content

def test_version_115_present():
    content = Path("main.py").read_text(encoding="utf-8")
    assert '1.16.5' in content
