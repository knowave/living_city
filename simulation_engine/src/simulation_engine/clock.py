"""Tick 시간 계산. 1 Tick = 1시간."""

TICKS_PER_DAY = 24
DAYS_PER_MONTH = 30
MONTHS_PER_YEAR = 12
TICKS_PER_MONTH = TICKS_PER_DAY * DAYS_PER_MONTH
TICKS_PER_YEAR = TICKS_PER_MONTH * MONTHS_PER_YEAR


def hour_of(tick: int) -> int:
    return tick % TICKS_PER_DAY


def day_of(tick: int) -> int:
    return tick // TICKS_PER_DAY


def month_of(tick: int) -> int:
    return tick // TICKS_PER_MONTH


def is_month_end(tick: int) -> bool:
    return tick % TICKS_PER_MONTH == TICKS_PER_MONTH - 1
