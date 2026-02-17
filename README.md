# SentinelHybrid

Jetson Orin Nano(Edge) + FastAPI/LLM(Cloud) 기반의 실시간 위험 대응 파이프라인입니다.

## 현재 구현 범위
- Edge 루프(`src/edge/main.py`)
  - 카메라 프레임 주기 분석
  - 위험 감지 시 로컬 알림(LED/사이렌 시뮬레이션)
  - 위험 이벤트를 서버로 전송
- API 서버(`src/api/main.py`)
  - `/events/danger` 수신, 최근 이벤트/응답 메모리 보관
  - Gemini 구조화 출력 + RAG 매뉴얼 기반 대응문 생성
  - 관리자 대시보드(`/admin`) 제공
- RAG/MCP(`src/mcp/rag_server.py`)
  - FastMCP 툴 `retrieve_guidelines`
  - Chroma + sentence-transformers 임베딩 검색
  - 실패 시 키워드 fallback 검색
- 시뮬레이터(`src/sim/send_mock_danger_event.py`)
  - `mixed/fire/fall/intrusion/electrical` 시나리오 전송

## 아키텍처
<p align="center">
  <img src="./pipeline.png" alt="SentinelHybrid Pipeline" width="980" />
</p>

## 디렉토리 구조(실제 기준)
```text
SentinelHybrid/
├── README.md
├── RELEASE_NOTES_v0.4.0.md
├── .env.example
├── requirements.txt
├── pipeline.png
├── data/
│   └── events/                      # danger_events.jsonl, danger_responses.jsonl
└── src/
    ├── api/
    │   ├── main.py                  # FastAPI 진입점
    │   ├── config.py                # API 환경변수 로딩
    │   ├── models.py                # Pydantic 모델
    │   ├── services/
    │   │   ├── pipeline.py          # MCP/Local RAG + LLM 응답 파이프라인
    │   │   ├── mcp_rag.py           # MCP retriever
    │   │   ├── local_rag.py         # 로컬 fallback retriever
    │   │   └── llm_responder.py     # Gemini 구조화 출력 + fallback 템플릿
    │   └── static/admin/            # 관리자 대시보드 (HTML/CSS/JS)
    ├── edge/
    │   ├── main.py                  # Jetson/로컬 추론 루프
    │   ├── vlm_client.py            # 임시 VLM/휴리스틱 분석
    │   ├── alerts.py                # LED/사이렌 제어(현재 시뮬레이션 중심)
    │   ├── server_client.py         # API 이벤트 전송
    │   └── config.py                # Edge 환경변수
    ├── mcp/
    │   └── rag_server.py            # FastMCP RAG 서버
    ├── rag/
    │   ├── default_manuals.json     # 기본 안전 매뉴얼
    │   └── manual_repository.py     # 로드/검색 유틸
    └── sim/
        └── send_mock_danger_event.py
```

## 빠른 실행
### 1) 환경 준비
```bash
uv sync
cp .env.example .env
# .env에서 GOOGLE_API_KEY 설정
```

### 2) MCP RAG 서버 실행 (터미널 1)
```bash
SENTINEL_MCP_TRANSPORT=streamable-http \
SENTINEL_MCP_HOST=127.0.0.1 \
SENTINEL_MCP_PORT=8765 \
SENTINEL_MCP_PATH=/mcp \
python -m src.mcp.rag_server
```

### 3) FastAPI 실행 (터미널 2)
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

### 4) 시뮬레이터 테스트 (터미널 3)
```bash
python src/sim/send_mock_danger_event.py --count 5 --interval 2 --scenario mixed
```

### 5) 대시보드 확인
- [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin)
- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## 주요 API
- `GET /health`
- `GET /events/recent`
- `GET /events/{event_id}/response`
- `POST /events/danger`

## 환경 변수 핵심
`.env.example` 기준 주요 항목:
- `GOOGLE_API_KEY`, `GEMINI_MODEL`
- `RAG_MCP_TRANSPORT`, `RAG_MCP_HOST`, `RAG_MCP_PORT`, `RAG_MCP_PATH`
- `RAG_MCP_TIMEOUT_SEC`, `RAG_TOP_K`
- `RAG_CHROMA_PATH`, `RAG_CHROMA_COLLECTION`
- `RAG_EMBEDDING_MODEL`, `RAG_EMBEDDING_DEVICE`

## 참고
- Gemini 무료 티어 제한 시 `429 RESOURCE_EXHAUSTED`가 발생할 수 있으며,
  이 경우 서버는 fallback 템플릿 응답으로 계속 동작합니다.
