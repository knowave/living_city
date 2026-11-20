"""결정적 파생 RNG. 전역 random과 hash()를 쓰지 않는다."""

import hashlib
import random


def derive_rng(seed: int, *keys: object) -> random.Random:
    """(seed, keys)에서 독립된 RNG 스트림을 만든다. 상태를 저장하지 않으므로 처리 순서에 영향받지 않는다."""
    digest = hashlib.sha256(repr((seed, *keys)).encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))
