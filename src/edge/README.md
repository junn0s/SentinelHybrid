# src/edge

Jetson 에지 파이프라인 모듈입니다.

## 기능
- 카메라 프레임 캡처/샘플링
- 온디바이스 VLM(Ollama Gemma) 판정
- 위험 시 로컬 경보(LED/사이렌)
- FastAPI로 이벤트 전송 및 서버 응답(TTS/WAV) 재생

## 핵심 파일
- `main.py`: 실행 엔트리포인트
- `orchestrator.py`: 루프/쿨다운/전송/재생 오케스트레이션
- `vlm_client.py`: Ollama 호출 + 위험 판정 가드레일
- `alerts.py`: 경보 컨트롤러 파사드
- `alerts_indicator.py`: LED/사이렌/GPIO 제어
- `alerts_speech.py`: 로컬 TTS/서버 WAV 재생
- `server_client.py`: 서버 POST 및 ACK 파싱
- `config.py`: Edge 환경변수 설정
