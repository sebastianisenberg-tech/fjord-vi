from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / 'main.py').read_text(encoding='utf-8')
CAPTAIN = (ROOT / 'templates' / 'captain.html').read_text(encoding='utf-8')

def test_captain_cancel_clears_embarked_state_without_charge():
    assert 'Cancelación total de salida: nadie debe seguir figurando embarcado.' in MAIN
    assert 'r.attendance = "No embarca"' in MAIN
    assert 'reason = "Salida cancelada por capitán"' in MAIN
    assert 'r.charge_amount = 0' in MAIN

def test_reopen_after_total_cancel_returns_to_pending_not_noshow_charge():
    assert 'if "salida cancelada" in reason_l:' in MAIN
    assert 'r.attendance = "Por confirmar"' in MAIN
    assert 'r.cancel_reason = reassignment_trace_only' in MAIN

def test_fast_captain_row_blocks_second_tap_before_reload():
    assert "row.dataset.submitting === '1'" in CAPTAIN
    assert "row.dataset.submitting = '1'" in CAPTAIN
    assert "Acción en proceso" in CAPTAIN
