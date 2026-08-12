"""Configurable MCX session boundaries in India time."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from zoneinfo import ZoneInfo


MCX_KOLKATA = ZoneInfo("Asia/Kolkata")


class SessionSegment(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"

    @classmethod
    def parse(cls, value: str) -> "SessionSegment":
        try:
            return cls(value.lower())
        except ValueError as exc:
            raise ValueError("segment must be one of: morning, afternoon, evening") from exc

    def ends_at(self, now: datetime) -> datetime:
        local = now.astimezone(MCX_KOLKATA)
        hour, minute = {
            SessionSegment.MORNING: (15, 0),
            SessionSegment.AFTERNOON: (21, 0),
            SessionSegment.EVENING: (23, 30),
        }[self]
        return local.replace(hour=hour, minute=minute, second=0, microsecond=0)

    def starts_at(self, now: datetime) -> datetime:
        local = now.astimezone(MCX_KOLKATA)
        hour, minute = {
            SessionSegment.MORNING: (9, 0),
            SessionSegment.AFTERNOON: (15, 0),
            SessionSegment.EVENING: (21, 0),
        }[self]
        return local.replace(hour=hour, minute=minute, second=0, microsecond=0)


def seconds_remaining(now: datetime, segment: SessionSegment) -> float:
    local = now.astimezone(MCX_KOLKATA)
    if local < segment.starts_at(local):
        return 0.0
    return max(0.0, (segment.ends_at(local) - local).total_seconds())

