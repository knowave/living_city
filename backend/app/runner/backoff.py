def next_delay(failures: int, max_ms: int, base_ms: int = 1000) -> int:
    return min(base_ms * 2 ** (failures - 1), max_ms)
