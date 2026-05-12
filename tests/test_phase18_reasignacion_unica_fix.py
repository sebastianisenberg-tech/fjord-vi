from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / 'main.py').read_text(encoding='utf-8')
TPL = (ROOT / 'templates' / 'captain.html').read_text(encoding='utf-8')


def test_reassignment_uses_persistent_fields_not_cancel_reason_as_source_of_truth():
    assert 'original_responsible_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)' in MAIN
    assert 'reassignment_count = Column(Integer, default=0)' in MAIN
    assert 'class ReservationReassignment(Base):' in MAIN
    assert 'record_reservation_reassignment' in MAIN
    assert 'if reassignment_trace_only(r.cancel_reason or ""):' not in MAIN.split('@app.post("/captain/reassign/{rid}")', 1)[1].split('return RedirectResponse(f"/captain?outing_id={outing.id}&msg=reasignacion_ok", status_code=303)',1)[0]


def test_reassign_endpoint_updates_final_responsible_and_counter():
    assert 'r.responsible_user_id = new_responsible.id' in MAIN
    assert 'r.reassignment_count = reservation_reassignment_count_value(r) + 1' in MAIN
    assert 'r.last_reassigned_at = now_local()' in MAIN
    assert 'r.last_reassigned_by = user.name' in MAIN


def test_captain_template_keeps_reassign_controls_available_and_shows_count():
    assert '{% if v.show_responsible and captain_responsible_options|length > 0 %}' in TPL
    assert 'Reasignado {{v.reassignment_count}} vez' in TPL


def test_captain_context_groups_from_current_responsible_and_exposes_count():
    assert 'return f"u-{rr.responsible_user_id}"' in MAIN
    assert 'v["reassignment_count"] = reservation_reassignment_count_value(r)' in MAIN
    assert 'v["is_reassigned"] = reservation_is_reassigned(r)' in MAIN
