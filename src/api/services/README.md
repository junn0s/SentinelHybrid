# src/api/services

API 비즈니스 로직 계층입니다.

## 주요 모듈
- `pipeline.py`: 위험 이벤트 처리 오케스트레이션
- `llm_responder.py`: LLM 구조화 응답 + fallback 템플릿
- `gemini_tts.py`: 서버 측 LLM TTS WAV(Base64) 생성
- `mcp_rag.py`: MCP RAG 조회
- `mcp_discord.py`: MCP Discord 전파
- `local_rag.py`: 로컬 fallback 검색
- `hazard_context.py`: 위험 유형 힌트/리랭킹

## 원칙
- 외부 연동(MCP/LLM/TTS)은 서비스 단에서 캡슐화
- 라우터/저장소와 역할 분리 유지
