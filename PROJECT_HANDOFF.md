# SentinelHybrid Handoff

## 프로젝트 경로
- `/Users/junsu/Desktop/프로젝트/Jetson Orin Nano/SentinelHybrid`

## 현재 브랜치
- `feat/2-jetson-hazard-pipeline`

## 목표
- Jetson에서 올라온 위험 상황 텍스트를 FastAPI 서버가 받아,
- RAG 기반 대응 가이드를 생성하고,
- 관리자용 응답 + Jetson TTS 요약을 반환하는 파이프라인 완성.

## 현재 구현 상태
### 구현된 파일
- `src/api/main.py`
- `src/api/config.py`
- `src/api/models.py`
- `src/api/services/pipeline.py`
- `src/api/services/local_rag.py`
- `src/api/services/mcp_rag.py`
- `src/api/services/llm_responder.py`
- `src/mcp/rag_server.py`
- `src/rag/default_manuals.json`
- `src/sim/send_mock_danger_event.py`

### 동작 확인
- `/events/danger` 수신 동작.
- `/events/recent` 조회 동작.
- Gemini 응답 생성 동작.
- `rag_source`가 `mcp` 또는 `local-fallback`로 기록됨.

### 현재 문제
- stdio FastMCP가 요청마다 재시작되는 로그 반복.
- 간헐적 `read timeout` 발생.
- MCP 경로가 불안정.

## 다음 작업 우선순위
1. MCP를 계속 사용한다(비활성화하지 않음).
2. stdio MCP 재기동/타임아웃을 줄이도록 연결 재사용 안정화.
3. 필요 시 streamable_http 기반 상시 MCP 서버로 전환하되, 현재는 stdio 경로를 유지한다.
4. FastAPI -> RAG(MCP) -> Gemini structured output -> Jetson TTS 응답 경로를 계속 고도화한다.

## 규칙
### 커밋 메시지
- 영어 + conventional prefix
  - `feat: ...`
  - `fix: ...`
  - `chore: ...`

### 브랜치 규칙
- `feat/이슈번호-이슈이름요약`
- `fix/이슈번호-이슈이름요약`

## 후속 요청 템플릿
- MCP를 유지한 상태에서 타임아웃과 재기동 문제를 완화하는 수정부터 진행.
- 테스트 커맨드까지 함께 정리.
