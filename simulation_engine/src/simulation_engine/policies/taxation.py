"""세금 정책을 담는다."""


def income_tax(gross: int, rate_bps: int) -> int:
    """소득세 = gross × rate_bps / 10000, 원 미만 버림(floor)."""
    return gross * rate_bps // 10_000
