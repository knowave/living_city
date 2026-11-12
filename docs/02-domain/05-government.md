# Government

> 원본: README §3.7

### 3.7 Government & Policy — 정부와 정책

정부는 세금을 징수하고 공공 지출을 실행한다.

정책 속성:

- worldId
- incomeTaxRate
- welfareAmount
- effectiveTick
- version

초기 소득세율은 15%로 설정한다.

> 코드 기준 갱신: 엔진 클래스명은 WorldPolicy(`simulation_engine/src/simulation_engine/entities/policy.py:8-12`)다. income_tax_rate는 정수 bps로 기본값 1500(= 15%), welfare_amount 기본값 0, effective_tick은 정책이 적용되는 Tick이다. 엔진에는 아직 Government 엔티티 클래스가 없다 (`entities/government.py`는 docstring만 있음). 정부 계정은 Account(owner_type=GOVERNMENT)로 표현한다 (코드 기준).

정책 변경은 명령으로 접수하며, 다음 시뮬레이션 Tick의 명확한 경계에서 적용한다.

