# SentinelHybrid Project Handoff

## 1. 현재 상태 요약
- 기준일: `2026-02-17`
- 저장소: `/Users/junsu/Desktop/프로젝트/Jetson Orin Nano/SentinelHybrid`
- 작업 브랜치: `feat/3-mcp-rag-pipeline`
- 관련 이슈: [#3](https://github.com/junn0s/SentinelHybrid/issues/3)
- 현재 방향: `MCP + RAG` 구조를 유지하면서 안정화

## 2. 지금까지 구현된 기능
### 2.1 Jetson 이벤트 수신 API
- 엔드포인트 `POST /events/danger`에서 위험 이벤트를 수신
- 위험 이벤트(`is_danger=true`)인 경우에만 후속 파이프라인 실행
- 파일: `src/api/main.py`, `src/api/models.py`

### 2.2 RAG 조회 (MCP 우선, 로컬 폴백)
- 1차 조회: MCP 도구(`retrieve_guidelines`) 호출
- 실패/타임아웃 시: 로컬 매뉴얼 검색으로 폴백
- 파일: `src/api/services/mcp_rag.py`, `src/api/services/local_rag.py`, `src/rag/manual_repository.py`

### 2.3 LLM 응답 생성 (구조화 출력)
- 기본 모델: `gemini-3-flash-preview`
- `response_mime_type=application/json` + Pydantic 스키마 검증 적용
- 출력 필드:
  - `operator_response` (관리자용 상세 대응)
  - `jetson_tts_summary` (Jetson 음성용 짧은 문장)
- 파일: `src/api/services/llm_responder.py`, `src/api/models.py`

### 2.4 로그 저장 및 조회
- 이벤트 로그: `data/events/danger_events.jsonl`
- 응답 로그: `data/events/danger_responses.jsonl`
- 조회 엔드포인트:
  - `GET /events/recent`
  - `GET /events/{event_id}/response`
- 파일: `src/api/main.py`

### 2.5 시뮬레이터
- Jetson 없이 위험 이벤트를 반복 전송하는 테스트 스크립트 제공
- 파일: `src/sim/send_mock_danger_event.py`

## 3. 핵심 실행 흐름
1. Jetson(또는 시뮬레이터)이 `/events/danger`로 이벤트 전송
2. API가 이벤트를 저장하고 위험 여부 확인
3. MCP RAG 조회 시도
4. 실패 시 로컬 매뉴얼 검색으로 폴백
5. Gemini 구조화 출력으로 대응 문장 생성
6. 응답/참고 매뉴얼/출처(`mcp` or `local-fallback`) 반환
7. 결과를 JSONL 로그에 누적

## 4. 환경 변수 기준값
- `GOOGLE_API_KEY`: Gemini API 키
- `LLM_PROVIDER=gemini`
- `GEMINI_MODEL=gemini-3-flash-preview`
- `RAG_MCP_ENABLED=true`
- `RAG_MCP_TRANSPORT=streamable_http`
- `RAG_MCP_HOST=127.0.0.1`
- `RAG_MCP_PORT=8765`
- `RAG_MCP_PATH=/mcp`
- `RAG_MCP_AUTOSTART=true`
- `RAG_MCP_COMMAND` 기본값: 현재 파이썬 실행파일
- `RAG_MCP_ARGS` 기본값: `-m src.mcp.rag_server`
- `RAG_MCP_TIMEOUT_SEC=10.0`
- `RAG_TOP_K=3`

## 5. 로컬 실행 방법
```bash
cd "/Users/junsu/Desktop/프로젝트/Jetson Orin Nano/SentinelHybrid"
source sentinelhybrid-venv/bin/activate
pip install -r requirements.txt
export GOOGLE_API_KEY="YOUR_GEMINI_API_KEY"
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

다른 터미널:
```bash
cd "/Users/junsu/Desktop/프로젝트/Jetson Orin Nano/SentinelHybrid"
source sentinelhybrid-venv/bin/activate
python src/sim/send_mock_danger_event.py --count 5 --interval 2 --timeout 12
```

확인 URL:
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/events/recent`
- `http://127.0.0.1:8000/events/<event_id>/response`

## 6. 현재 알려진 이슈
- Gemini 무료 티어 쿼터 초과 시(`429`) LLM 응답이 fallback 템플릿으로 내려감
- MCP 검색은 동작하지만, 참고 매뉴얼 정렬 정확도는 추가 리랭킹이 필요
- 기능상 동작은 유지되지만 응답 품질/일관성 관점에서 개선 필요

## 7. 다음 작업 우선순위
1. MCP 검색 결과 리랭킹 추가
- 위험 유형별 문서 우선순위 강화(전기/화재 등)
2. MCP 실패율/지연시간 지표 로깅 추가
- 응답 품질 저하 원인 추적 가능하도록 메트릭 확보
3. streamable_http 상시 MCP 서버 운영 모니터링
- 포트 점유/프로세스 헬스체크 자동화
4. Jetson 실장비 연동 전 E2E 시뮬레이션 고정 테스트 작성
- 성공률, 평균 지연, fallback 비율 점검

## 8. 문서 자산
- `2-1.md`: 초기 Jetson VLM 파이프라인 구현 요약
- `2-3.md`: FastAPI 서버 + 이벤트 시뮬레이터 구현 요약
- `2-5.md`: MCP RAG + Gemini 구조화 출력 구현 요약

## 9. 협업 규칙
- 브랜치 네이밍:
  - `feat/이슈번호-이슈요약`
  - `fix/이슈번호-이슈요약`
- 커밋 메시지:
  - `feat: ...`
  - `fix: ...`
  - `docs: ...`
  - `chore: ...`
