from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")


def test_email_skin_generates_html_primary_only_at_smtp_send():
    assert 'msg.set_content(body_html, subtype="html")' in MAIN
    assert 'HTML primario: Gmail/Android debe mostrar la tarjeta institucional' in MAIN


def test_email_skin_keeps_queue_email_lightweight():
    queue_start = MAIN.index("def queue_email(")
    queue_end = MAIN.index("RETRYABLE_NOTIFICATION_STATUSES", queue_start)
    block = MAIN[queue_start:queue_end]
    assert "build_notification_html_email" not in block
    assert "add_alternative" not in block


def test_cancel_guest_is_individual_and_does_not_recompute_group():
    route_start = MAIN.index('@app.post("/socio/cancel_guest/{rid}")')
    route_end = MAIN.index('@app.post("/socio/cancel/{rid}")', route_start)
    block = MAIN[route_start:route_end]
    assert 'promoted = promote_waitlist(db, outing)' in block
    assert 'recompute_waitlist_for_salida' not in block
    assert 'dependientes =' not in block
