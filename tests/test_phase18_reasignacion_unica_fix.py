from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_reassign_endpoint_checks_single_reassignment_before_success():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    unique_guard = 'if reassignment_trace_only(r.cancel_reason or ""):'
    success_return = 'return RedirectResponse(f"/captain?outing_id={outing.id}&msg=reasignacion_ok", status_code=303)'
    assert unique_guard in main
    assert success_return in main
    assert main.index(unique_guard) < main.index(success_return)
    assert 'if r.attendance == "Presente" and reservation_is_active(r):\n        return RedirectResponse(f"/captain?outing_id={outing.id}&msg=reasignacion_ok", status_code=303)' not in main


def test_captain_template_hides_reassign_controls_after_first_reassignment():
    html = (ROOT / 'templates' / 'captain.html').read_text(encoding='utf-8')
    assert '{% if v.show_responsible and not v.reassignment_locked and captain_responsible_options|length > 0 %}' in html


def test_captain_context_exposes_reassignment_locked_flag():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert 'v["reassignment_locked"] = bool(reassignment_trace_only(r.cancel_reason or ""))' in main
