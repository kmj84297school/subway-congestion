"""
통계 엔진 종합 테스트
=====================
발표 시나리오 그대로: "강남역, 평일, 18시"를 분석하고 보고서 그대로
숫자가 나오는지 확인한다.
"""
import sys
sys.path.insert(0, "/home/claude/subway_project")

import pandas as pd
from app.core.stats import (
    calc_mean_std,
    calc_congestion_probability,
    calc_conditional_probability,
    judge_independence,
    add_congestion_columns,
    classify_congestion,
)

# 1. 데이터 로드 & 혼잡 라벨링
df = pd.read_csv("/home/claude/subway_project/data/subway_sample.csv")
df = add_congestion_columns(df)
print("[1] 데이터 로드 완료. 행 수:", len(df))

# 2. 시나리오: 강남역 평일 18시
print("\n" + "=" * 65)
print("시나리오: 강남역, 평일, 18시")
print("=" * 65)

stats = calc_mean_std(df, station="강남", is_weekend=False, hour=18)
print(f"\n[평균과 표준편차]")
print(f"  관측 일수 n   = {stats['n']}")
print(f"  평균 이용량 m = {stats['mean']:,.0f} 명")
print(f"  표준편차 s    = {stats['std']:,.0f} 명")
print(f"  최대          = {stats['max']:,} 명")
print(f"  최소          = {stats['min']:,} 명")

# 어떤 가상의 관측값에 대한 등급 분류 데모
demo_value = stats['mean'] + 0.5 * stats['std']
grade = classify_congestion(demo_value, stats['mean'], stats['std'])
print(f"\n[혼잡 등급 분류 예시]")
print(f"  만약 오늘 이용량이 {demo_value:,.0f}명이라면 → '{grade}' 등급")

# 3. 혼잡 확률
prob = calc_congestion_probability(df, "강남", False, 18)
print(f"\n[혼잡 확률 (상대도수 기반)]")
print(f"  60일 중 혼잡으로 분류된 일수 = {prob['n_cong']} / {prob['n']}")
print(f"  P(강남 혼잡 | 평일 18시)     = {prob['prob']:.3f}  (= {prob['prob']*100:.1f}%)")

# 4. 조건부확률: 강남 혼잡 → 역삼 혼잡
print(f"\n[조건부확률 — 강남이 혼잡할 때 역삼도 혼잡할 확률]")
cond = calc_conditional_probability(df, "강남", "역삼", False, 18)
print(f"  강남 혼잡일 수 (분모)              = {cond['n_a']}")
print(f"  강남·역삼 모두 혼잡일 수 (분자)     = {cond['n_a_and_b']}")
print(f"  P(역삼 혼잡 | 강남 혼잡)           = {cond['p_b_given_a']:.3f}")

# 역삼의 평소 혼잡 확률
prob_y = calc_congestion_probability(df, "역삼", False, 18)
print(f"  P(역삼 혼잡)         (평소)        = {prob_y['prob']:.3f}")

# 5. 독립성 판단
print(f"\n[독립성 판단]")
ind = judge_independence(prob_y["prob"], cond["p_b_given_a"])
print(f"  diff = P(B|A) - P(B) = {ind['diff']:+.3f}")
print(f"  판정: {ind['verdict']}")
print(f"  → {ind['explanation']}")

# 6. 인접 역 종합 비교
print("\n" + "=" * 65)
print("강남역 인접 역 vs 비인접 역 비교 (평일 18시 기준)")
print("=" * 65)
for neighbor in ["교대", "역삼", "선릉", "삼성", "홍대입구", "잠실"]:
    cond_n = calc_conditional_probability(df, "강남", neighbor, False, 18)
    prob_n = calc_congestion_probability(df, neighbor, False, 18)
    if cond_n['p_b_given_a'] is None or prob_n['prob'] is None:
        continue
    diff = cond_n['p_b_given_a'] - prob_n['prob']
    is_neighbor = neighbor in ["교대", "역삼"]
    flag = "★인접" if is_neighbor else "  비인접"
    print(f"  {flag}  {neighbor:8s}  P(B)={prob_n['prob']:.3f}  "
          f"P(B|A)={cond_n['p_b_given_a']:.3f}  diff={diff:+.3f}")

print("\n[해석 포인트] 인접한 교대·역삼이 다른 역들보다 diff가 크게 나오면,")
print("              '혼잡이 인접 역으로 통계적으로 함께 나타나는 경향'을 확인한 것.")
