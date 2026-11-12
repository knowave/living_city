## Handoff: team-exec → complete (backend schema → engine dataclass)

- **Verified**: Python 3.12에서 `PYTHONPATH=src python3.12 -m unittest` 24개 OK. src/tests 아래 .omc 없음. stdlib 외 import 없음.
- **Risks**: 이 머신 기본 python3는 3.9라서 StrEnum import 실패 → 3.12+ 인터프리터 필요. WorldMetric의 code/unit/period를 enum으로 타입 지정함 (backend는 str).
- **Remaining**: float→bps 변환 어댑터(backend), System 로직, entities/government.py (backend 테이블 없음).
