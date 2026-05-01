"""
결과 해석 자동 생성기 (interpreter.py)
======================================

분석 결과(평균·표준편차·확률·조건부확률 등)를 받아서, 사람이 읽을 수 있는
한국어 해석 문장을 자동으로 만든다.

[설계 원칙 — 과장 금지]
이 프로젝트는 통계적 연관성만을 다루므로, 인과관계로 오해될 수 있는
표현을 사용하면 안 된다. 다음 규칙을 코드 내부에서 강제한다.

  ■ 금지 표현 (절대 출력에 포함되면 안 됨)
    - "유발했다", "초래했다", "원인이다"
    - "전염되었다", "옮겨갔다"
    - "확실하다", "분명히 ~할 것이다"

  ■ 권장 표현
    - "~한 경향이 있다"
    - "~할 가능성이 높게 나타났다"
    - "통계적으로 연관 가능성이 있다"
    - "독립적이라고 보기 어렵다"

이 규칙은 generate_*() 함수의 마지막에서 _sanitize() 검사를 통과한
문장만 반환하도록 구현되어 있다.
"""

from typing import Optional


# 절대 출력 금지 어휘
_FORBIDDEN_WORDS = [
    "유발", "초래", "원인이다", "원인이 된다",
    "전염되었", "옮겨갔", "옮겨간다",
    "확실히", "분명히 ~", "반드시 ~할",
]


def _sanitize(sentence: str) -> str:
    """
    생성된 문장에서 금지 표현이 있는지 마지막으로 검사.
    있으면 RuntimeError로 빠르게 실패시킨다 (개발 단계 디버깅 목적).
    프로덕션에서는 경고만 띄우는 형태로 바꿀 수 있음.
    """
    for w in _FORBIDDEN_WORDS:
        if w in sentence:
            # 학생 본인 코드 점검을 위해 명시적으로 실패시킴
            raise RuntimeError(
                f"[interpreter 안전장치] 금지된 표현 '{w}'이(가) 결과에 포함되었습니다. "
                f"문장을 다시 검토하세요. 문장: {sentence!r}"
            )
    return sentence


# =============================================================================
# 1. 기본 통계 해석
# =============================================================================
def describe_basic_stats(station: str,
                          weekday_label: str,
                          hour: int,
                          stats_result: dict) -> str:
    """
    평균·표준편차·관측수에 대한 한국어 해석.
    stats_result는 stats.calc_mean_std()의 반환 dict.
    """
    n, m, s = stats_result["n"], stats_result["mean"], stats_result["std"]
    if n == 0 or m is None:
        return _sanitize(f"{station}역 {weekday_label} {hour}시에 해당하는 데이터가 없습니다.")

    sentence = (
        f"{station}역 {weekday_label} {hour}시의 평균 이용량은 약 {m:,.0f}명, "
        f"표준편차는 약 {s:,.0f}명이다 (관측 일수 n = {n}일)."
    )
    if n < 10:
        sentence += " 다만 표본 수가 적어 결과의 신뢰도는 제한적이다."
    return _sanitize(sentence)


# =============================================================================
# 2. 혼잡 확률 해석
# =============================================================================
def describe_probability(station: str,
                          weekday_label: str,
                          hour: int,
                          prob_result: dict) -> str:
    """상대도수 기반 혼잡 확률 해석"""
    n, p = prob_result["n"], prob_result["prob"]
    if p is None:
        return _sanitize("혼잡 확률을 계산할 수 있는 데이터가 부족하다.")

    pct = p * 100
    if pct >= 70:
        level = "높은"
    elif pct >= 40:
        level = "중간 수준의"
    else:
        level = "낮은"

    sentence = (
        f"이 조건에서 {station}역의 혼잡 확률(상대도수)은 약 {pct:.1f}%로, "
        f"{level} 혼잡 빈도가 나타났다."
    )
    if prob_result.get("warn"):
        sentence += " (표본 수가 부족해 추정의 변동성이 클 수 있다.)"
    return _sanitize(sentence)


# =============================================================================
# 3. 조건부확률 + 독립성 해석 (이 프로젝트의 클라이맥스)
# =============================================================================
def describe_conditional(station_a: str,
                          station_b: str,
                          p_b: float,
                          p_b_given_a: float,
                          independence_result: dict) -> str:
    """
    P(B), P(B|A), 독립성 판정 결과를 받아서 종합 해석 문장을 만든다.
    가장 신중하게 표현해야 하는 부분.
    """
    if p_b is None or p_b_given_a is None:
        return _sanitize("두 역의 조건부확률을 계산할 수 있는 데이터가 부족하다.")

    diff = independence_result["diff"]
    verdict = independence_result["verdict"]

    base = (
        f"{station_b}역의 평소 혼잡 확률 P({station_b} 혼잡)은 약 {p_b*100:.1f}%이지만, "
        f"{station_a}역이 혼잡한 경우의 조건부확률 "
        f"P({station_b} 혼잡 | {station_a} 혼잡)은 약 {p_b_given_a*100:.1f}%로 나타났다."
    )

    if verdict == "양의 연관":
        tail = (
            f" 두 값의 차이는 {diff:+.3f}로, {station_a}역이 혼잡할 때 {station_b}역도 "
            f"혼잡할 가능성이 평소보다 높게 나타나는 경향을 보인다. "
            f"따라서 두 역의 혼잡 사건이 독립적이라고 보기 어렵다."
        )
    elif verdict == "음의 연관":
        tail = (
            f" 두 값의 차이는 {diff:+.3f}로, {station_a}역이 혼잡할 때 오히려 "
            f"{station_b}역의 혼잡 가능성이 평소보다 낮게 나타나는 경향을 보인다."
        )
    else:  # 독립에 가까움
        tail = (
            f" 두 값의 차이는 {diff:+.3f}로 작아, 두 사건은 독립에 가깝다고 볼 수 있다."
        )
    return _sanitize(base + tail)


# =============================================================================
# 4. 종합 해석 (웹 결과 페이지 최상단에 보일 한 문단)
# =============================================================================
def make_summary(station: str,
                  weekday_label: str,
                  hour: int,
                  stats_result: dict,
                  prob_result: dict,
                  ai_result: Optional[dict] = None,
                  conditional_blocks: Optional[list] = None) -> str:
    """
    여러 분석 결과를 모아서 한 문단의 종합 해석을 만든다.

    인자:
        conditional_blocks : list of dict
            각 원소: {"neighbor": 역명, "p_b": float, "p_b_given_a": float,
                       "independence": independence_result_dict}
    """
    parts = []
    # 기초 통계
    if stats_result["n"] > 0:
        parts.append(describe_basic_stats(station, weekday_label, hour, stats_result))
    # 혼잡 확률
    if prob_result.get("prob") is not None:
        parts.append(describe_probability(station, weekday_label, hour, prob_result))
    # AI 보조 결과 (있으면)
    if ai_result and ai_result.get("congested_prob") is not None:
        ai_pct = ai_result["congested_prob"] * 100
        parts.append(
            f"AI 보조 모델(의사결정나무)은 같은 조건에서 혼잡 확률을 약 {ai_pct:.1f}%로 예측했다. "
            f"이 값은 통계 기반 결과를 보조적으로 검증하는 용도이다."
        )
    # 조건부확률 블록들
    if conditional_blocks:
        for blk in conditional_blocks:
            sentence = describe_conditional(
                station,
                blk["neighbor"],
                blk["p_b"],
                blk["p_b_given_a"],
                blk["independence"],
            )
            parts.append(sentence)

    summary = " ".join(parts)
    return _sanitize(summary)
