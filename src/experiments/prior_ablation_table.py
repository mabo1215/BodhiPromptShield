"""
Generate ablation table values for the paper.
(A) Prior DBN/PB: values from Ma et al. [ma2021privacy] Table 1 and Fig.9 (MTAPBoMa).
(B)--(E): placeholders; optionally run simple baseline on REAEDP data to fill (B)(C)(D)(E).

Usage:
  python -m experiments.prior_ablation_table
  python -m experiments.prior_ablation_table --reaedp C:/source/REAEDP/data --out ablation_table.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

# Prior paper [ma2021privacy] Table 1: MIMIC Clinical Data Sets
# Columns: nu (sampling rate), PPDIFSEA+WECPSSVM, BERT only, WECPPSVM (no PPDIFSEA), Maximum gap
# Source: MTAPBoMa.pdf Table 1 "The comparison of accuracy rate of the algorithms..."
PRIOR_TABLE1_MIMIC = [
    (0.01, 0.8495, 0.8932, 0.8135, 0.0797),
    (0.02, 0.8312, 0.8715, 0.7852, 0.0863),
    (0.03, 0.8117, 0.8514, 0.7623, 0.0891),
    (0.04, 0.7962, 0.8385, 0.7735, 0.0650),
    (0.05, 0.7716, 0.8102, 0.7437, 0.0665),
    (0.06, 0.7595, 0.7824, 0.7161, 0.0663),
    (0.07, 0.7378, 0.7622, 0.6951, 0.0671),
    (0.08, 0.7002, 0.7327, 0.6566, 0.0761),
    (0.09, 0.6718, 0.7145, 0.6312, 0.0833),
]
# Prior paper Fig.9 text: "When the training set classification accuracy of the COVID-19 corpus is 0.90"
# and "MTC has also reached between 0.50 and 0.60"
PRIOR_COVID19_TRAIN_ACC = 0.90
PRIOR_MTC_VAL_RANGE = (0.50, 0.60)


def get_prior_A_for_ablation() -> dict:
    """Return (A) DBN/PB row for paper Table: train acc, val acc, notes."""
    # Representative: nu=0.01 gives val 0.8495 on MIMIC (Table 1)
    nu_01_val = PRIOR_TABLE1_MIMIC[0][1]
    return {
        "config": "A",
        "train_acc": PRIOR_COVID19_TRAIN_ACC,
        "val_acc": nu_01_val,
        "notes": r"COVID-19 train 0.90 (Fig.9); MIMIC val 0.8495 (\nu=0.01, Table 1 [ma2021privacy])",
    }


def run_reaedp_baseline(reaedp_dir: str) -> dict | None:
    """Run a minimal baseline on REAEDP data to get placeholder (B)(C)(D)(E) metrics.
    Returns dict with keys (B),(C),(D),(E) or None if data/sklearn not available.
    """
    try:
        import numpy as np
        from sklearn.model_selection import train_test_split
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score
    except ImportError:
        return None
    csv_path = None
    for name in ["tabular-feature-engineering.csv", "cdc-brfss-2024.csv", "brfss_survey_data_2024.csv"]:
        p = os.path.join(reaedp_dir, name)
        if os.path.isfile(p):
            csv_path = p
            break
    if not csv_path:
        return None
    try:
        import pandas as pd
        df = pd.read_csv(csv_path, nrows=5000)
    except Exception:
        return None
    # Need a target column: pick a numeric one with few unique values for classification
    numeric = df.select_dtypes(include=[np.number]).dropna(how="all")
    if numeric.empty or len(numeric.columns) < 2:
        return None
    y_col = numeric.columns[-1]
    X = numeric.drop(columns=[y_col], errors="ignore").fillna(0)
    y_raw = numeric[y_col]
    # Drop rows with NaN/inf in y; then factorize to integer labels
    valid = np.isfinite(y_raw.values)
    if valid.sum() < 100:
        return None
    y = pd.factorize(y_raw.values[valid])[0]
    X = X.values[valid][: len(y)]
    if len(np.unique(y)) < 2:
        return None
    # If too many classes (e.g. regression-like), binarize by median for proxy classification
    n_unique = len(np.unique(y))
    if n_unique > 20 or n_unique > len(y) // 2:
        y = (y >= np.median(y)).astype(np.intp)
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
    clf = LogisticRegression(max_iter=500, random_state=42)
    clf.fit(X_train, y_train)
    train_acc = accuracy_score(y_train, clf.predict(X_train))
    val_acc = accuracy_score(y_val, clf.predict(X_val))
    # Return same placeholder for (B)(C)(D)(E) as proxy (user will replace with real ablations)
    return {
        "B": (train_acc, val_acc, "Proxy on REAEDP (no boundary)"),
        "C": (train_acc, val_acc, "Proxy on REAEDP (internal center only)"),
        "D": (train_acc, val_acc, "Proxy on REAEDP (ring+center)"),
        "E": (train_acc, val_acc, "Proxy on REAEDP (full); replace with IBPPSVM"),
    }


def main():
    ap = argparse.ArgumentParser(description="Generate ablation table values for paper")
    ap.add_argument("--reaedp", default="", help="Path to REAEDP/data to run placeholder baselines")
    ap.add_argument("--out", default="", help="Output CSV path (default: print to stdout)")
    args = ap.parse_args()

    rows = []
    # (A) From prior paper
    a = get_prior_A_for_ablation()
    rows.append({
        "Config": "(A) DBN/PB",
        "Train_acc": a["train_acc"],
        "Val_acc": a["val_acc"],
        "Notes": a["notes"],
    })

    if args.reaedp and os.path.isdir(args.reaedp):
        reaedp_result = run_reaedp_baseline(args.reaedp)
        if reaedp_result:
            for cfg, (tr, va, note) in reaedp_result.items():
                rows.append({
                    "Config": f"({cfg})" if cfg != "E" else "(E) Full (ours)",
                    "Train_acc": round(tr, 4),
                    "Val_acc": round(va, 4),
                    "Notes": note,
                })
        else:
            for cfg in ["B", "C", "D", "E"]:
                rows.append({"Config": f"({cfg})", "Train_acc": "--", "Val_acc": "--", "Notes": "Placeholder"})
    else:
        for cfg in ["(B)", "(C)", "(D)", "(E) Full (ours)"]:
            rows.append({"Config": cfg, "Train_acc": "--", "Val_acc": "--", "Notes": "Placeholder"})

    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["Config", "Train_acc", "Val_acc", "Notes"])
            w.writeheader()
            w.writerows(rows)
        print("Wrote", args.out)
    else:
        for r in rows:
            print(r)

    # Print LaTeX snippet for (A) row
    print("\n--- (A) row for paper (from prior [ma2021privacy]) ---")
    print(f"(A) DBN/PB~\\cite{{ma2021privacy}} & {a['train_acc']} & {a['val_acc']} & "
          "COVID-19 train (Fig.9); MIMIC val $\\nu=0.01$ (Table~1 \\cite{ma2021privacy}) \\\\")
    return 0


if __name__ == "__main__":
    sys.exit(main())
