from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")


def test_rc10_async_helpers_exist():
    assert "def queue_email_background_task" in MAIN
    assert "def queue_email_after_response" in MAIN
    assert "BackgroundTasks" in MAIN


def test_add_guest_does_not_build_guest_summary_synchronously():
    segment = MAIN.split('@app.post("/socio/add_guest")', 1)[1].split('@app.post("/socio/add_protocolar")', 1)[0]
    assert "queue_email_after_response(background_tasks" in segment
    assert '"resumen_invitados": ""' in segment
    assert "guest_reservation_summary_for_email(db, outing.id, user.id)" not in segment


def test_email_failure_cannot_block_reservation_comment_present():
    assert "Si el email falla o tarda, nunca bloquea la reserva" in MAIN
