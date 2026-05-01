"""
시각화 모듈 (visualizer.py)
===========================

분석 결과를 그래프로 시각화한다. 결과는 base64 인코딩된 PNG 문자열로
반환되어, FastAPI에서 HTML <img src="data:image/png;base64,..."> 형태로
바로 삽입할 수 있다.

[제공 그래프 4종]
  1. plot_hourly_average        : 선택한 역의 시간대별 평균 이용량 (라인)
  2. plot_congestion_probability: 시간대별 혼잡 확률 막대그래프
  3. plot_neighbor_comparison   : 인접 역의 P(B) vs P(B|A) 비교 (★발표 핵심)
  4. plot_neighbor_diff         : 인접/비인접 역의 diff 막대그래프
"""

import io
import base64
import matplotlib

matplotlib.use("Agg")  # 서버 환경에서 GUI 없이 동작
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from app.core.stats import (
    calc_mean_std,
    calc_congestion_probability,
    calc_conditional_probability,
)
from app.core.adjacency import get_neighbors, get_all_stations


# =============================================================================
# 한글 폰트 설정 (OS별 fallback)
# =============================================================================
def _setup_korean_font():
    """
    한글이 가능한 폰트를 찾아 설정한다.

    우선순위:
      1) koreanize_matplotlib 패키지가 설치되어 있으면 그것을 사용
         (NanumGothic 내장, Render 등 시스템 폰트 설치 권한 없는 환경에서 유용)
      2) OS의 한글 폰트 이름 매칭 (Malgun Gothic, AppleGothic 등)
      3) 시스템에 있는 한글 폰트 파일 직접 등록
      4) 못 찾으면 기본값 (한글 깨질 수 있음)
    """
    # 1차: koreanize_matplotlib (pip로 설치된 경우)
    try:
        import koreanize_matplotlib  # noqa: F401  (import만으로 자동 설정됨)
        plt.rcParams["axes.unicode_minus"] = False
        return "koreanize_matplotlib (NanumGothic)"
    except ImportError:
        pass

    # 2차: 폰트 이름으로 매칭
    name_candidates = [
        "Malgun Gothic", "AppleGothic", "NanumGothic",
        "Noto Sans CJK KR", "Noto Sans KR", "Apple SD Gothic Neo",
        "NanumBarunGothic",
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for c in name_candidates:
        if c in available:
            plt.rcParams["font.family"] = c
            plt.rcParams["axes.unicode_minus"] = False
            return c

    # 3차: 파일 경로로 직접 등록 시도 (Linux 환경 대응)
    file_candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/Library/Fonts/AppleGothic.ttf",
        "C:/Windows/Fonts/malgun.ttf",
    ]
    for path in file_candidates:
        if os.path.exists(path):
            try:
                fm.fontManager.addfont(path)
                prop = fm.FontProperties(fname=path)
                name = prop.get_name()
                plt.rcParams["font.family"] = name
                plt.rcParams["axes.unicode_minus"] = False
                return name
            except Exception:
                continue

    # 4차: 못 찾음
    plt.rcParams["axes.unicode_minus"] = False
    return None


_setup_korean_font()


# =============================================================================
# 공통: matplotlib figure → base64 PNG 문자열
# =============================================================================
def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


# =============================================================================
# 그래프 1: 시간대별 평균 이용량 (라인 차트)
# =============================================================================
def plot_hourly_average(df: pd.DataFrame, station: str, is_weekend: bool) -> str:
    """선택한 역의 24시간 평균 이용량 패턴"""
    sub = df[(df["station"] == station) & (df["is_weekend"] == is_weekend)]
    hourly = sub.groupby("hour")["total"].mean().reindex(range(24), fill_value=0)

    fig, ax = plt.subplots(figsize=(8.5, 4.0))
    ax.plot(hourly.index, hourly.values, marker="o", linewidth=2, color="#2563eb")
    ax.fill_between(hourly.index, hourly.values, alpha=0.15, color="#2563eb")

    label = "주말" if is_weekend else "평일"
    ax.set_title(f"{station}역 {label} 시간대별 평균 이용량", fontsize=13)
    ax.set_xlabel("시간 (시)")
    ax.set_ylabel("평균 이용량 (명)")
    ax.set_xticks(range(0, 24, 2))
    ax.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    return _fig_to_base64(fig)


# =============================================================================
# 그래프 2: 시간대별 혼잡 확률 막대그래프
# =============================================================================
def plot_congestion_probability(df: pd.DataFrame, station: str, is_weekend: bool,
                                 highlight_hour: int = None) -> str:
    """24시간 각각의 혼잡 확률 P(혼잡)"""
    probs = []
    for h in range(24):
        r = calc_congestion_probability(df, station, is_weekend, h)
        probs.append(r["prob"] if r["prob"] is not None else 0.0)

    fig, ax = plt.subplots(figsize=(8.5, 4.0))
    colors = ["#94a3b8"] * 24
    if highlight_hour is not None and 0 <= highlight_hour < 24:
        colors[highlight_hour] = "#dc2626"
    ax.bar(range(24), probs, color=colors, edgecolor="white")
    ax.axhline(y=0.5, color="#475569", linestyle="--", alpha=0.5, linewidth=1)

    label = "주말" if is_weekend else "평일"
    ax.set_title(f"{station}역 {label} 시간대별 혼잡 확률", fontsize=13)
    ax.set_xlabel("시간 (시)")
    ax.set_ylabel("P(혼잡)")
    ax.set_xticks(range(0, 24, 2))
    ax.set_ylim(0, 1.0)
    ax.grid(True, alpha=0.3, axis="y")
    ax.set_axisbelow(True)

    if highlight_hour is not None:
        ax.text(highlight_hour, probs[highlight_hour] + 0.03,
                f"{probs[highlight_hour]:.2f}",
                ha="center", fontsize=10, fontweight="bold", color="#dc2626")
    return _fig_to_base64(fig)


# =============================================================================
# 그래프 3 (★발표 클라이맥스): 인접 역 P(B) vs P(B|A) 비교
# =============================================================================
def plot_neighbor_comparison(df: pd.DataFrame, station: str,
                              is_weekend: bool, hour: int) -> str:
    """
    선택 역의 인접 역들에 대해, 평소 혼잡 확률 P(B)와
    조건부확률 P(B|A)을 나란히 막대그래프로 보여준다.

    이게 본 프로젝트의 가장 핵심적인 시각화: 한 그래프 안에서
    "독립이라면 두 막대가 같아야 하는데, 실제로는 P(B|A)가 더 높다"가
    한눈에 보이도록.
    """
    neighbors = get_neighbors(station)
    if not neighbors:
        # 인접 없음 → 빈 그래프
        fig, ax = plt.subplots(figsize=(7, 3.5))
        ax.text(0.5, 0.5, f"{station}역의 인접 역 정보가 없습니다.",
                ha="center", va="center", fontsize=12)
        ax.axis("off")
        return _fig_to_base64(fig)

    p_b_list = []
    p_b_given_a_list = []
    for n in neighbors:
        prob = calc_congestion_probability(df, n, is_weekend, hour)
        cond = calc_conditional_probability(df, station, n, is_weekend, hour)
        p_b_list.append(prob["prob"] if prob["prob"] is not None else 0.0)
        p_b_given_a_list.append(cond["p_b_given_a"] if cond["p_b_given_a"] is not None else 0.0)

    x = np.arange(len(neighbors))
    width = 0.36
    fig, ax = plt.subplots(figsize=(max(7, 1.6 * len(neighbors) + 4), 4.5))
    bars1 = ax.bar(x - width/2, p_b_list, width,
                    label="P(B 혼잡) — 평소", color="#94a3b8", edgecolor="white")
    bars2 = ax.bar(x + width/2, p_b_given_a_list, width,
                    label=f"P(B 혼잡 | {station} 혼잡)",
                    color="#dc2626", edgecolor="white")

    for bars in (bars1, bars2):
        for b in bars:
            h = b.get_height()
            ax.text(b.get_x() + b.get_width()/2, h + 0.015,
                    f"{h:.2f}", ha="center", fontsize=10)

    label = "주말" if is_weekend else "평일"
    ax.set_title(f"{station}역 혼잡 시 인접 역의 조건부확률  ({label} {hour}시)",
                 fontsize=13)
    ax.set_xticks(x)
    ax.set_xticklabels(neighbors)
    ax.set_ylabel("확률")
    ax.set_ylim(0, max(1.0, max(p_b_given_a_list + p_b_list) * 1.2))
    ax.legend(loc="upper right", framealpha=0.95)
    ax.grid(True, alpha=0.3, axis="y")
    ax.set_axisbelow(True)
    return _fig_to_base64(fig)


# =============================================================================
# 그래프 4: 인접 vs 비인접 비교 (diff 막대그래프)
# =============================================================================
def plot_neighbor_diff(df: pd.DataFrame, station: str,
                        is_weekend: bool, hour: int,
                        n_far: int = 3) -> str:
    """
    P(B|A) - P(B) 차이를 인접 역과 비인접 역에 대해 비교.
    인접일수록 양의 값이 크게 나타나는 패턴을 시각화.
    """
    neighbors = get_neighbors(station)
    all_others = [s for s in get_all_stations()
                   if s != station and s not in neighbors]
    # 비인접 역은 무작위 선택보다는 적당한 표본을 선택 — 알파벳 기준 일부
    far_stations = all_others[:n_far]

    targets = [(n, "인접") for n in neighbors] + [(f, "비인접") for f in far_stations]
    if not targets:
        fig, ax = plt.subplots(figsize=(7, 3.5))
        ax.text(0.5, 0.5, "비교할 역이 없습니다.", ha="center", va="center")
        ax.axis("off")
        return _fig_to_base64(fig)

    diffs, labels, types = [], [], []
    for st, kind in targets:
        prob = calc_congestion_probability(df, st, is_weekend, hour)
        cond = calc_conditional_probability(df, station, st, is_weekend, hour)
        if prob["prob"] is None or cond["p_b_given_a"] is None:
            continue
        diffs.append(cond["p_b_given_a"] - prob["prob"])
        labels.append(st)
        types.append(kind)

    fig, ax = plt.subplots(figsize=(max(7, 1.0 * len(labels) + 3), 4.0))
    colors = ["#dc2626" if t == "인접" else "#94a3b8" for t in types]
    bars = ax.bar(range(len(labels)), diffs, color=colors, edgecolor="white")
    ax.axhline(y=0, color="#475569", linewidth=1)
    for b, d in zip(bars, diffs):
        offset = 0.012 if d >= 0 else -0.025
        ax.text(b.get_x() + b.get_width()/2, d + offset,
                f"{d:+.2f}", ha="center", fontsize=9)

    label = "주말" if is_weekend else "평일"
    ax.set_title(
        f"{station}역 혼잡 시 다른 역의 혼잡 확률 변화량  P(B|A) − P(B)  ({label} {hour}시)",
        fontsize=12,
    )
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_ylabel("diff = P(B|A) − P(B)")
    ax.grid(True, alpha=0.3, axis="y")
    ax.set_axisbelow(True)

    # 범례
    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(facecolor="#dc2626", label="인접 역"),
        Patch(facecolor="#94a3b8", label="비인접 역"),
    ], loc="best", framealpha=0.95)
    return _fig_to_base64(fig)
