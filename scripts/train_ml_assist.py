from __future__ import annotations

import csv
from pathlib import Path
from typing import List

import argparse

try:
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
    import joblib
except Exception as e:
    raise SystemExit("Please install scikit-learn, numpy, and joblib to train: pip install scikit-learn numpy joblib")


TARGETS = {
    "gesture": ["Hands Together", "Point Finger", "Hands on Hips", "Thrash Arms", "Outstretched Arms"],
    "shout": ["None", "Encourage", "Demand More", "Focus", "Fire Up", "Praise"],
}


def read_features(csv_path: Path) -> List[dict]:
    rows = []
    with csv_path.open("r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
    return rows


def vec_feature(row: dict, feature_order: List[str]) -> List[float]:
    def num(x):
        try:
            return float(x)
        except Exception:
            return 0.0
    return [num(row.get(k, 0)) for k in feature_order]


def train_model(rows: List[dict], target: str, feature_order: List[str], out_dir: Path):
    X = []
    y = []
    for row in rows:
        if not row.get(target):
            continue
        X.append(vec_feature(row, feature_order))
        y.append(row[target])
    if not X:
        raise SystemExit("No rows with target present; ensure logger collected data and target column exists.")
    X = np.array(X, dtype=float)
    y = np.array(y)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, multi_class="auto")),
    ])
    pipe.fit(X_train, y_train)
    acc = pipe.score(X_test, y_test)
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, out_dir / f"{target}.joblib")
    print(f"Trained {target} model; test accuracy: {acc:.3f}; saved to {out_dir / f'{target}.joblib'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=str, default="data/logs/ml/features.csv")
    parser.add_argument("--out", type=str, default="data/ml")
    parser.add_argument("--target", type=str, choices=["gesture", "shout"], default="gesture")
    args = parser.parse_args()
    rows = read_features(Path(args.csv))
    # Define feature order consistent with domain.ml_assist.FEATURE_COLUMNS
    feature_order = [
        "stage","venue","fav_status","score_state","minute","team_pos","opp_pos","pos_delta",
        "form_team","form_opp","form_delta","xg_for","xg_against","xg_delta","shots_for","shots_against","shots_delta","possession","tier_edge"
    ]
    train_model(rows, args.target, feature_order, Path(args.out))
