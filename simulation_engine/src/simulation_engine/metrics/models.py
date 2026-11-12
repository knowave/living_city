"""도시 지표 열거형과 지표 레코드(WorldMetric)를 담는다."""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


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


@dataclass(slots=True, kw_only=True)
class WorldMetric:
    """tick·기간별 도시 지표 값 레코드. backend WorldMetric 대응."""

    id: uuid.UUID
    tick: int
    metric_code: MetricCode
    metric_value: Decimal
    unit: MetricUnit
    period: MetricPeriod
    definition_version: int = 1
