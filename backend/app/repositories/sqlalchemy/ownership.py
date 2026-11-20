from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.runner.interfaces import OwnershipHandle, OwnershipLock


class _Handle(OwnershipHandle):
    def __init__(self, conn: Connection, key: int) -> None:
        self._conn: Connection | None = conn
        self._key = key

    def release(self) -> None:
        conn, self._conn = self._conn, None
        if conn is None:
            return
        try:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": self._key})
        except Exception:
            conn.invalidate()  # drop the session so the lock cannot linger in the pool
        try:
            conn.close()
        except Exception:
            pass


class PgAdvisoryOwnershipLock(OwnershipLock):
    """Session-level advisory lock; the dedicated connection must stay open while owned."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def try_acquire(self, world_id: UUID) -> OwnershipHandle | None:
        key = int.from_bytes(world_id.bytes[:8], "big", signed=True)
        conn = self._engine.connect()
        try:
            got = conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": key}).scalar()
        except Exception:
            conn.close()
            raise
        if not got:
            conn.close()
            return None
        return _Handle(conn, key)
