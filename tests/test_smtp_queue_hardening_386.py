from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")


def test_smtp_queue_has_processing_claim_columns_and_indexes():
    assert "processing_token = Column" in MAIN
    assert "processing_started_at = Column" in MAIN
    assert "ALTER TABLE notification_queue ADD COLUMN processing_token" in MAIN
    assert "ALTER TABLE notification_queue ADD COLUMN processing_started_at" in MAIN
    assert "idx_notification_queue_processing_token" in MAIN
    assert "idx_notification_queue_status_scheduled" in MAIN


def test_smtp_queue_claims_before_sending():
    claim_pos = MAIN.index("def claim_notification_queue_batch")
    process_pos = MAIN.index("def process_notification_queue(db: Session")
    send_pos = MAIN.index("send_email_now(db, row.recipient_email", process_pos)
    assert claim_pos < process_pos < send_pos
    body = MAIN[process_pos: MAIN.index("def process_notification_queue_ids", process_pos)]
    assert "claim_notification_queue_batch" in body
    assert "row.status = \"processing\"" in MAIN
    assert "processing_token == token" in MAIN
    assert "with_for_update(skip_locked=True)" in MAIN


def test_smtp_queue_finalizes_each_claimed_row_with_commit():
    assert "def finalize_claimed_notification" in MAIN
    assert "row.processing_token = \"\"" in MAIN
    assert "row.processing_started_at = None" in MAIN
    assert "db.commit()" in MAIN[MAIN.index("def finalize_claimed_notification"): MAIN.index("def process_notification_queue", MAIN.index("def finalize_claimed_notification"))]


def test_recovery_handles_processing_after_restart():
    assert "def recover_stale_processing_notifications" in MAIN
    assert "status == \"processing\"" in MAIN
    assert "Recovery post restart" in MAIN
    assert "recovered_processing" in MAIN


def test_selective_queue_uses_same_claim_guard():
    start = MAIN.index("def process_notification_queue_ids")
    end = MAIN.index("def smtp_connection_probe", start)
    body = MAIN[start:end]
    assert "claim_notification_queue_batch" in body
    assert "dos clicks o dos procesadores simultáneos" in body
