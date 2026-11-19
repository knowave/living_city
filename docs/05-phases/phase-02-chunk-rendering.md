# Phase 2 — Chunk 렌더링
> 원본: README §12 Phase 2(Chunk Manager, 건물), §11.1

## 목표
Chunk Manager로 맵을 분할 관리하고 건물을 렌더링하며, 큰 맵으로 확장 가능함을 검증한다.

## 작업
- Chunk Manager
- 건물 렌더링
- 확장 검증: 512 × 512 타일 (§11.1)
- 모듈 6종: MapGenerator(시드 결정적 Mock), ChunkManager, VisibilityManager, ChunkRenderer, BuildingRenderer, InstanceManager + DTO 매퍼
- 디버그 HUD (활성 Chunk 수, draw call 등)
- 리소스 누수 점검 (비활성화 시 dispose)

## 완료 기준
원본 Phase 2: 도시 맵을 자유롭게 탐색하고 건물을 선택할 수 있음

- 보이는 Chunk와 1 Chunk 링만 활성화하고, 활성화는 프레임당 최대 8개로 제한한다.
- 건물은 앵커 Chunk에서만 한 번 그려지며 id 중복이 없다.
- 지형·도로가 타일 스키마 v1대로 렌더링되고 알 수 없는 값은 경고 한 번 후 기본값으로 처리된다.
- 카메라 줌이 12~60 범위(기본 20)로 제한된다.
- 카메라를 이동해도 Chunk 비활성화 후 geometry/material 누수가 없다.

(재구성) 건물을 렌더링하고 선택할 수 있으며, 512 × 512 타일 확장 검증을 수행함

## 참고 문서
- [02-world](../02-domain/02-world.md)
- [04-map-rendering](../03-architecture/04-map-rendering.md)
