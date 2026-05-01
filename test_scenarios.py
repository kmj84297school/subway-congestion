"""
다양한 시나리오에서 인접 vs 비인접 패턴 검증
"""
import sys
sys.path.insert(0, "/home/claude/subway_project")
import pandas as pd
from app.core.stats import (
    add_congestion_columns,
    calc_conditional_probability,
    calc_congestion_probability,
)

df = pd.read_csv("/home/claude/subway_project/data/subway_sample.csv")
df = add_congestion_columns(df)

scenarios = [
    ("강남",       False, 18, ["교대", "역삼"],          ["선릉", "삼성", "홍대입구", "잠실"]),
    ("홍대입구",   False, 19, ["합정", "신촌"],          ["이대", "강남", "잠실"]),
    ("잠실",       False, 18, ["잠실새내", "잠실나루"],  ["강변", "강남", "홍대입구"]),
    ("강남",       False,  8, ["교대", "역삼"],          ["선릉", "홍대입구"]),
    ("홍대입구",   True,  21, ["합정", "신촌"],          ["강남", "잠실"]),
]

print(f"{'시나리오':<28} {'인접 평균 diff':>13} {'비인접 평균 diff':>16} {'차이':>8}")
print("-" * 75)
overall_adj, overall_far = [], []
for station, weekend, hour, neighbors, fars in scenarios:
    label = f"{station} {'주말' if weekend else '평일'} {hour}시"
    adj_diffs, far_diffs = [], []
    for n in neighbors:
        c = calc_conditional_probability(df, station, n, weekend, hour)
        p = calc_congestion_probability(df, n, weekend, hour)
        if c["p_b_given_a"] is not None and p["prob"] is not None:
            adj_diffs.append(c["p_b_given_a"] - p["prob"])
    for f in fars:
        c = calc_conditional_probability(df, station, f, weekend, hour)
        p = calc_congestion_probability(df, f, weekend, hour)
        if c["p_b_given_a"] is not None and p["prob"] is not None:
            far_diffs.append(c["p_b_given_a"] - p["prob"])
    adj_mean = sum(adj_diffs)/len(adj_diffs) if adj_diffs else 0
    far_mean = sum(far_diffs)/len(far_diffs) if far_diffs else 0
    print(f"{label:<28} {adj_mean:>+13.3f} {far_mean:>+16.3f} {adj_mean - far_mean:>+8.3f}")
    overall_adj.extend(adj_diffs); overall_far.extend(far_diffs)

print("-" * 75)
print(f"{'전체 평균':<28} {sum(overall_adj)/len(overall_adj):>+13.3f} "
      f"{sum(overall_far)/len(overall_far):>+16.3f} "
      f"{sum(overall_adj)/len(overall_adj) - sum(overall_far)/len(overall_far):>+8.3f}")
