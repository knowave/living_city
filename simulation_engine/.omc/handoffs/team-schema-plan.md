## Handoff: team-plan → team-exec (backend schema → engine dataclass)

- **Decided**: backend/app/models(SQLAlchemy)를 엔진 dataclass(slots=True, kw_only=True)로 미러링. stdlib only. DB 전용 필드(created_at, updated_at, 낙관적 락 version, world_id FK)는 제외 — WorldState가 world 범위를 가진다. id는 uuid.UUID. 비율 float(risk_tolerance, consumption_preference)는 엔진 규칙대로 int bps. Enum은 StrEnum 값 동일.
- **위치(7.10 TBD 해소)**: entities/{world,citizen,household,company,employment,building,policy}.py, economy/{account,transaction,ledger}.py, events/models.py(WorldEvent), world/{snapshot,map_chunk}.py, metrics/models.py. entities/business.py → company.py (docs·backend 명칭 Company).
- **Rejected**: Business 이름 유지(docs/backend 불일치), DB 메타 필드 포함(엔진 무관).
- **Workers**: w-entities(sonnet), w-economy(sonnet), w-records(haiku). 리드: docs 갱신, test_package.py 모듈 목록.
- **Risks**: float→bps 변환은 backend 어댑터 책임(미구현).
