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
  - `trigger_signals`: 감지 트리거(관측 신호)
  - `first_60_sec`: 최초 60초 조치
  - `first_5_min`: 최초 5분 조치
  - `immediate_actions`: 즉시 조치 목록
  - `secondary_actions`: 후속 조치 목록
  - `reporting`: 보고 체계
  - `ppe`: 필요 보호구
  - `prohibitions`: 금지사항
  - `escalation_criteria`: 상향/긴급 전환 기준
  - `restart_conditions`: 작업 재개 조건
  - `version`, `updated_at`, `source`
  - `content`: 응답 생성에 사용할 요약 텍스트(없으면 필드에서 합성)

## 작성 기준(권장)
- 각 항목은 실제 현장 지시어 형태(명령형, 단문)로 작성한다.
- `first_60_sec`는 즉시 생명/화재/감전 리스크 차단에 집중한다.
- `first_5_min`은 확산 방지, 외부 신고, 통제선 유지 등 운영 조치에 집중한다.
- `escalation_criteria`에는 “언제 119/비상 대응으로 전환하는지”를 수치/상태 기준으로 명시한다.

## 인제스트 규칙
- 문서는 Chroma에 `index_text()` 결과(구조화 필드 포함)를 임베딩한다.
- 검색 결과 반환 시 `metadata.content`가 있으면 해당 값을 우선 사용한다.
- `tags`, `hazard_type`, `severity`, `version`은 metadata로 함께 저장한다.
