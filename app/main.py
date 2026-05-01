"""
FastAPI 웹 서버 (main.py)
=========================

웹 인터페이스를 제공한다. 사용자는 역·요일·시간대를 선택하고, 분석 결과를
받는다. 모든 백엔드 로직은 app/core/ 의 모듈을 호출해서 처리한다.

[엔드포인트]
  GET  /          : 입력 폼 페이지
  POST /analyze   : 분석 실행 → 결과 페이지 렌더링
  GET  /api/stations : 등록된 역 목록 (JSON)

[실행 방법]
  cd 프로젝트_루트
  uvicorn app.main:app --reload
  → 브라우저에서 http://127.0.0.1:8000 접속
"""

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

import pandas as pd

# 백엔드 모듈 (app/core)
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
from app.core.interpreter import (
    describe_basic_stats,
    describe_probability,
    describe_conditional,
    make_summary,
)
from app.core.visualizer import (
    plot_hourly_average,
    plot_congestion_probability,
    plot_neighbor_comparison,
    plot_neighbor_diff,
)


# =============================================================================
# 앱 및 전역 리소스 초기화
# =============================================================================
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DATA_PATH = PROJECT_ROOT / "data" / "subway_sample.csv"

app = FastAPI(title="지하철 혼잡 예측 모델")

# 정적 파일 / 템플릿
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# 데이터와 AI 모델은 서버 시작 시 1회 로드 (요청마다 재로딩 X)
# startup이 실패해도 서버는 떠야 디버깅 가능 — 예외를 잡아 STARTUP_ERROR 에 저장
DF = None
AI_MODEL = None
STARTUP_ERROR = None
try:
    print("[startup] 데이터 로드 중...", flush=True)
    DF = pd.read_csv(DATA_PATH)
    DF = add_congestion_columns(DF)
    print(f"[startup] 데이터 행 수: {len(DF):,}", flush=True)

    print("[startup] AI 모델 학습 중...", flush=True)
    AI_MODEL = CongestionModel(model_type="tree", max_depth=6).fit(DF)
    print(f"[startup] AI 모델 테스트 정확도: {AI_MODEL.test_accuracy:.3f}", flush=True)
    print("[startup] 초기화 완료.", flush=True)
except Exception as e:
    import traceback
    STARTUP_ERROR = f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}"
    print("[startup] !!! 초기화 실패 !!!", flush=True)
    print(STARTUP_ERROR, flush=True)


# =============================================================================
# 라우트
# =============================================================================
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    """입력 폼 페이지"""
    if STARTUP_ERROR is not None:
        # 부팅 실패 시 에러 페이지 직접 반환 (디버깅 용도)
        return HTMLResponse(
            content=(
                "<html><head><meta charset='utf-8'><title>Startup Error</title>"
                "<style>body{font-family:system-ui;padding:24px;max-width:900px;margin:auto;}"
                "pre{background:#fef2f2;border:1px solid #fecaca;padding:16px;border-radius:8px;"
                "white-space:pre-wrap;word-break:break-word;}h1{color:#b91c1c;}</style></head>"
                "<body><h1>서버 초기화 실패</h1>"
                "<p>서버는 떠 있지만 데이터 또는 AI 모델 로드에 실패했습니다. "
                "Render Logs와 아래 메시지를 확인하세요.</p>"
                f"<pre>{STARTUP_ERROR}</pre></body></html>"
            ),
            status_code=500,
        )
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "stations": get_all_stations(),
            "hours": list(range(24)),
        },
    )


@app.get("/api/stations")
def api_stations():
    """등록된 역 목록 (JSON)"""
    return JSONResponse({"stations": get_all_stations()})


@app.get("/health")
def health_check():
    """Render 헬스체크용. startup 성공 여부 + 모델 준비 여부 반환."""
    if STARTUP_ERROR is not None:
        return JSONResponse(
            {"status": "startup_failed", "error": STARTUP_ERROR[:500]},
            status_code=500,
        )
    ready = AI_MODEL is not None and AI_MODEL.feature_columns is not None
    return JSONResponse(
        {"status": "ok" if ready else "loading",
         "rows": int(len(DF)) if DF is not None else 0},
        status_code=200 if ready else 503,
    )


@app.post("/analyze", response_class=HTMLResponse)
def analyze(
    request: Request,
    station: str = Form(...),
    weekday_type: str = Form(...),  # "weekday" or "weekend"
    hour: int = Form(...),
):
    """
    분석 실행 후 결과 페이지 렌더링.
    """
    if STARTUP_ERROR is not None or DF is None or AI_MODEL is None:
        return HTMLResponse(
            content=f"<h1>서버 초기화 실패</h1><pre>{STARTUP_ERROR or 'Unknown'}</pre>",
            status_code=500,
        )
    is_weekend = (weekday_type == "weekend")
    weekday_label = "주말" if is_weekend else "평일"

    # 1) 기초 통계
    stats_res = calc_mean_std(DF, station, is_weekend, hour)

    # 2) 혼잡 확률
    prob_res = calc_congestion_probability(DF, station, is_weekend, hour)

    # 데이터 부족 처리
    if stats_res["n"] == 0:
        return templates.TemplateResponse(request, "result.html", {
            "error": f"{station}역 {weekday_label} {hour}시 조건에 해당하는 데이터가 없습니다.",
            "station": station, "weekday_label": weekday_label, "hour": hour,
        })

    # 3) 인접 역 조건부확률
    neighbors = get_neighbors(station)
    conditional_blocks = []
    for n in neighbors:
        cond = calc_conditional_probability(DF, station, n, is_weekend, hour)
        prob_b = calc_congestion_probability(DF, n, is_weekend, hour)
        indep = judge_independence(prob_b["prob"], cond["p_b_given_a"])
        conditional_blocks.append({
            "neighbor": n,
            "p_b": prob_b["prob"],
            "p_b_given_a": cond["p_b_given_a"],
            "diff": indep["diff"],
            "verdict": indep["verdict"],
            "explanation": indep["explanation"],
        })

    # 4) AI 보조 예측
    prev_hour_avg = float(
        DF[(DF.station == station) & (DF.hour == max(0, hour - 1)) &
           (DF.is_weekend == is_weekend)]["total"].mean()
    )
    if neighbors:
        neighbor_cong_ratio = float(
            DF[(DF.station.isin(neighbors)) & (DF.hour == hour) &
               (DF.is_weekend == is_weekend)]["congested"].mean()
        )
    else:
        neighbor_cong_ratio = 0.0
    ai_res = AI_MODEL.predict_proba_for(
        station=station, is_weekend=is_weekend, hour=hour,
        prev_total=prev_hour_avg, neighbor_ratio=neighbor_cong_ratio,
    )

    # 5) 이 조건의 "전형적 수준" — 평균을 기준점으로 한 등급
    #    (단일 날짜 예측이 아니라, 이 조건의 평균이 평소 기준에서 어디 위치하는지)
    typical_grade = classify_congestion(stats_res["mean"], stats_res["mean"], stats_res["std"])
    # AI 예측이 0.5를 넘으면 혼잡, 아니면 비혼잡으로 표기
    expected_grade = "혼잡 가능성 높음" if (ai_res.get("congested_prob") or 0) >= 0.5 else "혼잡 가능성 낮음"

    # 6) 자동 해석 문장
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

    # 7) 시각화 (base64 PNG)
    chart_hourly = plot_hourly_average(DF, station, is_weekend)
    chart_prob = plot_congestion_probability(DF, station, is_weekend, highlight_hour=hour)
    chart_neighbor = plot_neighbor_comparison(DF, station, is_weekend, hour)
    chart_diff = plot_neighbor_diff(DF, station, is_weekend, hour, n_far=4)

    # 표본 부족 경고
    low_sample_warning = stats_res["n"] < 10

    return templates.TemplateResponse(request, "result.html", {
        "error": None,
        # 입력값
        "station": station,
        "weekday_label": weekday_label,
        "hour": hour,
        # 통계
        "stats": stats_res,
        "prob": prob_res,
        "typical_grade": typical_grade,
        "expected_grade": expected_grade,
        # 조건부확률
        "neighbors": neighbors,
        "conditional_blocks": conditional_blocks,
        # AI
        "ai": ai_res,
        # 해석
        "summary": summary,
        # 그래프
        "chart_hourly": chart_hourly,
        "chart_prob": chart_prob,
        "chart_neighbor": chart_neighbor,
        "chart_diff": chart_diff,
        # 경고
        "low_sample_warning": low_sample_warning,
    })
