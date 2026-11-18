# Living City 문서

설계 명세의 목차. 프로젝트 소개와 실행 방법은 [루트 README](../README.md), AI 에이전트 지침은 [CLAUDE.md](../CLAUDE.md)를 참고한다.

## 01-product

- [01-overview](01-product/01-overview.md): 문서 버전 정보, 프로젝트 개요, 핵심 목표와 사용자 경험, 최종 설계 원칙
- [02-requirements](01-product/02-requirements.md): 초기 세계 기본값, 비기능 요구사항(성능, 안정성), MVP 출시 기준
- [03-features](01-product/03-features.md): MVP 포함 기능과 제외 기능
- [04-roadmap](01-product/04-roadmap.md): 원본 개발 로드맵 Phase 1-7과 05-phases 대응 표

## 02-domain

- [01-domain-overview](02-domain/01-domain-overview.md): 도메인 엔티티 목록과 관계
- [02-world](02-domain/02-world.md): World, Building, WorldEvent, WorldSnapshot
- [03-citizen](02-domain/03-citizen.md): Citizen, Household, 시민 행동 시스템
- [04-business](02-domain/04-business.md): Company, Employment, 기업 행동 시스템
- [05-government](02-domain/05-government.md): 정부와 정책
- [06-economy](02-domain/06-economy.md): 경제 원장, 경제 시뮬레이션, 자금 보존
- [07-simulation-rules](02-domain/07-simulation-rules.md): Tick, 달력, 배속, 결정적 실행, 정책 적용 경계

## 03-architecture

- [01-system-architecture](03-architecture/01-system-architecture.md): 계층 책임, 실행 주체, 안정성
- [02-tech-stack](03-architecture/02-tech-stack.md): backend, simulation_engine, frontend 기술 스택
- [03-simulation-engine](03-architecture/03-simulation-engine.md): 엔진 설계 원칙, 실행 순서, 결정적 실행
- [04-map-rendering](03-architecture/04-map-rendering.md): Isometric 맵, Chunk, 렌더링 계층
- [05-data-flow](03-architecture/05-data-flow.md): 이동 데이터 흐름, 커밋 후 이벤트 발행, 이벤트 복구, 일관성 원칙
- [06-database](03-architecture/06-database.md): PostgreSQL 테이블과 데이터 구분, Implemented Baseline과 우선 검토 항목(§10.5)
- [07-rest-sse](03-architecture/07-rest-sse.md): REST API 목록과 SSE 이벤트

## 04-development

- [01-common-convention](04-development/01-common-convention.md): 공통 컨벤션
- [02-backend-convention](04-development/02-backend-convention.md): backend 컨벤션
- [03-frontend-convention](04-development/03-frontend-convention.md): frontend 컨벤션
- [04-simulation-convention](04-development/04-simulation-convention.md): 시뮬레이션 엔진 컨벤션
- [05-api-convention](04-development/05-api-convention.md): API 컨벤션
- [06-testing-guide](04-development/06-testing-guide.md): 엔진, 통합, 프론트엔드 테스트 항목

## 05-phases

- [phase-01-map-prototype](05-phases/phase-01-map-prototype.md): 프로젝트 기반, Three.js/R3F 초기화, 지형·도로·건물, 카메라, 타일 선택
- [phase-02-chunk-rendering](05-phases/phase-02-chunk-rendering.md): Chunk Manager, 건물 렌더링, 512x512 검증
- [phase-03-citizen-movement](05-phases/phase-03-citizen-movement.md): 시민 이동 시각화
- [phase-04-simulation-engine](05-phases/phase-04-simulation-engine.md): 도메인·엔진 인터페이스, 시뮬레이션 엔진
- [phase-05-economic-system](05-phases/phase-05-economic-system.md): 경제 시스템

## 원본 README 섹션 → 문서 대응표

원본 설계 명세는 `.omc/backup/README.original.md`에 백업되어 있다.

| 원본 | 대상 |
|---|---|
| 헤더(Version 등), §1 | [01-product/01-overview](01-product/01-overview.md) |
| §14 | [01-product/01-overview](01-product/01-overview.md), [03-architecture/01-system-architecture](03-architecture/01-system-architecture.md) |
| §2.1, §11.1, §11.2, §13 | [01-product/02-requirements](01-product/02-requirements.md) |
| §2.2, §2.3 | [01-product/03-features](01-product/03-features.md) |
| §12 (Phase 1-7 전체) | [01-product/04-roadmap](01-product/04-roadmap.md) |
| §3 개요 | [02-domain/01-domain-overview](02-domain/01-domain-overview.md) |
| §3.1, §3.6, §3.9, §3.10 | [02-domain/02-world](02-domain/02-world.md) |
| §3.2, §3.3, §4 | [02-domain/03-citizen](02-domain/03-citizen.md) |
| §3.4, §3.5, §5 | [02-domain/04-business](02-domain/04-business.md) |
| §3.7 | [02-domain/05-government](02-domain/05-government.md) |
| §3.8, §6 | [02-domain/06-economy](02-domain/06-economy.md) |
| §2.1 시간 규칙, §6.3, §7.3, 정책의 Tick 경계 적용 | [02-domain/07-simulation-rules](02-domain/07-simulation-rules.md) |
| §7.4, §11.2, §14 | [03-architecture/01-system-architecture](03-architecture/01-system-architecture.md) |
| 기술 스택(§7.1, §8, §10, §14 + backend 사실) | [03-architecture/02-tech-stack](03-architecture/02-tech-stack.md) |
| §7 | [03-architecture/03-simulation-engine](03-architecture/03-simulation-engine.md) |
| §8 | [03-architecture/04-map-rendering](03-architecture/04-map-rendering.md) |
| §4.4, §7.2(9-10단계), §8.4, §9.3, §9.4 | [03-architecture/05-data-flow](03-architecture/05-data-flow.md) |
| §10 | [03-architecture/06-database](03-architecture/06-database.md) |
| §9.1, §9.2 | [03-architecture/07-rest-sse](03-architecture/07-rest-sse.md) |
| §11.3 | [04-development/06-testing-guide](04-development/06-testing-guide.md) |

## 원본 Phase → 05-phases 대응표

| 파일 | 원본 출처 |
|---|---|
| [phase-01-map-prototype](05-phases/phase-01-map-prototype.md) | Phase 1 프로젝트 기반, Phase 2 Three.js/R3F 초기화, 지형·도로·건물, 카메라, 타일 선택 |
| [phase-02-chunk-rendering](05-phases/phase-02-chunk-rendering.md) | Phase 2 Chunk Manager, 건물 렌더링, 512×512 검증 |
| [phase-03-citizen-movement](05-phases/phase-03-citizen-movement.md) | Phase 6 시민 이동 시각화, §4.4, §8.4 |
| [phase-04-simulation-engine](05-phases/phase-04-simulation-engine.md) | Phase 1 도메인·엔진 인터페이스, Phase 3 전체 |
| [phase-05-economic-system](05-phases/phase-05-economic-system.md) | Phase 4 전체 |

위 5개에 들어가지 않는 Phase 5(REST/SSE), Phase 6의 나머지 항목, Phase 7은 [04-roadmap](01-product/04-roadmap.md)에 "향후 phase"로 표시한다.
