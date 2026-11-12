# 테스트 가이드

> 원본: README §11.3

**엔진 단위 테스트**

- 시민 행동 조건
- 채용 및 해고 조건
- 세금 계산
- 경제 거래 및 자금 보존
- 결정적 난수 재현

**통합 테스트**

- Tick 실행과 DB 저장
- REST 명령의 상태 변경
- SSE 이벤트 재전송
- 스냅샷 기반 복구
- 중복 요청 및 동시 실행 방지

**프론트엔드 테스트**

- Isometric 좌표 변환과 역변환
- 화면 밖 Chunk 제외
- 건물 및 시민 선택
- SSE 중복 이벤트 처리
- 시민 이동 애니메이션
- 장시간 카메라 이동 시 메모리 누수 확인

## 실행 방법

> 근거: backend/pyproject.toml (`[dependency-groups] dev = ["pytest", "httpx"]`, `[tool.pytest.ini_options] pythonpath = ["."]`), backend/tests/, frontend/package.json scripts, simulation_engine/tests/ (코드 기준)

- backend: `cd backend && uv run pytest`
- frontend: `cd frontend && yarn test` (vitest, 현재 `src/smoke.test.ts` 1개) (코드 기준)
- simulation_engine: `cd simulation_engine && PYTHONPATH=src uv run --no-project --python 3.12 python -m unittest` (코드 기준. 시스템 python3가 3.12 미만이면 실패)
