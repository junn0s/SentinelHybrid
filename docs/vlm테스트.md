# Jetson Gemma(VLM) 이미지셋 검증 가이드 (바로 실행용)

## 목적
- 로컬 Edge 판정 품질을 수치로 검증한다.
- 목표: 오탐(FP)율을 낮추고, 정탐(TP)율/지연시간을 함께 확인한다.

---

## 1) 준비 (Jetson)
프로젝트 루트에서 실행:

```bash
cd ~/SentinelHybrid
source sentinelhybrid-venv/bin/activate
```

이미지 폴더 생성:

```bash
mkdir -p data/eval/safe data/eval/danger
```

- `data/eval/safe`: 실제로 안전한 장면 이미지
- `data/eval/danger`: 실제로 위험한 장면 이미지

지원 확장자: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.webp`

---

## 2) 이미지셋 구성안 (1차 권장)

### 최소 권장 수량
- 빠른 1차: `safe 50장 + danger 50장`
- 안정 권장: `safe 100장 + danger 100장`

### `safe` 구성 (오탐 방지용)
- 일반 작업/사무 장면: 30%
- 빨간색 물체가 많은 안전 장면(옷/포스터/화면): 25%
- 밝기/역광/노이즈 있는 안전 장면: 20%
- 사람은 있으나 위험행동 없는 장면: 25%

### `danger` 구성 (정탐 확보용)
- 화재/연기: 30%
- 낙상/전도 위험: 25%
- 무단 접근/위협 행동: 25%
- 전기 이상(스파크/노출선 등): 20%

### 수집 규칙
- 같은 장소/각도 연속샷은 중복 제거
- 근거리/원거리/다양한 조명 조건 섞기
- 파일명 예시:
  - `safe_001.jpg`
  - `danger_fire_012.jpg`
  - `danger_fall_021.jpg`

---

## 3) 평가 실행

기본 실행:

```bash
python3 -m src.sim.eval_vlm_dataset --shuffle --save-json data/eval/result_v1.json
```

옵션 예시:

```bash
# 클래스별 최대 80장만 사용
python3 -m src.sim.eval_vlm_dataset --limit 80 --shuffle --save-json data/eval/result_limit80.json
```

---

## 4) 결과 확인 포인트
스크립트 출력/JSON에서 아래 3개를 우선 확인:

- `fp_rate_percent` (오탐율)
- `tp_rate_percent` (정탐율)
- `avg_latency_ms` (평균 지연시간)

추가로 confusion 값 확인:
- `tp`, `tn`, `fp`, `fn`

---

## 5) 합격 기준(1차)
- 오탐율: `fp_rate_percent <= 5`
- 정탐율: `tp_rate_percent >= 80`
- 지연시간: 이전 측정 대비 급격한 악화 없을 것

---

## 6) 목표 미달 시 튜닝 순서

1. `EDGE_VLM_MIN_DANGER_SCORE` 조정 (`0.70 -> 0.72/0.75`)
2. `EDGE_VLM_DANGER_DOUBLE_CHECK` on/off 비교
3. 분류 프롬프트 문구 미세 조정
4. 동일 이미지셋으로 재측정(전/후 비교)

중요: 매번 다른 데이터셋으로 비교하지 말고, 같은 데이터셋으로 비교해야 개선 여부가 정확하다.

---

## 7) 실행 체크리스트
- [ ] Ollama 서버 실행 상태 확인
- [ ] `gemma3:4b` 모델 로드 확인
- [ ] `data/eval/safe`, `data/eval/danger` 이미지 준비
- [ ] 평가 실행 및 JSON 저장
- [ ] FP/TP/지연시간 기록
- [ ] 환경변수 튜닝 후 재실행/재비교

