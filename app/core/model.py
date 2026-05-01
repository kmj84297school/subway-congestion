"""
AI 보조 예측 모델 (model.py)
============================

[프로젝트에서의 위치 — 보조 도구]
이 모듈은 본 프로젝트의 핵심이 아니다. 핵심은 stats.py의 확률·통계 분석이다.
AI 모델은 다음 두 가지 보조 역할만 한다:

  1. 사용자가 입력한 새로운 조건(역·요일·시간대)에 대해 빠르게
     "혼잡 여부" 예측값을 제공한다.
  2. 통계 기반 예측과 AI 예측을 나란히 보여주어, 두 결과가 일치하는지를
     사용자가 직접 비교할 수 있게 한다.

[구조의 의미 — 보고서에 반드시 명시할 포인트]
AI 모델의 학습 라벨은 "stats.py의 평균 기준에 따라 정의된 혼잡 여부"이다.
즉 AI는 우리가 확률·통계로 정의한 혼잡 기준을 흉내내도록 훈련된다.
따라서 AI의 정확도는 "AI가 확통 기준을 얼마나 잘 따라하는가"이지,
새로운 진실을 발견하는 것이 아니다.

[모델 선택]
의사결정나무(DecisionTreeClassifier)를 기본으로 사용한다.
이유:
  - 해석 가능성: 어떤 변수가 어떤 임계값에서 분기되는지 사람이 읽을 수 있다.
  - 작은 데이터에 적합: 60일 × 15역 정도 규모에서 잘 작동한다.
  - 발표용으로 적합: "왜 AI가 그렇게 판단했는가"를 설명하기 쉽다.
선택 옵션으로 랜덤포레스트도 제공한다.

[입력 변수 (피처)]
  - station (역명 → one-hot 인코딩)
  - is_weekend (0/1)
  - hour (0~23)
  - prev_hour_total (직전 시간대 이용량)
  - neighbor_congested_ratio (인접 역들의 평균 혼잡 여부)

[출력]
  - 0/1 이진 예측 (혼잡 여부)
  - 혼잡 확률 (0.0~1.0)
"""

import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from app.core.adjacency import ADJACENCY, get_all_stations


# =============================================================================
# 1. 피처 엔지니어링 (확통 분석 결과를 AI에게 먹이는 단계)
# =============================================================================
def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    원본 데이터프레임으로부터 AI 모델용 피처 데이터프레임을 만든다.

    [중요] 이 함수는 stats.add_congestion_columns()가 이미 적용된 df를
    입력받는다고 가정한다. 즉 'congested', 'group_mean' 컬럼이 있어야 함.

    피처:
      - is_weekend (0/1)
      - hour (0~23)
      - prev_hour_total: 같은 역의 1시간 전 이용량
      - neighbor_congested_ratio: 같은 시간 인접 역들의 혼잡 평균
      - station_* (one-hot)

    레이블:
      - congested (0/1)
    """
    df = df.copy()
    df = df.sort_values(["station", "date", "hour"]).reset_index(drop=True)

    # 직전 시간대 이용량 (같은 역, 같은 날짜 안에서 1시간 전)
    df["prev_hour_total"] = df.groupby(["station", "date"])["total"].shift(1).fillna(0)

    # 인접 역들의 같은 시간 평균 혼잡 비율
    # 효율을 위해 (date, hour, station) → congested 룩업 테이블을 미리 만든다
    lookup = df.set_index(["date", "hour", "station"])["congested"].to_dict()

    def _neighbor_ratio(row):
        ns = ADJACENCY.get(row["station"], [])
        if not ns:
            return 0.0
        vals = [lookup.get((row["date"], row["hour"], n)) for n in ns]
        vals = [v for v in vals if v is not None]
        return float(np.mean(vals)) if vals else 0.0

    df["neighbor_congested_ratio"] = df.apply(_neighbor_ratio, axis=1)

    # 역 이름 one-hot 인코딩
    station_dummies = pd.get_dummies(df["station"], prefix="st")
    feat = pd.concat([
        df[["is_weekend", "hour", "prev_hour_total", "neighbor_congested_ratio"]].astype(float),
        station_dummies.astype(float),
    ], axis=1)
    label = df["congested"].astype(int)
    return feat, label


# =============================================================================
# 2. 모델 학습 클래스
# =============================================================================
class CongestionModel:
    """
    AI 보조 예측 모델 래퍼.

    사용 흐름:
        m = CongestionModel(model_type="tree")
        m.fit(df_with_congestion_columns)
        prob = m.predict_proba_for(station="강남", is_weekend=False, hour=18,
                                    prev_total=..., neighbor_ratio=...)
    """

    def __init__(self, model_type: str = "tree", max_depth: int = 6, random_state: int = 42):
        if model_type == "tree":
            self.clf = DecisionTreeClassifier(max_depth=max_depth, random_state=random_state)
        elif model_type == "forest":
            self.clf = RandomForestClassifier(n_estimators=100, max_depth=max_depth,
                                               random_state=random_state)
        else:
            raise ValueError(f"Unknown model_type: {model_type}")
        self.model_type = model_type
        self.feature_columns = None
        self.train_accuracy = None
        self.test_accuracy = None

    def fit(self, df: pd.DataFrame, test_size: float = 0.2):
        """모델 학습. df는 add_congestion_columns()를 거친 데이터여야 함."""
        X, y = build_features(df)
        self.feature_columns = list(X.columns)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )
        self.clf.fit(X_train, y_train)
        self.train_accuracy = accuracy_score(y_train, self.clf.predict(X_train))
        self.test_accuracy = accuracy_score(y_test, self.clf.predict(X_test))
        return self

    def predict_proba_for(self,
                          station: str,
                          is_weekend: bool,
                          hour: int,
                          prev_total: float,
                          neighbor_ratio: float) -> dict:
        """
        하나의 (역·요일·시간) 조건에 대해 혼잡 확률 예측.

        반환:
            congested_prob : AI가 예측한 혼잡 확률 (0~1)
            congested_pred : 0 또는 1 (이진 예측)
        """
        if self.feature_columns is None:
            raise RuntimeError("모델이 아직 학습되지 않았습니다. fit() 먼저 호출하세요.")
        # 피처 벡터 한 행 만들기
        row = {col: 0.0 for col in self.feature_columns}
        row["is_weekend"] = float(bool(is_weekend))
        row["hour"] = float(hour)
        row["prev_hour_total"] = float(prev_total)
        row["neighbor_congested_ratio"] = float(neighbor_ratio)
        st_col = f"st_{station}"
        if st_col in row:
            row[st_col] = 1.0
        else:
            return {"congested_prob": None, "congested_pred": None,
                    "warn": f"학습 데이터에 없는 역: {station}"}
        x = pd.DataFrame([row])[self.feature_columns]
        proba = self.clf.predict_proba(x)[0]
        # 클래스 인덱스 1이 "혼잡"
        if 1 in self.clf.classes_:
            idx = list(self.clf.classes_).index(1)
            prob = float(proba[idx])
        else:
            prob = 0.0
        return {
            "congested_prob": prob,
            "congested_pred": int(prob >= 0.5),
            "warn": None,
        }

    def feature_importance(self, top_k: int = 10) -> list:
        """어떤 피처가 예측에 중요한지 (보고서·발표용)"""
        if self.feature_columns is None:
            return []
        importances = self.clf.feature_importances_
        pairs = sorted(zip(self.feature_columns, importances), key=lambda x: -x[1])
        return pairs[:top_k]
