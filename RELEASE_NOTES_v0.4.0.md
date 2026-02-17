# SentinelHybrid Release Notes

## Version
v0.4.0

## Date
2026-02-17

## Highlights
- 관리자 대시보드(`/admin`) 추가 및 이벤트/응답 가시화
- 위험 시나리오 시뮬레이터 고도화(`mixed/fire/fall/intrusion/electrical`)
- Gemini 구조화 출력 스키마 강화 + fallback 지침 품질 개선
- MCP RAG 안정화(`streamable_http`, timeout 10s)
- 임베딩 기반 검색 적용(`intfloat/multilingual-e5-small`)

## Added
- `/admin` UI (HTML/CSS/JS)
- 이벤트 상세 패널(상황요약/운영자 대응/Jetson TTS/참조 매뉴얼)
- 시나리오별 샘플 이벤트 생성 및 전송 옵션

## Changed
- MCP transport 기본값을 `streamable_http`로 전환
- RAG timeout 기본값을 10초로 상향
- Chroma 검색을 sentence-transformers 임베딩 기반으로 개선
- README를 실제 코드 구조/실행 순서 기준으로 재정리

## Fixed
- Gemini 실패/쿼터 초과 시 fallback 응답 품질 개선
- 위험 유형별 지침 문장 구체화(운영자 대응/Jetson TTS)

## Operational Notes
- Gemini free tier 초과 시 `429 RESOURCE_EXHAUSTED`가 발생할 수 있습니다.
- 이 경우에도 API는 fallback 템플릿으로 응답을 유지합니다.

## Included Branch Work
- `feat/3-mcp-rag-pipeline`
- `feat/4-admin-dashboard`
- `feat/7-mcp-embedding-stabilization`
