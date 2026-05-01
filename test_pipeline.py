"""
백엔드 통합 테스트 — 전체 분석 파이프라인 검증
==============================================
사용자가 웹에서 (강남, 평일, 18시)를 입력했을 때 어떤 결과가 나오는지를
처음부터 끝까지 시뮬레이션한다.
"""
import sys
sys.path.insert(0, "/home/claude/subway_project")

import pandas as pd
from app.core.stats import (
    add_congestion_columns,
    calc_mean_std,
    calc_congestion_probability,
    calc_conditional_probability,
    judge_independence,
)
from app.core.adjacency import get_neighbors
from app.core.model import CongestionModel
from app.core.interpreter import (
    describe_basic_stats,
    describe_probability,
    describe_conditional,
    make_summary,
)

# === 1. 데이터 준비 ===
df = pd.read_csv("/home/claude/subway_project/data/subway_sample.csv")
df = add_congestion_columns(df)

# === 2. AI 모델 학습 (서버 시작 시 1회 학습 가정) ===
ai_model = CongestionModel(model_type="tree", max_depth=6).fit(df)
print(f"[AI] 학습 완료. 테스트 정확도: {ai_model.test_accuracy:.3f}\n")

# === 3. 사용자 입력 시뮬레이션 ===
user_station = "강남"
user_weekday = False  # 평일
user_hour = 18
user_label = "평일" if not user_weekday else "주말"

print("=" * 70)
print(f"사용자 입력: {user_station}역, {user_label}, {user_hour}시")
print("=" * 70)

# === 4. 통계 분석 ===
stats_res = calc_mean_std(df, user_station, user_weekday, user_hour)
prob_res = calc_congestion_probability(df, user_station, user_weekday, user_hour)
print("\n[1] 기초 통계")
print(f"    n={stats_res['n']}, 평균={stats_res['mean']:,.0f}, 표준편차={stats_res['std']:,.0f}")
print("\n[2] 혼잡 확률")
print(f"    P(혼잡) = {prob_res['prob']:.3f} ({prob_res['n_cong']}/{prob_res['n']})")

# === 5. 조건부확률 (인접 역) ===
neighbors = get_neighbors(user_station)
print(f"\n[3] 인접 역과의 조건부확률 (인접: {neighbors})")
conditional_blocks = []
for n in neighbors:
    cond = calc_conditional_probability(df, user_station, n, user_weekday, user_hour)
    p_b = calc_congestion_probability(df, n, user_weekday, user_hour)["prob"]
    indep = judge_independence(p_b, cond["p_b_given_a"])
    print(f"    {n:8s}: P(B)={p_b:.3f}  P(B|A)={cond['p_b_given_a']:.3f}  "
          f"diff={indep['diff']:+.3f}  → {indep['verdict']}")
    conditional_blocks.append({
        "neighbor": n,
        "p_b": p_b,
        "p_b_given_a": cond["p_b_given_a"],
        "independence": indep,
    })

# === 6. AI 보조 예측 ===
# 직전 시간대 평균 이용량과 인접 역 혼잡 비율을 데이터에서 도출
prev_hour_avg = df[(df.station==user_station) & (df.hour==user_hour-1) &
                   (df.is_weekend==user_weekday)]["total"].mean()
neighbor_cong_avg = df[(df.station.isin(neighbors)) & (df.hour==user_hour) &
                       (df.is_weekend==user_weekday)]["congested"].mean()
ai_res = ai_model.predict_proba_for(
    station=user_station, is_weekend=user_weekday, hour=user_hour,
    prev_total=float(prev_hour_avg), neighbor_ratio=float(neighbor_cong_avg),
)
print(f"\n[4] AI 보조 예측")
print(f"    AI 혼잡 확률: {ai_res['congested_prob']:.3f}")
print(f"    AI 이진 예측: {'혼잡' if ai_res['congested_pred']==1 else '비혼잡'}")

# === 7. 자동 해석 문장 (웹에 표시될 텍스트) ===
print("\n" + "=" * 70)
print("자동 생성된 해석 문장 (웹 결과 페이지에 표시될 내용)")
print("=" * 70)
summary = make_summary(
    station=user_station, weekday_label=user_label, hour=user_hour,
    stats_result=stats_res, prob_result=prob_res,
    ai_result=ai_res, conditional_blocks=conditional_blocks,
)
# 줄바꿈 보기 좋게
for line in summary.split(". "):
    if line.strip():
        print(f"  • {line.strip().rstrip('.')}.")
