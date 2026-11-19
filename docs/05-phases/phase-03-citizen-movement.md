# Phase 3 — 시민 이동
> 원본: README §12 Phase 6(시민 이동 시각화), §4.4, §8.4

## 목표
엔진이 결정한 시민의 논리적 이동(출발·도착 Tick)을 프론트엔드가 도로망 기반 경로와 애니메이션으로 표현한다. 이 phase는 백엔드 없이 프론트엔드 Mock 시민으로 구현한다.

## 범위
- Mock 시민(seed 고정, 0/100/500/1000명, `?citizens=`가 없으면 100명)을 Phase 2 Chunk 도시 위에 그린다. Chunk 동작은 바꾸지 않는다.
- REST와 SSE는 쓰지 않는다. SSE 기반 기준(이동 이벤트 수신, 서버 Tick 동기화)은 Phase 4~5로 옮긴다.
- 시민 데이터는 이후 REST `CitizenRead`와 SSE `citizen.movement.started`를 그대로 받을 수 있는 형태(snake_case DTO + mapper)로 둔다. Mock 엔진은 이 DTO를 내보내는 임시 대역이다.
- 도착 Tick 산정은 Python 엔진 소유 규칙이다([03-citizen §4.4](../02-domain/03-citizen.md)). Phase 3의 프론트엔드 구현은 Mock 엔진 안의 임시 코드이며 Phase 4~5에서 엔진 값으로 대체한다.
- 제외: 충돌 회피, 정확한 교통 시뮬레이션, 경제·의사결정 로직, 경로 탐색 Web Worker.

## 작업
모듈은 `frontend/src/render/citizens/` 아래에 둔다.
1. 모델·시계: DTO/도메인 타입, mapper(신뢰 경계 검증), 논리 상태 store(좌표 없음), 논리 시계(`SimClock`, Mock 1 Tick = 10초, 속도 x1/x4/x16).
2. 도로망·경로: 전역 도로 연결 그리드, 건물 입구 타일, A*, 보도 offset polyline, 경로 스케줄러(`PathService`).
3. Mock 엔진·이동: seed 고정 시민 생성, 출발·도착 Tick 진행(A* 없음), 현재 Tick 기준 위치 계산, Chunk 가시성 압축.
4. 렌더: 공유 저폴리 geometry·material 1개와 InstancedMesh 1개.
5. 씬·UI: 시민 선택과 패널(휘발 필드는 ref로 갱신), 시민 수·속도 컨트롤, 디버그 HUD.
6. 검증: 단위 테스트, CDP 회귀, 성능표.

추가로 맵 생성기가 모든 건물 입구를 주 도로망 연결 요소에 연결하도록 검증한다([04-map-rendering §8.4](../03-architecture/04-map-rendering.md)).

## 확장성 원칙
- 렌더 비용은 보이는 시민 수에 비례한다(Chunk visible set 안의 시민만 instance 버퍼에 올린다).
- 시뮬레이션 비용은 엔진이 소유한다. 렌더 계층은 엔진 내부 계산에 의존하지 않고 출발·도착 Tick만 받는다.
- 두 비용을 분리해 측정하고 관리하므로 시민 10만 명까지 독립적으로 확장할 수 있다. Phase 3에서 실측으로 확인하는 상한은 1000명이다.

## 완료 기준
- 같은 seed와 정수 Tick이면 시민 생성과 이동 이벤트 시퀀스가 같다.
- DTO 필드가 backend `CitizenRead`와 일치한다(테스트로 대조).
- 시민은 도로 경로를 따라 이동하고, 화면 밖이나 숨김 탭 이후에도 현재 Tick 기준 같은 위치로 이어진다. 과거 이동을 다시 계산하지 않는다.
- 시민 InstancedMesh는 mesh·geometry·material 각 1개이며, 시민 추가로 draw call이 2 이하로만 늘어난다.
- 시민 선택 상태에서도 React 렌더 횟수가 늘지 않는다(패널 휘발 필드는 ref 갱신).
- 1000명에서 시민 프레임 작업 평균 2 ms 미만(x1, x16), pan/zoom 중 long task 0건.
- Phase 2 회귀 기준 유지, `yarn typecheck && yarn lint && yarn test && yarn build` 통과.

원본 Phase 6 완료 기준(소득세율 변경 후 경제적 변화 확인)과 "브라우저를 닫아도 논리적 이동이 진행된다"는 서버 연동이 필요하므로 Phase 4~5에서 확인한다.

## 참고 문서
- [03-citizen](../02-domain/03-citizen.md)
- [07-simulation-rules](../02-domain/07-simulation-rules.md)
- [04-map-rendering](../03-architecture/04-map-rendering.md)
- [05-data-flow](../03-architecture/05-data-flow.md)
- [03-frontend-convention](../04-development/03-frontend-convention.md)

## 완료 기록 (2026-11-19)

검증: `scripts/cdp-pan-check.mjs` (CDP 실입력). 기본 스위트(SwiftShader, 1280x720)는 AC5–AC12와 P3-AC7~AC12를 포함해 31개 항목 전부 PASS. 성능표(`--perf-table`)의 P3-AC13 기준도 PASS.

### P3-AC13 성능표
GPU: ANGLE (Apple, ANGLE Metal Renderer: Apple M5), 1920x1080, 줌 기본, 중심 (256,256). 행마다 3 s 대기 후 5 s 표본, 이어서 5 s 연속 drag/zoom으로 long task를 센다.

| citizens | speed | fps avg | calls | triangles | geometries | heap MB | cpu avg ms | cpu max ms | path queue max | path misses avg | long tasks |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | x1 | 44.5 | 48 | 65516 | 25 | 34.4 | 0.02 | 0.10 | 0 | 0.0 | 0 |
| 0 | x16 | 60.0 | 48 | 65516 | 25 | 40.0 | 0.01 | 0.10 | 0 | 0.0 | 0 |
| 100 | x1 | 60.0 | 49 | 65676 | 26 | 51.8 | 0.03 | 0.10 | 0 | 0.0 | 0 |
| 100 | x16 | 60.0 | 49 | 65756 | 26 | 52.0 | 0.05 | 0.60 | 0 | 0.0 | 0 |
| 500 | x1 | 60.0 | 49 | 67196 | 26 | 63.9 | 0.05 | 0.20 | 0 | 0.0 | 0 |
| 500 | x16 | 60.0 | 49 | 67196 | 26 | 64.2 | 0.10 | 0.70 | 0 | 0.4 | 0 |
| 1000 | x1 | 60.0 | 49 | 68996 | 26 | 76.3 | 0.07 | 0.20 | 0 | 0.0 | 0 |
| 1000 | x16 | 60.0 | 49 | 69076 | 26 | 76.7 | 0.18 | 1.50 | 0 | 0.9 | 0 |

1000명 기준: cpu avg 0.07/0.18 ms (< 2 ms), long task 0, calls(1000) − calls(0) = 1 (≤ 2).

### 힙 메모리 확인
성능표의 heap MB가 시민 수를 0 → 100 → 500 → 1000으로 바꿀 때마다 약 12 MB씩 오른 원인을 확인했다(2026-11-19, Chrome for Testing headless, Metal, 1920x1080, dev 서버). 측정은 GC 2회 + 500 ms 후 `Runtime.getHeapUsage`.

| 실험 | 결과 |
|---|---|
| 같은 페이지에서 `setCitizenCount` 1000 → 0을 12회 반복 (0명 시점 heap) | 29.8 → 29.9 → 30.1 → 30.3 → 30.4 → 30.5 MB (사이클 1·2·3·5·8·12). 12회 합계 약 +0.7 MB, 증가 폭 감소(수렴) |
| 같은 반복의 1000명 시점 heap | 29.5 → 31.3 MB, 사이클 10 이후 정체. geometries 25(0명) / 26(1000명)로 고정 |
| 500 ↔ 1000 5회 왕복 후 1000명 | 31.4 MB |
| 같은 페이지에서 0 → 100 → 500 → 1000 → 0 | 30.6 / 30.7 / 31.0 / 31.4 / 30.6 MB (단계당 약 +0.3 MB) |
| 페이지를 `?citizens=n`로 매번 다시 로드(성능표 방식) 0 → 100 → 500 → 1000 → 1000(x16) → 0 | 29.6 / 40.8 / 52.6 / 64.6 / 64.9 / 75.9 MB. 마지막 0명 행도 75.9 MB |

판정: 시민 수 전환에 따른 누수는 없다(0명 heap이 수렴하고 geometries가 늘지 않는다). 성능표의 단계별 +12 MB는 시민 수와 무관하게 같은 탭에서 `Page.navigate`를 반복할 때마다 약 +11~12 MB씩 쌓이는 현상이며, 시민 수 0으로 되돌아간 마지막 행(75.9 MB)이 이를 보여준다. 즉 성능표의 heap 열은 행 순서(재로드 횟수)를 반영하며 시민 수의 비용이 아니다. 이 누적의 정확한 원인(dev 빌드/Vite 클라이언트, 이전 문서 컨텍스트의 잔존 등)은 prod 빌드로 확인하지 않았다.

메모리 구성(코드 기준 추정): `CitizenSystem`은 생성자 기본 인자로 `buildRoadGrid(city)`를 새로 만든다(`roadGrid.ts`: `conn` Uint8Array 512x512 = 0.25 MB, `component` Int32Array = 1 MB, 임시 `stack` 1 MB는 생성 직후 해제). 시민당 SoA 배열과 `slots`/`requested`/인스턴스 버퍼는 1000명 기준 1 MB 미만이고, `PathService.cache`는 최대 2048개 경로로 상한이 있다. 시민 수 변경 시 `CitizenLayer.tsx`의 effect cleanup이 `manager.dispose()`와 `api.system = null`을 호출하므로 이전 `CitizenSystem`, `RoadGrid`, `InstancedMesh`는 GC 대상이 된다(`Runtime.queryObjects`로 사이클 후 `Int32Array`/`Uint8Array`/`Float32Array` 생존 수 0 확인, Map 수는 0명 69개 / 1000명 78개).

후속 과제: 재로드 시 +12 MB 누적의 원인을 prod 빌드(`yarn build` + preview)에서 재측정해 dev 전용 현상인지 확인한다. 성능표의 heap 열은 페이지 재로드 방식에서는 비교 지표로 쓰지 않는다.

### 알려진 한계
- 첫 행(0명, x1)의 fps 44.5는 첫 로드의 셰이더/GPU 워밍업 영향으로 보이며, 이후 행은 60 fps다.
- cpu max는 샘플링(100 ms 간격)한 `cpu.last`의 최댓값이라 실제 최댓값보다 작을 수 있다.
- 시민 id를 열거하는 디버그 훅이 없어 CDP 스크립트는 타일 중심을 클릭 스캔해 시민을 찾는다.
- P3-AC7 off-screen 구간의 비교 오차 기준은 0.05 tile이다(계획 본문의 1e-3보다 완화).
- 성능표는 단일 실행 결과이며 분산을 측정하지 않았다.
