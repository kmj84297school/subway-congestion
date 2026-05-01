# 지하철 혼잡 예측 웹 모델

> **고등학교 확률과 통계 수행평가**
> 주제: *지하철 혼잡은 전염되는가? — 서울 지하철 승하차 데이터를 활용한 혼잡 확률 예측 웹 모델*

---

## 1. 프로젝트 개요

서울 지하철의 시간대별 승하차 데이터를 바탕으로, 사용자가 **역 · 요일 · 시간대**를 입력하면 다음을 분석해주는 웹 모델이다.

- 평균 이용량, 표준편차
- 상대도수 기반 혼잡 확률 P(혼잡)
- 인접 역과의 조건부확률 P(B 혼잡 | A 혼잡)
- 두 사건의 독립성 판단
- AI 보조 예측 (의사결정나무)
- 자연어 해석 문장과 4종의 시각화

본 프로젝트의 **중심은 확률 · 통계 분석**이고, AI와 웹은 분석 결과를 더 잘 보여주기 위한 보조 도구로만 사용한다.

---

## 2. 실행 방법

### 2-1. 사전 준비

- Python 3.10 이상
- 가상환경 권장

```bash
# 1) 의존 패키지 설치
pip install -r requirements.txt

# 2) 샘플 데이터 생성 (이미 data/subway_sample.csv 가 있다면 생략)
python data/generate_sample.py

# 3) 웹 서버 실행
uvicorn app.main:app --reload
```

브라우저에서 **http://127.0.0.1:8000** 접속.

### 2-2. 사용

1. 메인 페이지에서 **역 / 평일·주말 / 시간대**를 선택
2. "분석 실행" 클릭
3. 결과 페이지에서 통계 요약, 조건부확률 표, 그래프 4종을 확인

---

## 3. 프로젝트 구조

```
subway_project/
├── app/
│   ├── main.py              ← FastAPI 앱 (엔드포인트)
│   ├── core/
│   │   ├── adjacency.py     ← 인접 역 그래프
│   │   ├── stats.py         ← 핵심: 평균·표준편차·확률·조건부확률·독립성
│   │   ├── model.py         ← AI 보조 모델 (의사결정나무)
│   │   ├── interpreter.py   ← 결과 해석 자동 생성 (과장 금지 안전장치 내장)
│   │   └── visualizer.py    ← 그래프 4종 (matplotlib → base64 PNG)
│   ├── templates/
│   │   ├── index.html       ← 입력 폼
│   │   └── result.html      ← 결과 페이지
│   └── static/
│       └── style.css
├── data/
│   ├── generate_sample.py   ← 가상 샘플 데이터 생성기
│   ├── verify_sample.py     ← 데이터 품질 검증
│   └── subway_sample.csv    ← 샘플 데이터 (60일 × 15역)
├── test_*.py                ← 단위/통합 테스트
├── requirements.txt
├── README.md                ← 본 문서
└── REPORT.md                ← 수행평가 보고서 본문
```

---

## 4. 실제 서울시 공개 데이터로 교체하기

샘플 데이터는 가상이지만, 본 코드는 **서울시 열린데이터광장**의 실제 지하철 데이터로 바로 교체 가능하다.

### 4-1. 데이터 출처
- 서울 열린데이터광장: https://data.seoul.go.kr
  → 검색어 "지하철 시간대별 승하차"
- 공공데이터포털: https://www.data.go.kr

### 4-2. 필요한 컬럼

`data/subway_sample.csv` 의 컬럼명에 맞춰주면 된다:

| 컬럼명 | 의미 | 예시 |
|---|---|---|
| `date` | 날짜 (YYYY-MM-DD) | 2025-09-01 |
| `weekday` | 요일 (월~일) | 월 |
| `is_weekend` | 주말 여부 (True/False) | False |
| `line` | 호선 | 2호선 |
| `station` | 역명 | 강남 |
| `hour` | 시간대 (0~23) | 18 |
| `boarding` | 승차 인원 | 12450 |
| `alighting` | 하차 인원 | 11320 |
| `total` | 이용량 (= boarding + alighting) | 23770 |

### 4-3. 컬럼명이 다를 때

서울시 데이터는 보통 다음과 같은 컬럼을 가진다:
- `사용월` 또는 `사용일자`, `호선명`, `지하철역`, `06시-07시 승차인원`, …

이런 wide format 데이터를 위 long format으로 변환하는 전처리 스크립트를 작성하면 된다. 핵심은 **`date / station / hour / boarding / alighting / total / is_weekend`** 컬럼만 만들어주면 나머지 코드는 그대로 동작한다.

### 4-4. 인접 역 정보 추가

본 샘플은 2호선 일부 역(강남 라인, 홍대 라인, 잠실 라인 등 15개)만 다룬다. 다른 노선/역을 추가하려면 `app/core/adjacency.py` 의 두 딕셔너리에 추가:

```python
STATIONS = {
    ...
    "신논현": {"line": "9호선", "base": 14000, "type": "office"},
}
ADJACENCY = {
    ...
    "신논현": ["언주", "강남"],  # 인접한 역들
}
```

`validate_graph()` 가 양방향성을 자동 검증한다.

---

## 5. 테스트 스크립트

각 모듈이 잘 작동하는지 확인할 수 있는 테스트가 포함되어 있다.

```bash
python test_stats.py          # 통계 엔진 단독 테스트 (강남 평일 18시 시나리오)
python test_scenarios.py      # 5개 시나리오에서 인접 vs 비인접 패턴 검증
python test_model.py          # AI 보조 모델 학습 및 예측
python test_pipeline.py       # 백엔드 전체 파이프라인 (해석 문장까지)
python test_web_simulation.py # FastAPI 없이도 응답 HTML 시뮬레이션
```

---

## 6. 기술적 주의사항

### 6-1. 한글 폰트
matplotlib 그래프의 한글이 깨질 수 있다. `app/core/visualizer.py` 의 `_setup_korean_font()` 가 OS별로 자동 폴백하지만, 폰트가 정말 없는 환경(예: 일부 리눅스 도커)에서는 한글이 □ 로 표시될 수 있다.

해결법:
- Linux: `sudo apt install fonts-nanum` 또는 `fonts-noto-cjk`
- Windows / macOS: 보통 기본 한글 폰트로 자동 매칭됨

### 6-2. 데이터 부족 처리
표본이 10일 미만인 조건은 결과 페이지 상단에 경고가 표시된다. 신뢰도가 낮으니 발표 시 해석에 주의.

---

## 7. 라이선스 / 저작권 안내

- 코드: 본인 학습 목적의 수행평가용
- 가상 샘플 데이터: 본 프로젝트에서 통계적 시연을 위해 생성 (실제 데이터 아님)
- 실제 사용 시: 서울 열린데이터광장의 라이선스(공공누리 4유형 등) 준수
