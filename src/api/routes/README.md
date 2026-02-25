# src/api/routes

FastAPI 라우팅 계층입니다.

## 파일
- `admin.py`: `/`, `/admin`
- `health.py`: `/health`
- `events.py`: `/events/*` (핵심 이벤트 API)
- `deps.py`: 런타임 DI

## 원칙
- 라우트는 입출력/상태코드 처리에 집중
- 비즈니스 로직은 `services/`로 위임
