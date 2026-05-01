"""
FastAPI 서버 없이도 서버 응답을 시뮬레이션하는 통합 테스트.

이 스크립트는 실제 서버를 띄우지 않고도, /analyze 엔드포인트가 받았을
입력값에 대해 같은 백엔드 로직을 실행하고, 같은 Jinja2 템플릿을
렌더링하여 최종 HTML이 정상적으로 만들어지는지 확인한다.

목적: 학생 본인 컴퓨터에서 `uvicorn app.main:app` 했을 때 어떤 결과가
나올지 사전 검증.
"""
import sys
sys.path.insert(0, "/home/claude/subway_project")

from pathlib import Path
import pandas as pd
from jinja2 import Environment, FileSystemLoader

from app.core.stats import (
    add_congestion_columns,
    calc_mean_std,
    calc_congestion_probability,
    calc_conditional_probability,
    judge_independence,
    classify_congestion,
)
from app.core.adjacency import get_neighbors, get_all_stations
from app.core.model import CongestionModel
from app.core.interpreter import make_summary
from app.core.visualizer import (
    plot_hourly_average,
    plot_congestion_probability,
    plot_neighbor_comparison,
    plot_neighbor_diff,
)


# === 데이터 / 모델 준비 (서버 startup 흉내) ===
DF = pd.read_csv("/home/claude/subway_project/data/subway_sample.csv")
DF = add_congestion_columns(DF)
AI_MODEL = CongestionModel(model_type="tree", max_depth=6).fit(DF)

# === 사용자 입력 시뮬레이션 ===
station, weekday_type, hour = "강남", "weekday", 18
is_weekend = (weekday_type == "weekend")
weekday_label = "주말" if is_weekend else "평일"

# === main.py의 /analyze 엔드포인트 로직을 그대로 ===
stats_res = calc_mean_std(DF, station, is_weekend, hour)
prob_res = calc_congestion_probability(DF, station, is_weekend, hour)

neighbors = get_neighbors(station)
conditional_blocks = []
for n in neighbors:
    cond = calc_conditional_probability(DF, station, n, is_weekend, hour)
    prob_b = calc_congestion_probability(DF, n, is_weekend, hour)
    indep = judge_independence(prob_b["prob"], cond["p_b_given_a"])
    conditional_blocks.append({
        "neighbor": n, "p_b": prob_b["prob"],
        "p_b_given_a": cond["p_b_given_a"],
        "diff": indep["diff"], "verdict": indep["verdict"],
        "explanation": indep["explanation"],
    })

prev_hour_avg = float(
    DF[(DF.station == station) & (DF.hour == max(0, hour-1)) &
       (DF.is_weekend == is_weekend)]["total"].mean()
)
neighbor_cong_ratio = float(
    DF[(DF.station.isin(neighbors)) & (DF.hour == hour) &
       (DF.is_weekend == is_weekend)]["congested"].mean()
) if neighbors else 0.0

ai_res = AI_MODEL.predict_proba_for(
    station=station, is_weekend=is_weekend, hour=hour,
    prev_total=prev_hour_avg, neighbor_ratio=neighbor_cong_ratio,
)
grade = classify_congestion(stats_res["mean"], stats_res["mean"], stats_res["std"])
expected_grade = "혼잡 가능성 높음" if (ai_res.get("congested_prob") or 0) >= 0.5 else "혼잡 가능성 낮음"

interp_blocks = [
    {"neighbor": b["neighbor"], "p_b": b["p_b"],
     "p_b_given_a": b["p_b_given_a"],
     "independence": {"diff": b["diff"], "verdict": b["verdict"],
                       "explanation": b["explanation"]}}
    for b in conditional_blocks if b["p_b_given_a"] is not None
]
summary = make_summary(
    station=station, weekday_label=weekday_label, hour=hour,
    stats_result=stats_res, prob_result=prob_res,
    ai_result=ai_res, conditional_blocks=interp_blocks,
)

chart_hourly = plot_hourly_average(DF, station, is_weekend)
chart_prob = plot_congestion_probability(DF, station, is_weekend, highlight_hour=hour)
chart_neighbor = plot_neighbor_comparison(DF, station, is_weekend, hour)
chart_diff = plot_neighbor_diff(DF, station, is_weekend, hour, n_far=4)

# === Jinja2 템플릿 직접 렌더링 ===
env = Environment(loader=FileSystemLoader("/home/claude/subway_project/app/templates"))

# index.html 도 한번 확인
idx_tmpl = env.get_template("index.html")
class FakeRequest: pass
idx_html = idx_tmpl.render(request=FakeRequest(), stations=get_all_stations(), hours=list(range(24)))
Path("/tmp/index_rendered.html").write_text(idx_html, encoding="utf-8")
print(f"[OK] index.html 렌더링: {len(idx_html):,} chars")

# result.html
res_tmpl = env.get_template("result.html")
res_html = res_tmpl.render(
    request=FakeRequest(), error=None,
    station=station, weekday_label=weekday_label, hour=hour,
    stats=stats_res, prob=prob_res, typical_grade=grade, expected_grade=expected_grade,
    neighbors=neighbors, conditional_blocks=conditional_blocks,
    ai=ai_res, summary=summary,
    chart_hourly=chart_hourly, chart_prob=chart_prob,
    chart_neighbor=chart_neighbor, chart_diff=chart_diff,
    low_sample_warning=stats_res["n"] < 10,
)
Path("/tmp/result_rendered.html").write_text(res_html, encoding="utf-8")
print(f"[OK] result.html 렌더링: {len(res_html):,} chars")

# 검증: 핵심 요소가 HTML에 들어있는지
checks = [
    ("station name in HTML",       station in res_html),
    ("summary text included",      "혼잡" in res_html),
    ("conditional table rendered", "P(B 혼잡 | 강남 혼잡)" in res_html or "조건부확률" in res_html),
    ("4 chart images embedded",    res_html.count("data:image/png;base64,") == 4),
    ("AI prob displayed",          "AI 보조" in res_html),
    ("no template errors",         "{{" not in res_html and "{%" not in res_html),
]
print("\n[검증]")
for label, ok in checks:
    print(f"  {'✓' if ok else '✗'}  {label}")
