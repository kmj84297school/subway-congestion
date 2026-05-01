"""
샘플 데이터 생성기 (v2: 인접 효과 강화 설계)
=============================================

[v1 대비 변경]
v1은 "노선 공통의 그날 분위기" 효과만 있어서, 같은 노선이면 인접하든 멀든
비슷한 상관이 나왔다. v2에서는 다음 두 가지를 분리한다.

  1. 노선 공통 효과 (약하게)
     - 같은 노선 전체에 약한 일별 효과 (std=0.05)
     - "오늘 2호선 전체가 약간 더 붐비는 날" 같은 광역 효과
  2. 인접 전파 효과 (강하게)
     - 각 역마다 그날의 "역 고유 노이즈"를 만든 뒤,
       인접 역의 노이즈와 가중평균하여 최종 노이즈로 사용
     - 결과: 인접한 두 역은 같은 날 노이즈가 비슷해짐
            → 한 역이 평균보다 높으면 인접 역도 평균보다 높을 확률 ↑
            → 조건부확률 P(B|A) > P(B) 가 자연스럽게 발생

[설계 원칙은 그대로]
  - 시간대별 패턴 (출퇴근 폭증)
  - 평일/주말 차이
  - 역 성격(office/leisure/mixed)에 따른 패턴 차이
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import os
import sys

# 인접 그래프 모듈을 부모 디렉토리에서 import
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from app.core.adjacency import STATIONS, ADJACENCY


# -----------------------------------------------------------------------------
# 2. 시간대별 가중치 (v1과 동일)
# -----------------------------------------------------------------------------
def get_hourly_pattern(station_type: str, is_weekend: bool):
    pattern = np.zeros(24)
    if station_type == "office":
        if not is_weekend:
            pattern[7:10]  = [1.5, 2.2, 1.8]
            pattern[10:17] = 0.7
            pattern[17:21] = [2.0, 2.5, 2.0, 1.3]
            pattern[21:24] = [0.8, 0.5, 0.3]
        else:
            pattern[7:10]  = 0.4
            pattern[10:17] = 0.6
            pattern[17:21] = 0.7
            pattern[21:24] = 0.4
    elif station_type == "leisure":
        if not is_weekend:
            pattern[7:10]  = [0.8, 1.2, 1.0]
            pattern[10:17] = 0.8
            pattern[17:21] = [1.5, 1.8, 1.7, 1.5]
            pattern[21:24] = [1.4, 1.2, 0.8]
        else:
            pattern[7:10]  = 0.4
            pattern[10:17] = [0.7, 0.9, 1.1, 1.3, 1.5, 1.6, 1.7]
            pattern[17:21] = [1.9, 2.0, 1.9, 1.6]
            pattern[21:24] = [1.5, 1.3, 0.9]
    else:  # mixed
        if not is_weekend:
            pattern[7:10]  = [1.3, 1.8, 1.4]
            pattern[10:17] = 0.8
            pattern[17:21] = [1.7, 2.0, 1.7, 1.2]
            pattern[21:24] = [0.9, 0.6, 0.4]
        else:
            pattern[7:10]  = 0.5
            pattern[10:17] = [0.9, 1.1, 1.3, 1.4, 1.5, 1.5, 1.4]
            pattern[17:21] = [1.6, 1.7, 1.5, 1.2]
            pattern[21:24] = [1.0, 0.7, 0.5]
    pattern[0:7] = np.maximum(pattern[0:7], 0.05)
    return pattern


# -----------------------------------------------------------------------------
# 3. 노이즈 행렬 생성 (v2의 핵심)
# -----------------------------------------------------------------------------
def build_noise_matrix(num_days: int,
                       line_effect_std: float = 0.05,
                       station_own_std: float = 0.15,
                       neighbor_weight: float = 0.55,
                       seed: int = 42) -> dict:
    """
    날짜 × 역 단위로, 각 (날짜, 역)에서 사용할 곱셈 노이즈를 만든다.

    절차:
      1) 노선 공통 효과 line_effect[d]: 평균 0, std=line_effect_std (작게)
      2) 역 고유 효과 own[d, station]: 평균 0, std=station_own_std
      3) 최종 효과 effect[d, station]
            = 1.0 + line_effect[d]
                  + (1 - neighbor_weight) * own[d, station]
                  + neighbor_weight * (인접 역들의 own 평균)

    수치 직관:
      - 인접 두 역은 own의 ~55%를 공유 → 강한 상관
      - 같은 노선 비인접은 line_effect만 공유 (std=0.05) → 매우 약한 상관
    """
    rng = np.random.default_rng(seed)

    lines = sorted({info["line"] for info in STATIONS.values()})
    line_effect = {
        line: rng.normal(loc=0.0, scale=line_effect_std, size=num_days)
        for line in lines
    }
    own = {
        st: rng.normal(loc=0.0, scale=station_own_std, size=num_days)
        for st in STATIONS
    }

    effect = {}
    for st, info in STATIONS.items():
        line = info["line"]
        neighbors = ADJACENCY.get(st, [])
        if neighbors:
            neighbor_mean = np.mean([own[n] for n in neighbors], axis=0)
        else:
            neighbor_mean = np.zeros(num_days)

        combined = (1.0
                    + line_effect[line]
                    + (1 - neighbor_weight) * own[st]
                    + neighbor_weight * neighbor_mean)
        combined = np.clip(combined, 0.6, 1.5)
        effect[st] = combined
    return effect


# -----------------------------------------------------------------------------
# 4. 데이터 생성 메인 함수
# -----------------------------------------------------------------------------
def generate(num_days: int = 60,
             start_date: str = "2025-09-01",
             output_path: str = None,
             seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    daily_effect_by_station = build_noise_matrix(num_days, seed=seed)

    start = datetime.strptime(start_date, "%Y-%m-%d")
    weekday_kr = ["월", "화", "수", "목", "금", "토", "일"]

    rows = []
    for d in range(num_days):
        date = start + timedelta(days=d)
        wd_idx = date.weekday()
        wd_name = weekday_kr[wd_idx]
        is_weekend = wd_idx >= 5

        for station, info in STATIONS.items():
            base = info["base"]
            line = info["line"]
            stype = info["type"]
            pattern = get_hourly_pattern(stype, is_weekend)
            day_eff = daily_effect_by_station[station][d]

            for hour in range(24):
                mean_total = base * pattern[hour] * day_eff
                hour_noise = rng.normal(loc=1.0, scale=0.06)
                total = max(0, int(mean_total * hour_noise))

                boarding_ratio = float(np.clip(0.5 + rng.normal(0, 0.05), 0.3, 0.7))
                boarding = int(total * boarding_ratio)
                alighting = total - boarding

                rows.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "weekday": wd_name,
                    "is_weekend": is_weekend,
                    "line": line,
                    "station": station,
                    "hour": hour,
                    "boarding": boarding,
                    "alighting": alighting,
                    "total": total,
                })

    df = pd.DataFrame(rows)
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        print(f"[OK] 샘플 데이터(v2) 저장: {output_path}")
        print(f"  - 총 행 수: {len(df):,}")
        print(f"  - 날짜 범위: {df['date'].min()} ~ {df['date'].max()}")
        print(f"  - 역 개수: {df['station'].nunique()}")
    return df


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "subway_sample.csv")
    generate(num_days=60, start_date="2025-09-01", output_path=out)
