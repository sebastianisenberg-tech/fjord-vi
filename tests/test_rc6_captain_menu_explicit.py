from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
CAPTAIN = (ROOT / 'templates' / 'captain.html').read_text(encoding='utf-8')
MAIN = (ROOT / 'main.py').read_text(encoding='utf-8')
CSS = (ROOT / 'static' / 'style.css').read_text(encoding='utf-8')


def test_rc6_menu_has_direct_no_show_with_charge():
    assert 'No se presentó / con cargo' in CAPTAIN
    assert 'attendanceAbsentMenuForm' in CAPTAIN
    assert 'action="/captain/attendance/{{r.id}}/Ausente"' in CAPTAIN


def test_rc6_menu_keeps_free_no_board_separate():
    assert 'No embarca / sin cargo' in CAPTAIN
    assert 'attendanceNoBoardMenuForm' in CAPTAIN
    assert 'no_board_reason' in CAPTAIN


def test_rc6_menu_has_present_and_pending_direct_corrections():
    assert 'Marcar presente' in CAPTAIN
    assert 'Volver a pendiente' in CAPTAIN
    assert 'action="/captain/attendance/{{r.id}}/Por confirmar"' in CAPTAIN


def test_rc6_direct_attendance_uses_stale_guard():
    assert 'acción capitán con pantalla desactualizada' in MAIN
    assert 'expected_attendance_is_stale(r, expected_current)' in MAIN


def test_rc6_absent_button_forced_visible_in_sheet():
    assert '.captainOpsSheetContent .attendanceAbsentMenuForm' in CSS
    assert '.capAction.absentAction' in CSS
