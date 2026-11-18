# Phase 1 — 맵 프로토타입
> 원본: README §12 Phase 1(프로젝트 기반), Phase 2(렌더링 기반)

## 목표
개발 환경과 테스트 기반을 갖추고, Three.js(React Three Fiber)로 지형·도로·건물을 OrthographicCamera 시점에서 렌더링하며 카메라 이동·줌과 타일 선택을 제공한다.

## 작업
- Repository 구성과 개발 환경 설정
- 테스트 기반 구성
- Three.js/R3F 씬 초기화
- 지형·도로·건물 렌더링 (OrthographicCamera)
- 카메라 이동 및 줌
- 타일 선택

## 완료 기준
원본 Phase 1: 세계 상태와 핵심 도메인을 코드로 표현하고 단위 테스트 실행 가능
원본 Phase 2: 도시 맵을 자유롭게 탐색하고 건물을 선택할 수 있음

(재구성) 개발 환경에서 단위 테스트가 실행되고, 도시 맵을 카메라로 자유롭게 탐색하며 타일을 선택할 수 있음

## 참고 문서
- [02-world](../02-domain/02-world.md)
- [04-map-rendering](../03-architecture/04-map-rendering.md)
- [02-tech-stack](../03-architecture/02-tech-stack.md)
