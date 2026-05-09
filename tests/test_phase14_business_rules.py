from app.core.business_rules import (
    validate_admin_reset_confirmation,
    validate_capacity,
    validate_captain_close_window,
    validate_guest_has_responsible_member,
    validate_no_duplicate_document,
    validate_outing_open_for_reservation,
    validate_reservation_state_transition,
    validate_role_access,
)


def test_capacity_allows_available_seat():
    assert validate_capacity(current_active=8, max_capacity=9).ok


def test_capacity_blocks_overbooking():
    result = validate_capacity(current_active=9, max_capacity=9)
    assert not result.ok
    assert result.code == "capacity_exceeded"


def test_duplicate_document_blocked():
    result = validate_no_duplicate_document("20123456", ["20123456", "30999111"])
    assert not result.ok
    assert result.code == "duplicate_document"


def test_outing_closed_blocks_new_reservation():
    result = validate_outing_open_for_reservation("cerrada")
    assert not result.ok
    assert result.code == "outing_not_open"


def test_cancelled_reservation_cannot_go_direct_present():
    result = validate_reservation_state_transition("cancelada", "presente")
    assert not result.ok
    assert result.code == "cancelled_to_present_blocked"


def test_admin_role_allowed_for_admin_endpoint():
    assert validate_role_access("admin", ["admin"]).ok


def test_socio_role_blocked_from_admin_endpoint():
    result = validate_role_access("socio", ["admin"])
    assert not result.ok
    assert result.code == "role_forbidden"


def test_guest_requires_responsible_member():
    result = validate_guest_has_responsible_member("")
    assert not result.ok
    assert result.code == "guest_without_responsible"


def test_captain_close_before_departure_blocked():
    result = validate_captain_close_window(now_ts=1000, departure_ts=2000)
    assert not result.ok
    assert result.code == "close_before_departure"


def test_captain_close_inside_window_allowed():
    assert validate_captain_close_window(now_ts=2500, departure_ts=2000).ok


def test_admin_reset_confirmation_exact():
    assert validate_admin_reset_confirmation("RESET OPERATIVO FJORD VI", "RESET OPERATIVO FJORD VI").ok
