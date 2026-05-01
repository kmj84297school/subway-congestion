"""AI 모델 학습 및 예측 테스트"""
import sys
sys.path.insert(0, "/home/claude/subway_project")
import pandas as pd
from app.core.stats import add_congestion_columns
from app.core.model import CongestionModel

df = pd.read_csv("/home/claude/subway_project/data/subway_sample.csv")
df = add_congestion_columns(df)

print("=" * 60)
print("의사결정나무 학습")
print("=" * 60)
m = CongestionModel(model_type="tree", max_depth=6).fit(df)
print(f"  훈련 정확도: {m.train_accuracy:.3f}")
print(f"  테스트 정확도: {m.test_accuracy:.3f}")

print("\n[중요한 피처 Top 6]")
for name, imp in m.feature_importance(top_k=6):
    print(f"  {name:<32s} {imp:.4f}")

print("\n[예측 데모: 강남 평일 18시]")
# 직전 시간대(17시) 이용량과 인접 역 혼잡 비율을 데이터에서 가져옴
sample_row = df[(df.station=="강남") & (~df.is_weekend) & (df.hour==18)].iloc[0]
prev = df[(df.station=="강남") & (df.date==sample_row["date"]) & (df.hour==17)]["total"].values[0]
res = m.predict_proba_for(
    station="강남", is_weekend=False, hour=18,
    prev_total=prev, neighbor_ratio=0.5
)
print(f"  AI 예측 혼잡 확률: {res['congested_prob']:.3f}")
print(f"  AI 예측 (이진): {'혼잡' if res['congested_pred']==1 else '비혼잡'}")

print("\n" + "=" * 60)
print("랜덤포레스트 학습 (옵션)")
print("=" * 60)
m2 = CongestionModel(model_type="forest", max_depth=8).fit(df)
print(f"  훈련 정확도: {m2.train_accuracy:.3f}")
print(f"  테스트 정확도: {m2.test_accuracy:.3f}")
