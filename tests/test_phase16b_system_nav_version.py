from pathlib import Path

def test_version_unified_1151():
    content = Path("main.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "1.16.9"' in content
    assert 'APP_BUILD = "Fjord VI 1.16.9"' in content
    assert 'RELEASE_LABEL = "Fjord VI · v1.16.9"' in content

def test_system_quick_links_load_full_sections():
    content = Path("templates/admin.html").read_text(encoding="utf-8")
    assert "/admin/sistema?full=1#system-release" in content
    assert "/admin/sistema?full=1#system-operativo" in content
    assert "/admin/sistema?full=1#system-reset" in content
    assert "openHashTarget" in content
