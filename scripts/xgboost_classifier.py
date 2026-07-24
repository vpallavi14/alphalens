"""
XGBoost Price Direction Classifier — Week 3
=============================================
Trains an XGBoost multi-class classifier to predict whether each stock
will go UP, DOWN, or stay NEUTRAL over the next 5 trading days.

Label construction:
  future_return = close(t+5) / close(t) - 1
  UP      if future_return >  +2%
  DOWN    if future_return <  -2%
  NEUTRAL otherwise

Features (from feature_engineering.py):
  RSI_14, MACD, MACD_signal, MACD_hist, BB_pct, ATR_14,
  Volatility_20, Momentum_20, Stoch_K, Volume_ratio, OBV,
  VWAP_signal, Price_vs_SMA50, SMA_20, SMA_50, EMA_12, EMA_26

Training strategy:
  - Train on all tickers combined (cross-ticker generalization)
  - Time-aware split: train on older data, test on most recent 20%
    (no data leakage — future rows never appear in training set)
  - 3-fold time-series cross-validation on training set

Output:
  scripts/output/models/xgb_classifier.pkl   — trained model
  scripts/output/xgb_predictions.csv         — latest predictions per ticker
  scripts/output/xgb_feature_importance.csv  — which features matter most

Run:
  pip install xgboost scikit-learn
  python scripts/xgboost_classifier.py
"""

import os
import pickle
import warnings
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

FEATURES_FILE = os.path.join(os.path.dirname(__file__), "output", "features", "all_features.csv")
MODEL_DIR     = os.path.join(os.path.dirname(__file__), "output", "models")
OUTPUT_DIR    = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(MODEL_DIR, exist_ok=True)

# Feature columns to use
FEATURE_COLS = [
    "RSI_14", "MACD", "MACD_signal", "MACD_hist",
    "BB_pct", "ATR_14", "Volatility_20", "Momentum_20",
    "Stoch_K", "Volume_ratio", "VWAP_signal", "Price_vs_SMA50",
    "SMA_20", "SMA_50", "EMA_12", "EMA_26",
]

# Label thresholds
UP_THRESH   =  0.02   # +2%
DOWN_THRESH = -0.02   # -2%
HORIZON     = 5       # predict 5 trading days forward

LABEL_MAP   = {0: "DOWN", 1: "NEUTRAL", 2: "UP"}
LABEL_COLOR = {"UP": "🟢", "DOWN": "🔴", "NEUTRAL": "⚪"}


# ─────────────────────────────────────────────────────────────
# Data preparation
# ─────────────────────────────────────────────────────────────

def build_dataset(df: pd.DataFrame):
    """
    For each ticker, compute the 5-day forward return and assign a label.
    Drops the last HORIZON rows per ticker (no future data to label them).
    """
    rows = []
    for ticker, group in df.groupby("ticker"):
        g = group.sort_values("date").copy()
        g["future_return"] = g["close"].shift(-HORIZON) / g["close"] - 1
        g = g.dropna(subset=["future_return"] + FEATURE_COLS)

        g["label"] = 1  # NEUTRAL
        g.loc[g["future_return"] >  UP_THRESH,   "label"] = 2  # UP
        g.loc[g["future_return"] <  DOWN_THRESH,  "label"] = 0  # DOWN
        rows.append(g)

    return pd.concat(rows, ignore_index=True)


def time_split(df: pd.DataFrame, test_frac=0.20):
    """
    Chronological split — train on older dates, test on recent ones.
    Prevents leakage: model never sees future data during training.
    """
    dates  = sorted(df["date"].unique())
    cutoff = dates[int(len(dates) * (1 - test_frac))]
    train  = df[df["date"] <  cutoff]
    test   = df[df["date"] >= cutoff]
    return train, test, cutoff


# ─────────────────────────────────────────────────────────────
# Model training
# ─────────────────────────────────────────────────────────────

def train_xgb(X_train, y_train):
    from xgboost import XGBClassifier
    model = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric="mlogloss",
        random_state=42,
        verbosity=0,
    )
    model.fit(X_train, y_train)
    return model


def cross_val_scores(df_train: pd.DataFrame, n_folds=3):
    """Time-series cross-validation — each fold uses older data to predict newer."""
    from sklearn.metrics import accuracy_score, classification_report
    from xgboost import XGBClassifier

    dates  = sorted(df_train["date"].unique())
    fold_size = len(dates) // (n_folds + 1)
    accs = []

    for i in range(1, n_folds + 1):
        train_end = dates[fold_size * i]
        val_start = train_end
        val_end   = dates[min(fold_size * (i + 1), len(dates) - 1)]

        fold_train = df_train[df_train["date"] <  train_end]
        fold_val   = df_train[(df_train["date"] >= val_start) & (df_train["date"] < val_end)]

        if fold_train.empty or fold_val.empty:
            continue

        m = XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.05,
                          use_label_encoder=False, eval_metric="mlogloss",
                          random_state=42, verbosity=0)
        m.fit(fold_train[FEATURE_COLS], fold_train["label"])
        preds = m.predict(fold_val[FEATURE_COLS])
        acc = accuracy_score(fold_val["label"], preds)
        accs.append(acc)
        print(f"    Fold {i}: accuracy = {acc:.1%}")

    return np.mean(accs) if accs else 0.0


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main():
    try:
        from xgboost import XGBClassifier
        from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
    except ImportError:
        print("❌ Missing packages. Run: pip install xgboost scikit-learn")
        return

    print(f"\nXGBoost Price Direction Classifier")
    print("=" * 60)

    # 1. Load and prepare data
    print(f"\n1. Loading features...")
    raw = pd.read_csv(FEATURES_FILE)
    df  = build_dataset(raw)
    print(f"   {len(df):,} labeled rows after adding 5-day forward returns")

    label_counts = df["label"].value_counts().sort_index()
    for code, name in LABEL_MAP.items():
        pct = label_counts.get(code, 0) / len(df) * 100
        print(f"   {LABEL_COLOR[name]} {name:<8} {label_counts.get(code, 0):>5} rows  ({pct:.1f}%)")

    # 2. Time-aware split
    print(f"\n2. Chronological train/test split (80/20)...")
    train, test, cutoff = time_split(df)
    print(f"   Train: {train['date'].min()} → {cutoff}  ({len(train):,} rows)")
    print(f"   Test:  {cutoff} → {test['date'].max()}   ({len(test):,} rows)")

    X_train, y_train = train[FEATURE_COLS], train["label"]
    X_test,  y_test  = test[FEATURE_COLS],  test["label"]

    # 3. Cross-validation
    print(f"\n3. Time-series cross-validation (3 folds)...")
    cv_acc = cross_val_scores(train)
    print(f"   Mean CV accuracy: {cv_acc:.1%}")

    # 4. Train final model
    print(f"\n4. Training final XGBoost model on full training set...")
    model = train_xgb(X_train, y_train)

    # 5. Evaluate on hold-out test set
    print(f"\n5. Evaluating on hold-out test set...")
    preds     = model.predict(X_test)
    test_acc  = accuracy_score(y_test, preds)
    print(f"   Test accuracy: {test_acc:.1%}")

    # Class-level report
    print(f"\n   Per-class breakdown:")
    report = classification_report(y_test, preds,
                                   target_names=["DOWN", "NEUTRAL", "UP"],
                                   output_dict=True)
    for cls in ["DOWN", "NEUTRAL", "UP"]:
        m = report[cls]
        print(f"   {LABEL_COLOR[cls]} {cls:<8}  precision={m['precision']:.0%}  "
              f"recall={m['recall']:.0%}  f1={m['f1-score']:.0%}")

    # Confusion matrix
    cm = confusion_matrix(y_test, preds)
    print(f"\n   Confusion matrix (rows=actual, cols=predicted):")
    print(f"              DOWN  NEUT    UP")
    for i, row in enumerate(cm):
        print(f"   {LABEL_MAP[i]:<8}  {row[0]:>4}  {row[1]:>4}  {row[2]:>4}")

    # 6. Feature importance
    print(f"\n6. Top 10 most important features:")
    importance = pd.DataFrame({
        "feature":   FEATURE_COLS,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=False)

    for _, row in importance.head(10).iterrows():
        bar = "█" * int(row["importance"] * 200)
        print(f"   {row['feature']:<20} {row['importance']:.4f}  {bar}")

    # 7. Predict latest date per ticker
    print(f"\n7. Predictions for latest available date per ticker:")
    print("-" * 60)

    latest_rows = []
    for ticker, group in raw.groupby("ticker"):
        g = group.sort_values("date")
        latest = g.dropna(subset=FEATURE_COLS).iloc[-1]
        latest_rows.append(latest)

    latest_df = pd.DataFrame(latest_rows)
    X_latest  = latest_df[FEATURE_COLS]

    pred_labels  = model.predict(X_latest)
    pred_proba   = model.predict_proba(X_latest)   # shape: (n, 3)

    predictions = []
    print(f"\n{'Ticker':<8} {'Signal':<10} {'DOWN%':>7} {'NEUT%':>7} {'UP%':>7}  {'Confidence':>10}")
    print("-" * 60)

    for i, (ticker, label_code) in enumerate(zip(latest_df["ticker"], pred_labels)):
        label     = LABEL_MAP[label_code]
        proba     = pred_proba[i]
        down_p, neu_p, up_p = proba[0], proba[1], proba[2]
        confidence = max(proba)

        print(f"{ticker:<8} {LABEL_COLOR[label]} {label:<8} "
              f"{down_p*100:>6.1f}% {neu_p*100:>6.1f}% {up_p*100:>6.1f}%  "
              f"{confidence*100:>9.1f}%")

        predictions.append({
            "ticker":       ticker,
            "date":         latest_df.iloc[i]["date"],
            "prediction":   label,
            "confidence":   round(float(confidence), 4),
            "prob_down":    round(float(down_p), 4),
            "prob_neutral": round(float(neu_p), 4),
            "prob_up":      round(float(up_p), 4),
            "horizon_days": HORIZON,
        })

    # 8. Save outputs
    model_path = os.path.join(MODEL_DIR, "xgb_classifier.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    pred_path = os.path.join(OUTPUT_DIR, "xgb_predictions.csv")
    pd.DataFrame(predictions).to_csv(pred_path, index=False)

    imp_path = os.path.join(OUTPUT_DIR, "xgb_feature_importance.csv")
    importance.to_csv(imp_path, index=False)

    print(f"\n✅ Saved:")
    print(f"   {model_path}  (trained model)")
    print(f"   {pred_path}   (predictions)")
    print(f"   {imp_path}")
    print(f"\n   Test accuracy: {test_acc:.1%}  |  CV accuracy: {cv_acc:.1%}")
    print(f"   Note: ~50-55% accuracy is typical for stock direction prediction.")
    print(f"   The edge comes from combining this with AlphaScore + SocialRank.")


if __name__ == "__main__":
    main()
