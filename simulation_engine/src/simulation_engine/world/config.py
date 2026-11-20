"""시뮬레이션 설정값. 규칙 수치는 모두 여기에 둔다. 금액은 원(int), 비율은 bps."""

from dataclasses import dataclass, field

RETAIL = "RETAIL"
RESTAURANT = "RESTAURANT"
WHOLESALE = "WHOLESALE"
BUSINESS_SERVICE = "BUSINESS_SERVICE"


@dataclass(frozen=True, slots=True)
class IndustryConfig:
    industry: str
    count: int
    base_wage: int
    employee_capacity: int
    building_type: str  # BuildingType 값 (COMMERCIAL / OFFICE)


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    # 세계 규모
    map_size: int = 128
    citizen_count: int = 100
    residential_buildings: int = 10
    residential_capacity: int = 10
    commercial_buildings: int = 6
    office_buildings: int = 4
    public_buildings: int = 1
    citizen_age_range: tuple[int, int] = (20, 64)
    consumption_preference_range: tuple[int, int] = (5000, 9000)

    # 업종·기업
    industries: tuple[IndustryConfig, ...] = (
        IndustryConfig(RETAIL, 3, 2_400_000, 12, "COMMERCIAL"),
        IndustryConfig(RESTAURANT, 3, 2_400_000, 12, "COMMERCIAL"),
        IndustryConfig(WHOLESALE, 2, 3_000_000, 6, "OFFICE"),
        IndustryConfig(BUSINESS_SERVICE, 2, 3_600_000, 2, "OFFICE"),
    )  # 정원: 2026-11-19 보정안 C1
    initial_employed: int = 88
    operating_cost: int = 5_000_000  # 기업당 월
    opex_b2b_bps: int = 7000
    opex_government_bps: int = 2000
    opex_external_bps: int = 1000
    supplier_of: dict[str, str] = field(
        default_factory=lambda: {
            RETAIL: WHOLESALE,
            RESTAURANT: WHOLESALE,
            WHOLESALE: BUSINESS_SERVICE,
            BUSINESS_SERVICE: WHOLESALE,
        }
    )

    # 초기 자금
    citizen_opening_balance: int = 3_000_000
    company_opening_months: int = 3  # 월 고정비(급여 총액 + 운영비) 배수
    government_opening_balance: int = 50_000_000

    # 정책 기본값
    income_tax_rate_bps: int = 1500
    welfare_amount: int = 1_000_000
    procurement_budget_bps: int = 5000
    export_bps: int = 5000  # 외부(SYSTEM CASH) 잔액 중 월 수출로 재유입되는 비율. 보정 대상

    # 시민 일과
    work_start_hour: int = 8
    work_end_hour: int = 18
    shop_hour: int = 19
    tiles_per_tick: int = 40
    first_month_income_bps: int = 8500
    cash_reserve: int = 1_000_000  # 이 금액을 넘는 현금의 일부를 추가 소비 (2026-11-19 보정안 C1)
    extra_spend_bps: int = 3000  # 2026-11-19 보정안 C1

    # 기업 상태 판정
    distress_cash_months: int = 1
    recovery_cash_months: int = 2
    bankrupt_distressed_months: int = 3
