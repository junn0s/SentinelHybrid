# src/api

클라우드 측 FastAPI 애플리케이션 영역입니다.

## 책임
- 위험 이벤트 수신 API 제공
- RAG + LLM + TTS 파이프라인 실행
- MCP Ops(Discord) 전파
- 관리자 대시보드 서빙

## 핵심 파일
- `main.py`: 앱 팩토리/런타임 조립
- `config.py`: API 환경변수 설정(pydantic-settings)
- `models.py`: API 계약 모델(Pydantic)
- `routes/`: 엔드포인트 분리
- `services/`: 파이프라인/연동 로직
- `repositories/`: 이벤트/응답 저장소
