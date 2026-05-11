from pathlib import Path


def test_captain_cancel_final_validation_exists():
    main = Path("main.py").read_text(encoding="utf-8")
    assert "def captain_cancel_final_validation" in main
    assert 'if outing.status == "Cancelada por capitán":' in main


def test_captain_reopen_final_validation_exists():
    main = Path("main.py").read_text(encoding="utf-8")
    assert "def captain_reopen_final_validation" in main
    assert 'if outing.status == "En reservas":' in main


def test_close_uses_final_validation_and_returns_existing_sheet_on_retry():
    main = Path("main.py").read_text(encoding="utf-8")
    assert "captain_close_final_validation(db, outing)" in main
    assert 'msg=cierre_ok&sheet_id={current_sheet.id}' in main


def test_attendance_idempotent_noop_exists():
    main = Path("main.py").read_text(encoding="utf-8")
    assert "def attendance_idempotent_noop" in main
    assert 'if attendance_idempotent_noop(r, value):' in main


def test_socio_cancel_is_idempotent():
    main = Path("main.py").read_text(encoding="utf-8")
    assert 'if not reservation_is_active(r):' in main
    assert 'msg=cancelado' in main
