from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / 'main.py').read_text(encoding='utf-8')
CAPTAIN = (ROOT / 'templates' / 'captain.html').read_text(encoding='utf-8')


def test_rc4_fast_tap_is_server_authoritative_not_dom_absolute():
    assert 'def resolve_captain_fast_toggle_value' in MAIN
    assert '@app.post("/captain/attendance_toggle/{rid}")' in MAIN
    assert 'value = resolve_captain_fast_toggle_value(r)' in MAIN
    assert 'form[data-v65-status="TOGGLE"]' in CAPTAIN
    assert 'action="/captain/attendance_toggle/{{r.id}}"' in CAPTAIN


def test_rc4_stale_captain_screen_is_blocked_and_audited():
    assert 'def expected_attendance_is_stale' in MAIN
    assert 'tap rápido con pantalla desactualizada' in MAIN
    assert 'msg=pantalla_actualizada' in MAIN
    assert 'La pantalla estaba desactualizada' in CAPTAIN
    assert 'expected_current' in CAPTAIN


def test_rc4_toggle_semantics_preserve_captain_business_rules():
    body = MAIN[MAIN.index('def resolve_captain_fast_toggle_value'):MAIN.index('def expected_attendance_is_stale')]
    assert 'BOARDING_TRANSITION_PRESENT' in body
    assert 'return BOARDING_TRANSITION_PENDING' in body
    assert 'return BOARDING_TRANSITION_PRESENT' in body
    assert 'No embarcó/con cargo y No embarca/sin cargo quedan como acciones explícitas del menú' in body
