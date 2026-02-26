# src/rag

RAG 데이터/유틸리티 영역입니다.

## 파일
- `default_manuals.json`: 기본 안전 매뉴얼 데이터
- `manual_repository.py`: 로컬 로딩/키워드 검색 유틸

## 매뉴얼 스키마(운영형)
- 필수
  - `id`: 문서 고유 식별자
  - `title`: 매뉴얼 제목
- 권장
  - `hazard_type`: `fire|fall|intrusion|electrical|general`
  - `severity`: `low|medium|high|critical`
  - `tags`: 검색 키워드 배열
  - `situation`: 상황 정의
  - `immediate_actions`: 즉시 조치 목록
  - `secondary_actions`: 후속 조치 목록
  - `reporting`: 보고 체계
  - `ppe`: 필요 보호구
  - `prohibitions`: 금지사항
  - `restart_conditions`: 작업 재개 조건
  - `version`, `updated_at`, `source`
  - `content`: 응답 생성에 사용할 요약 텍스트(없으면 필드에서 합성)

## 인제스트 규칙
- 문서는 Chroma에 `index_text()` 결과(구조화 필드 포함)를 임베딩한다.
- 검색 결과 반환 시 `metadata.content`가 있으면 해당 값을 우선 사용한다.
- `tags`, `hazard_type`, `severity`, `version`은 metadata로 함께 저장한다.
