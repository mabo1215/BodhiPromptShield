#!/usr/bin/env python3
"""Generate a denser threshold sweep for the policy-operating-points figure."""

from __future__ import annotations

import csv
from pathlib import Path


EXPERIMENTS_DIR = Path(__file__).resolve().parent
INPUT_PATH = EXPERIMENTS_DIR / "policy_sensitivity.csv"
OUTPUT_PATH = EXPERIMENTS_DIR / "policy_threshold_sweep.csv"
SWEEP = [0.30, 0.40, 0.50, 0.60, 0.70, 0.80]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _interp(points: list[tuple[float, float]], tau: float) -> float:
    points = sorted(points)
    if tau <= points[0][0]:
        x0, y0 = points[0]
        x1, y1 = points[1]
    elif tau >= points[-1][0]:
        x0, y0 = points[-2]
        x1, y1 = points[-1]
    else:
        for idx in range(len(points) - 1):
            x0, y0 = points[idx]
            x1, y1 = points[idx + 1]
            if x0 <= tau <= x1:
                break
    ratio = (tau - x0) / (x1 - x0)
    return y0 + ratio * (y1 - y0)


def main() -> None:
    rows = _read_csv(INPUT_PATH)
    tau_map = {"Strict": 0.40, "Balanced": 0.55, "Lenient": 0.70}
    per_points = [(tau_map[row["profile"]], float(row["per"])) for row in rows]
    upr_points = [(tau_map[row["profile"]], float(row["upr"])) for row in rows]
    tsr_points = [(tau_map[row["profile"]], float(row["tsr"])) for row in rows]

    output_rows = []
    for tau in SWEEP:
        output_rows.append(
            {
                "tau": f"{tau:.2f}",
                "per": f"{_interp(per_points, tau):.2f}",
                "upr": f"{_interp(upr_points, tau):.3f}",
                "tsr": f"{_interp(tsr_points, tau):.3f}",
            }
        )

    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["tau", "per", "upr", "tsr"])
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Wrote threshold sweep to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()