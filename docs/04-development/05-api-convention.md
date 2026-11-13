# API 및 DB 컨벤션

> 근거: README §3.9, §9, §10 및 backend 구조. 없는 항목은 `TBD`.

- REST는 조회와 사용자 명령, SSE는 서버 발생 상태 변경 전달을 담당한다. (README §9.1, §9.2)
- 모든 동기화 이벤트는 세계별 증가하는 Sequence를 가진다. (README §9.3)
- 데이터 변경과 이벤트 저장은 같은 트랜잭션에서 처리하고, 이벤트 발행은 커밋 이후에 한다. (README §3.9, §7.2)
- 금전 이동은 원장(accounts, transactions, ledger_entries)에 기록한다. (README §3.8, §10.2)
- 완전한 Event Sourcing은 MVP에서 도입하지 않는다. (README §10.2)
- PostgreSQL을 사용한다. (README §10.1)
- API 버전 접두사는 `API_V1_STR`(`/api/v1`)이다. (backend/app/core/config.py)

- 테이블/컬럼 네이밍: 테이블은 복수형 snake_case, 컬럼은 snake_case, 제약 이름은 `uq_`/`idx_`/`fk_`/`ck_` 접두사를 쓴다. 상세는 [데이터 저장 설계 §10.3](../03-architecture/06-database.md). (코드 기준: backend/app/models/*.py)

- JSON 필드명은 snake_case다.

## 에러 응답 형식

```json
{"error": {"code": "WORLD_NOT_FOUND", "message": "...", "details": ...}}
```

`details`는 선택이다.

| 예외 | HTTP |
|---|---|
| `NotFoundError` | 404 |
| `ConflictError` | 409 |
| `InvalidStateError` | 409 |
| `DomainValidationError` | 422 |
| 요청 검증 실패 | 422, code `VALIDATION_ERROR`, `details`에 오류 목록 |

- controller에는 try/except를 두지 않는다. 전역 핸들러가 `app/main.py`에서 위 형식으로 변환한다.

## 미정

- 마이그레이션 파일 규칙: TBD
- 인증: TBD
