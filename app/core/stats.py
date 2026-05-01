"""
확률과 통계 분석 엔진 (stats.py)
================================

[프로젝트 핵심 모듈]
이 파일은 본 수행평가의 가장 중요한 부분이다. 고등학교 확률과 통계의
다음 개념들을 코드로 구현한다.

  1. 평균        → calc_mean_std()
  2. 표준편차     → calc_mean_std()
  3. 혼잡 분류    → classify_congestion()
  4. 상대도수 확률 → calc_congestion_probability()
  5. 조건부확률   → calc_conditional_probability()
  6. 독립성 판단  → judge_independence()

각 함수의 docstring에 어떤 확통 개념을 어떻게 구현했는지 적어두었다.
보고서에서 인용하기 좋게 수식 형태도 함께 표시했다.
"""

import pandas as pd
import numpy as np
from typing import Optional


# =============================================================================
# 0. 보조 함수 — 시간대 그룹화와 요일 그룹화
# =============================================================================
def time_group_of(hour: int) -> str:
    """
    시간대(0~23시)를 의미 있는 4개 그룹으로 묶는다.

    표본 수가 적을 때 시간대를 너무 세분화하면 혼잡 확률 추정이
    불안정해진다. 4개 그룹으로 묶으면 표본이 늘어 추정이 안정된다.
    (단, 본 프로젝트에서는 1시간 단위 분석을 기본으로 하고,
     이 함수는 보조용으로만 사용한다.)
    """
    if 7 <= hour <= 9:
        return "출근"
    elif 10 <= hour <= 16:
        return "낮"
    elif 17 <= hour <= 20:
        return "퇴근"
    elif 21 <= hour <= 23:
        return "야간"
    else:
        return "심야"


def weekday_group_of(is_weekend: bool) -> str:
    """평일/주말 이진 분류"""
    return "주말" if is_weekend else "평일"


# =============================================================================
# 1. 평균과 표준편차
# =============================================================================
def calc_mean_std(df: pd.DataFrame,
                  station: str,
                  is_weekend: Optional[bool],
                  hour: Optional[int]) -> dict:
    """
    [확통 개념] 평균(mean)과 표준편차(standard deviation)

    수식:
        평균   m = (1/n) Σ x_i
        분산   s² = (1/(n-1)) Σ (x_i - m)²    ← 표본분산 (자유도 보정)
        표준편차 s = √s²

    [의미]
    - 평균은 "특정 조건(역·요일·시간대)에서 평소 어느 정도 이용되는가"의 기준값.
    - 표준편차는 "같은 조건이라도 날마다 얼마나 달라지는가"의 변동성 지표.
      표준편차가 크면 그 조건은 "어떤 날엔 한산하고 어떤 날엔 매우 붐빔" 의미.

    [반환]
        n      : 표본 개수 (관측 일수)
        mean   : 평균 이용량
        std    : 표준편차
        max    : 최대 이용량
        min    : 최소 이용량
    """
    sub = df[df["station"] == station]
    if is_weekend is not None:
        sub = sub[sub["is_weekend"] == is_weekend]
    if hour is not None:
        sub = sub[sub["hour"] == hour]

    if len(sub) == 0:
        return {"n": 0, "mean": None, "std": None, "max": None, "min": None}

    return {
        "n": int(len(sub)),
        "mean": float(sub["total"].mean()),
        # ddof=1: 표본분산. 고등학교 교과과정과 동일.
        "std": float(sub["total"].std(ddof=1)) if len(sub) > 1 else 0.0,
        "max": int(sub["total"].max()),
        "min": int(sub["total"].min()),
    }


# =============================================================================
# 2. 혼잡 분류 (혼잡 사건의 정의)
# =============================================================================
def classify_congestion(value: float, mean: float, std: float) -> str:
    """
    [확통 개념] 평균과 표준편차를 이용한 혼잡 사건 정의

    분류 기준:
        value < mean              → "보통"
        mean ≤ value < mean + std → "혼잡"
        value ≥ mean + std        → "매우 혼잡"

    [근거]
    정규분포 가정 하에서 mean+1std 이상은 상위 약 16% 영역이다.
    즉 "평균보다 표준편차 1개 이상 높음" = "통상보다 뚜렷이 많음".
    이는 단순히 "평균보다 많다"보다 더 엄격한 기준이며, 통계적으로
    의미 있는 혼잡 상태를 정의한다.

    [반환] "보통" / "혼잡" / "매우 혼잡"
    """
    if std is None or std == 0 or pd.isna(std):
        # 표준편차가 0이면 평균으로만 분류 (예외 처리)
        return "혼잡" if value >= mean else "보통"
    if value < mean:
        return "보통"
    elif value < mean + std:
        return "혼잡"
    else:
        return "매우 혼잡"


def is_congested_binary(value: float, mean: float, std: float = None) -> int:
    """
    혼잡 여부를 이진(0/1)으로 변환.
    조건부확률 계산할 때 사용하기 위함.

    "혼잡" 또는 "매우 혼잡" → 1
    "보통"                  → 0

    [참고]
    이 이진 분류 기준은 "이용량 ≥ 평균"이다. 평균 이상이면 혼잡으로 본다.
    이는 보고서/발표에서 명시할 핵심 정의 중 하나.
    """
    return 1 if value >= mean else 0


def add_congestion_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    데이터프레임 전체에 대해, 각 행이 (역·요일구분·시간) 그룹 안에서
    혼잡인지 아닌지 라벨을 붙인다.

    같은 (역, 평일/주말, 시간대) 조건의 평균을 그룹별로 구한 다음,
    각 행의 이용량이 그 평균 이상인지로 혼잡(1)/비혼잡(0)을 판정한다.

    이 라벨링이 모든 후속 확률 계산의 기반이 된다.
    """
    df = df.copy()
    grouping = ["station", "is_weekend", "hour"]
    df["group_mean"] = df.groupby(grouping)["total"].transform("mean")
    df["group_std"] = df.groupby(grouping)["total"].transform(lambda x: x.std(ddof=1))
    df["congested"] = (df["total"] >= df["group_mean"]).astype(int)

    # 3단계 등급도 함께
    def _grade(row):
        return classify_congestion(row["total"], row["group_mean"], row["group_std"])
    df["grade"] = df.apply(_grade, axis=1)
    return df


# =============================================================================
# 3. 상대도수 기반 혼잡 확률
# =============================================================================
def calc_congestion_probability(df: pd.DataFrame,
                                station: str,
                                is_weekend: Optional[bool],
                                hour: Optional[int]) -> dict:
    """
    [확통 개념] 상대도수 기반 확률 (= 통계적 확률)

    수식:
        P(혼잡) ≈ (혼잡한 날의 수) / (전체 관측일 수)

    [중요 — 보고서 포인트]
    이 값은 이론적 확률이 아니라 "수많은 관측에서 나타난 상대도수"이다.
    표본 크기 n이 클수록 진짜 확률에 가까워진다 (큰 수의 법칙).
    표본이 너무 작으면 신뢰도가 낮으므로 경고를 함께 표시한다.

    [반환]
        n      : 관측 일수
        n_cong : 혼잡으로 분류된 일수
        prob   : 상대도수 = n_cong / n
        warn   : 표본 부족 경고 (n < 10)
    """
    sub = df[df["station"] == station]
    if is_weekend is not None:
        sub = sub[sub["is_weekend"] == is_weekend]
    if hour is not None:
        sub = sub[sub["hour"] == hour]

    if "congested" not in sub.columns:
        # 라벨링 안 된 경우, 즉석으로 평균 기준 적용
        if len(sub) == 0:
            return {"n": 0, "n_cong": 0, "prob": None, "warn": True}
        m = sub["total"].mean()
        n_cong = int((sub["total"] >= m).sum())
    else:
        n_cong = int(sub["congested"].sum())

    n = int(len(sub))
    prob = n_cong / n if n > 0 else None
    return {
        "n": n,
        "n_cong": n_cong,
        "prob": prob,
        "warn": n < 10,
    }


# =============================================================================
# 4. 조건부확률 (프로젝트의 핵심 개념)
# =============================================================================
def calc_conditional_probability(df: pd.DataFrame,
                                 station_a: str,
                                 station_b: str,
                                 is_weekend: Optional[bool],
                                 hour: Optional[int]) -> dict:
    """
    [확통 개념] 조건부확률 P(B|A)

    수식:
        P(B|A) = P(A ∩ B) / P(A)
              = (A와 B가 동시에 일어난 횟수) / (A가 일어난 횟수)

    [본 프로젝트에서의 의미]
        A = "특정 조건에서 station_a가 혼잡한 사건"
        B = "같은 조건에서 station_b가 혼잡한 사건"
        같은 날, 같은 시간대를 기준으로 두 사건이 함께 발생했는지를 본다.

    [구현 절차]
        1) 두 역에 대해 같은 조건(요일구분·시간대)으로 데이터를 추출
        2) 날짜를 기준으로 두 역을 매칭 (한 행 = 한 날의 두 역 상태)
        3) station_a가 혼잡인 날만 추려서, 그 안에서 station_b도 혼잡인 비율 계산

    [반환]
        n_a       : A 사건이 발생한 횟수 (조건부확률의 분모)
        n_a_and_b : A와 B가 동시에 발생한 횟수 (분자)
        p_b_given_a : 조건부확률 P(B|A)
        warn      : 표본 부족 경고
    """
    # 두 역의 (요일구분·시간대) 조건이 같은 데이터 추출
    def _filter(station):
        sub = df[df["station"] == station]
        if is_weekend is not None:
            sub = sub[sub["is_weekend"] == is_weekend]
        if hour is not None:
            sub = sub[sub["hour"] == hour]
        return sub[["date", "congested"]]

    a = _filter(station_a)
    b = _filter(station_b)
    if len(a) == 0 or len(b) == 0:
        return {"n_a": 0, "n_a_and_b": 0, "p_b_given_a": None, "warn": True}

    # 같은 날짜로 매칭
    merged = a.merge(b, on="date", suffixes=("_a", "_b"))
    n_a = int((merged["congested_a"] == 1).sum())
    n_a_and_b = int(((merged["congested_a"] == 1) & (merged["congested_b"] == 1)).sum())

    p_b_given_a = (n_a_and_b / n_a) if n_a > 0 else None
    return {
        "n_a": n_a,
        "n_a_and_b": n_a_and_b,
        "p_b_given_a": p_b_given_a,
        "warn": n_a < 10,
    }


# =============================================================================
# 5. 독립성 판단
# =============================================================================
def judge_independence(p_b: float, p_b_given_a: float, threshold: float = 0.05) -> dict:
    """
    [확통 개념] 사건의 독립성

    이론:
        두 사건 A, B가 독립이면 다음이 성립:
            P(B|A) = P(B)        (식 1)
            또는 동치로
            P(A ∩ B) = P(A) × P(B)  (식 2)

        따라서 |P(B|A) - P(B)|가 0에 가까우면 독립에 가깝다고 본다.
        이 값이 충분히 크면 독립이라고 보기 어렵다.

    [본 프로젝트의 해석 기준]
        diff = P(B|A) - P(B)

        diff > +threshold (예: +0.05) → 양의 연관 (A가 일어나면 B도 더 잘 일어남)
        diff < -threshold             → 음의 연관 (A가 일어나면 B는 덜 일어남)
        |diff| ≤ threshold            → 독립에 가까움

    [주의 — 과장 금지]
    이 분석은 "통계적 연관성"을 보여줄 뿐, "인과관계"를 증명하지 않는다.
    A가 B를 유발한다는 결론은 절대 내릴 수 없다. 보고서 표현은
    "독립적이라고 보기 어렵다", "연관 가능성이 있다" 등으로 신중하게.

    [반환]
        diff       : P(B|A) - P(B)
        verdict    : "독립에 가까움" / "양의 연관" / "음의 연관" / "판단 불가"
        explanation: 사람이 읽을 수 있는 해석 문장
    """
    if p_b is None or p_b_given_a is None:
        return {"diff": None, "verdict": "판단 불가", "explanation": "데이터 부족으로 판단할 수 없습니다."}

    diff = p_b_given_a - p_b
    if abs(diff) <= threshold:
        verdict = "독립에 가까움"
        expl = (f"P(B|A)={p_b_given_a:.3f}, P(B)={p_b:.3f}로 차이가 {diff:+.3f}에 불과합니다. "
                f"두 사건은 독립에 가깝다고 볼 수 있습니다.")
    elif diff > threshold:
        verdict = "양의 연관"
        expl = (f"P(B|A)={p_b_given_a:.3f}이 P(B)={p_b:.3f}보다 {diff:+.3f}만큼 높습니다. "
                f"A 사건이 일어나면 B 사건도 함께 일어나는 경향이 있어, 두 사건이 독립이라고 보기 어렵습니다.")
    else:
        verdict = "음의 연관"
        expl = (f"P(B|A)={p_b_given_a:.3f}이 P(B)={p_b:.3f}보다 {diff:+.3f}만큼 낮습니다. "
                f"A 사건이 일어나면 B 사건은 오히려 덜 일어나는 경향이 있습니다.")
    return {"diff": diff, "verdict": verdict, "explanation": expl}
