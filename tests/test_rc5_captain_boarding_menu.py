from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / 'main.py').read_text(encoding='utf-8')
CAPTAIN = (ROOT / 'templates' / 'captain.html').read_text(encoding='utf-8')
STYLE = (ROOT / 'static' / 'style.css').read_text(encoding='utf-8')


def test_rc5_captain_menu_has_direct_absent_with_charge_from_pending():
    assert 'attendanceAbsentMenuForm' in CAPTAIN
    assert 'action="/captain/attendance/{{r.id}}/Ausente"' in CAPTAIN
    assert 'No embarcó / con cargo' in CAPTAIN
    assert 'libera plaza' in CAPTAIN
    assert 'puede generar cargo reglamentario' in CAPTAIN


def test_rc5_fast_tap_no_longer_creates_false_absent_state():
    body = MAIN[MAIN.index('def resolve_captain_fast_toggle_value'):MAIN.index('def expected_attendance_is_stale')]
    assert 'return BOARDING_TRANSITION_ABSENT_CHARGED' not in body
    assert 'return BOARDING_TRANSITION_PENDING' in body
    assert 'return BOARDING_TRANSITION_PRESENT' in body
    assert 'No embarcó/con cargo' in body


def test_rc5_waitlist_recomputes_when_absent_or_no_board_frees_place():
    body = MAIN[MAIN.index('def apply_boarding_transition'):MAIN.index('def enforce_responsible_dependency')]
    assert 'value == BOARDING_TRANSITION_ABSENT_CHARGED' in body
    assert 'result["recalculate_waitlist"] = True' in body
    assert 'value == BOARDING_TRANSITION_NO_BOARD_FREE' in body
    assert 'recompute_waitlist_for_salida' in MAIN


def test_rc5_captain_menu_distinguishes_charge_vs_free():
    assert 'No embarcó / con cargo' in CAPTAIN
    assert 'No embarca / sin cargo' in CAPTAIN
    assert 'attendanceAbsentMenuForm' in CAPTAIN
    assert 'attendanceNoBoardMenuForm' in CAPTAIN
    assert '.capAction.absentAction' in STYLE
    assert '.capAction.noBoardAction' in STYLE
