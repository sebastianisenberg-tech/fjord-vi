from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_templates_and_static_exist():
    assert (ROOT / 'templates' / 'admin.html').exists()
    assert (ROOT / 'templates' / 'captain.html').exists()
    assert (ROOT / 'templates' / 'socio.html').exists()
    assert (ROOT / 'static' / 'style.css').exists()
    assert (ROOT / 'static' / 'app.js').exists()
