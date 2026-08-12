from datetime import datetime

from crudeoil_chain.timebox import MCX_KOLKATA, SessionSegment, seconds_remaining


def test_afternoon_segment_uses_configured_mcx_evening_close() -> None:
    now = datetime(2026, 8, 12, 19, 0, tzinfo=MCX_KOLKATA)

    assert SessionSegment.AFTERNOON.ends_at(now) == datetime(2026, 8, 12, 21, 0, tzinfo=MCX_KOLKATA)
    assert seconds_remaining(now, SessionSegment.AFTERNOON) == 2 * 60 * 60


def test_evening_segment_covers_the_final_mcx_session_window() -> None:
    now = datetime(2026, 8, 12, 21, 0, tzinfo=MCX_KOLKATA)

    assert SessionSegment.parse("evening") is SessionSegment.EVENING
    assert SessionSegment.EVENING.ends_at(now) == datetime(2026, 8, 12, 23, 30, tzinfo=MCX_KOLKATA)

