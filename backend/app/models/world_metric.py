import uuid
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseEntity


class MetricCode(StrEnum):
    POPULATION = "POPULATION"
    EMPLOYED_POPULATION = "EMPLOYED_POPULATION"
    UNEMPLOYMENT_RATE = "UNEMPLOYMENT_RATE"
    AVERAGE_SALARY = "AVERAGE_SALARY"
    AVERAGE_WEALTH = "AVERAGE_WEALTH"
    TOTAL_CONSUMPTION = "TOTAL_CONSUMPTION"
    TOTAL_COMPANY_REVENUE = "TOTAL_COMPANY_REVENUE"
    ACTIVE_COMPANIES = "ACTIVE_COMPANIES"
    BANKRUPT_COMPANIES = "BANKRUPT_COMPANIES"
    GOVERNMENT_REVENUE = "GOVERNMENT_REVENUE"
    GOVERNMENT_EXPENDITURE = "GOVERNMENT_EXPENDITURE"
    AVERAGE_HAPPINESS = "AVERAGE_HAPPINESS"


class MetricUnit(StrEnum):
    COUNT = "COUNT"
    KRW = "KRW"
    PERCENT = "PERCENT"
    RATIO = "RATIO"
    INDEX = "INDEX"


class MetricPeriod(StrEnum):
    HOURLY = "HOURLY"
    DAILY = "DAILY"
    MONTHLY = "MONTHLY"


class WorldMetric(BaseEntity):
    __tablename__ = "world_metrics"
    __table_args__ = (
        UniqueConstraint("world_id", "id", name="uq_world_metrics_world_id_id"),
        UniqueConstraint("world_id", "tick", "metric_code", "period", name="uq_world_metrics"),
        Index("idx_world_metrics_chart", "world_id", "metric_code", "period", text("tick DESC")),
    )

    world_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("worlds.id", ondelete="RESTRICT"), nullable=False
    )
    tick: Mapped[int] = mapped_column(BigInteger)
    metric_code: Mapped[str] = mapped_column(String(64))
    metric_value: Mapped[Decimal] = mapped_column(Numeric(24, 6))
    unit: Mapped[str] = mapped_column(String(20))
    period: Mapped[str] = mapped_column(String(10))
    definition_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
