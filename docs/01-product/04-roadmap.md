> 원본: README §12

## 12. 개발 로드맵

### Phase 1. 설계 및 프로젝트 기반

- 도메인 모델 확정
- 경제 거래 모델 확정
- 엔진 입력 및 출력 인터페이스 정의
- Repository 구성과 개발 환경 설정
- 테스트 기반 구성

완료 기준: 세계 상태와 핵심 도메인을 코드로 표현하고 단위 테스트 실행 가능

### Phase 2. Isometric 렌더링

- Three.js/R3F 씬 초기화
- 지형·도로·건물 렌더링 (OrthographicCamera)
- 카메라 이동 및 줌
- 타일 선택
- Chunk Manager
- 건물 렌더링 (3D 깊이 버퍼)

완료 기준: 도시 맵을 자유롭게 탐색하고 건물을 선택할 수 있음

### Phase 3. 시뮬레이션 엔진

- 도시 생성
- 시민과 기업 초기화
- 시뮬레이션 시간
- 행동 결정 엔진
- 시드 기반 난수
- 상태 전이 및 엔진 테스트

완료 기준: UI가 없어도 도시가 독립적으로 진행됨

### Phase 4. 경제 시스템

- 고용 및 구직
- 급여 지급
- 소득세 징수
- 소비와 매출
- 복지
- 기업 채용, 해고 및 파산
- 경제 원장

완료 기준: 시민, 기업, 정부 사이에 검증 가능한 자금 흐름이 존재함

### Phase 5. REST 및 SSE 통합

- 도시 상태 조회
- 실행 및 정지 제어
- 정책 변경
- 이벤트 저장 및 발행
- SSE 실시간 동기화
- 스냅샷 및 연결 복구

완료 기준: 프론트엔드가 서버에서 진행되는 도시 변화를 실시간 반영

### Phase 6. 도시 인터랙션과 대시보드

- 시민 이동 시각화
- 시민 및 기업 정보 패널
- 경제 통계
- 주요 사건 타임라인
- 도시 정책 화면
- 부하 및 안정성 검증

완료 기준: 사용자가 도시를 관찰하고 소득세율을 변경한 후 경제적 변화를 확인할 수 있음

### Phase 7. 확장 기능

- 주거시장
- 인구 변화
- 교육 및 건강
- 사회적 관계
- 기업 업종 고도화
- 절차적 지도 생성
- 세계 복제 및 정책 비교

---

## 05-phases 대응

| 원본 Phase 항목 | 대응 phase 파일 |
|---|---|
| Phase 1: 도메인 모델 확정, 엔진 입력 및 출력 인터페이스 정의 | [phase-04](../05-phases/phase-04-simulation-engine.md) |
| Phase 1: 경제 거래 모델 확정 | [phase-05](../05-phases/phase-05-economic-system.md) |
| Phase 1: Repository 구성과 개발 환경 설정, 테스트 기반 구성 | [phase-01](../05-phases/phase-01-map-prototype.md) |
| Phase 2: Three.js/R3F 씬 초기화, 지형·도로·건물 렌더링, 카메라 이동 및 줌, 타일 선택 | [phase-01](../05-phases/phase-01-map-prototype.md) |
| Phase 2: Chunk Manager, 건물 렌더링 (3D 깊이 버퍼) | [phase-02](../05-phases/phase-02-chunk-rendering.md) |
| Phase 3: 전체 | [phase-04](../05-phases/phase-04-simulation-engine.md) |
| Phase 4: 전체 | [phase-05](../05-phases/phase-05-economic-system.md) |
| Phase 5: REST 및 SSE 통합 전체 | 향후 phase (미정) |
| Phase 6: 시민 이동 시각화 | [phase-03](../05-phases/phase-03-citizen-movement.md) |
| Phase 6: 시민 및 기업 정보 패널, 경제 통계, 주요 사건 타임라인, 도시 정책 화면, 부하 및 안정성 검증 | 향후 phase (미정) |
| Phase 7: 확장 기능 전체 | 향후 phase (미정) |
