"""
샘플 데이터 검증 스크립트
=========================
- 시간대별 평균 패턴이 합리적인가
- 평일과 주말이 다르게 나오는가
- 인접 역 상관관계가 실제로 존재하는가 (조건부확률 P(B|A) > P(B))
"""
import pandas as pd
import numpy as np

df = pd.read_csv("/home/claude/subway_project/data/subway_sample.csv")
print("=" * 60)
print("검증 1: 시간대별 평균 (강남역, 평일)")
print("=" * 60)
sub = df[(df.station == "강남") & (~df.is_weekend)]
print(sub.groupby("hour")["total"].mean().round(0).to_string())

print()
print("=" * 60)
print("검증 2: 평일 vs 주말 (강남 18시 vs 홍대입구 21시)")
print("=" * 60)
print("강남 18시 평일 평균:",
      df[(df.station=="강남") & (df.hour==18) & (~df.is_weekend)]["total"].mean().round(0))
print("강남 18시 주말 평균:",
      df[(df.station=="강남") & (df.hour==18) & (df.is_weekend)]["total"].mean().round(0))
print("홍대 21시 평일 평균:",
      df[(df.station=="홍대입구") & (df.hour==21) & (~df.is_weekend)]["total"].mean().round(0))
print("홍대 21시 주말 평균:",
      df[(df.station=="홍대입구") & (df.hour==21) & (df.is_weekend)]["total"].mean().round(0))

print()
print("=" * 60)
print("검증 3: 인접 역 상관관계 (P(B|A) vs P(B))")
print("=" * 60)
print("강남 평일 18시가 혼잡할 때, 역삼도 혼잡한가?")

# 강남 평일 18시
g_weekday_18 = df[(df.station=="강남") & (df.hour==18) & (~df.is_weekend)].copy()
y_weekday_18 = df[(df.station=="역삼") & (df.hour==18) & (~df.is_weekend)].copy()

# 평균 + 표준편차로 혼잡 정의
g_mean, g_std = g_weekday_18["total"].mean(), g_weekday_18["total"].std()
y_mean, y_std = y_weekday_18["total"].mean(), y_weekday_18["total"].std()

g_weekday_18["congested"] = g_weekday_18["total"] >= g_mean
y_weekday_18["congested"] = y_weekday_18["total"] >= y_mean

# 날짜별로 두 역을 합쳐서 비교
merged = g_weekday_18[["date","congested"]].merge(
    y_weekday_18[["date","congested"]], on="date", suffixes=("_g","_y"))

P_y = merged["congested_y"].mean()
P_y_given_g = merged[merged["congested_g"]]["congested_y"].mean()

print(f"  P(역삼 혼잡)               = {P_y:.3f}")
print(f"  P(역삼 혼잡 | 강남 혼잡)    = {P_y_given_g:.3f}")
print(f"  차이 (P(B|A) - P(B))       = {P_y_given_g - P_y:+.3f}")
print(f"  → {'OK: 인접 역 상관관계 존재 ✓' if P_y_given_g > P_y + 0.05 else '약한 상관 (재조정 필요)'}")

print()
print("검증 4: 비인접 역 비교 (강남 vs 홍대입구는 노선은 같지만 멀리 있음)")
h_weekday_18 = df[(df.station=="홍대입구") & (df.hour==18) & (~df.is_weekend)].copy()
h_mean = h_weekday_18["total"].mean()
h_weekday_18["congested"] = h_weekday_18["total"] >= h_mean

merged2 = g_weekday_18[["date","congested"]].merge(
    h_weekday_18[["date","congested"]], on="date", suffixes=("_g","_h"))
P_h = merged2["congested_h"].mean()
P_h_given_g = merged2[merged2["congested_g"]]["congested_h"].mean()
print(f"  P(홍대입구 혼잡)               = {P_h:.3f}")
print(f"  P(홍대입구 혼잡 | 강남 혼잡)    = {P_h_given_g:.3f}")
print(f"  차이                          = {P_h_given_g - P_h:+.3f}")
print(f"  (참고: 노선 공통 효과로 약한 양의 상관은 있을 수 있음)")
