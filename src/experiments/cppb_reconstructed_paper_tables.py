#!/usr/bin/env python3
"""Turn the reconstructed CPPB measurement into the four paper-facing CSVs.

``cppb_reconstructed_measurement.py`` writes a summary, a policy sweep, and a
latency table keyed by internal method names.  The table builders in
``fill_paper_tables.py`` read differently-shaped files keyed by paper labels.
This converts the former into the latter.

The outputs carry a ``_reconstructed`` suffix and are written beside the legacy
files rather than over them.  The legacy CSVs are the only surviving trace of
the original CPPB run -- the prompts behind them no longer exist -- so they are
kept as a record even though the manuscript now reports these numbers instead.

The policy profiles are read off the measured sweep at their own thresholds
rather than interpolated: strict is tau 0.40, balanced 0.55, lenient 0.70, and
each was run.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parent

# Internal method key -> the label the paper's tables print.
PAPER_LABELS = {
    "no_protection": "No protection",
    "regex_only": "Regex-only",
    "capitalization_heuristic": "Capitalization heuristic",
    "generic_deid": "Generic de-identification",
    "enterprise_staged": "Enterprise staged redaction",
    "proposed_abstraction": "Proposed (semantic abstraction)",
    "proposed_utility_constrained": "Proposed (utility-constrained)",
}
# The order the appendix tables list them in.
METHOD_ORDER = list(PAPER_LABELS)

# Latency rows name pipelines rather than detectors, so they carry their own
# labels; the mediation cost of a method is the cost of the pipeline it is.
LATENCY_LABELS = {
    "no_protection": "Raw prompting (no middleware)",
    "regex_only": "Regex-only redaction",
    "capitalization_heuristic": "Capitalization heuristic",
    "generic_deid": "Generic de-identification",
    "enterprise_staged": "Enterprise staged redaction",
    "proposed_utility_constrained": "Proposed (policy-aware balanced)",
}

PROFILE_TAUS = [("Lenient", "0.70"), ("Balanced", "0.55"), ("Strict", "0.40")]


def _read(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        out.flush()
        os.fsync(out.fileno())
    print(f"wrote {path.name} ({len(rows)} rows)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--agent", default="qwen3_32b-q4km-hf",
                        help="agent tag as it appears in the measurement filenames")
    args = parser.parse_args()

    summary_path = EXPERIMENTS_DIR / f"cppb_reconstructed_summary_{args.agent}.csv"
    sweep_path = EXPERIMENTS_DIR / f"cppb_reconstructed_policy_sweep_{args.agent}.csv"
    latency_path = EXPERIMENTS_DIR / f"cppb_reconstructed_latency_{args.agent}.csv"
    for path in (summary_path, sweep_path, latency_path):
        if not path.exists():
            print(f"missing input: {path.name}", file=sys.stderr)
            return 1

    summary = {r["method"]: r for r in _read(summary_path)}
    sweep = {r["tau"]: r for r in _read(sweep_path)}
    latency = {r["method"]: r for r in _read(latency_path)}

    missing = [k for k in METHOD_ORDER if k not in summary]
    if missing:
        print(f"summary is missing methods: {', '.join(missing)}", file=sys.stderr)
        return 1

    # tab:per and tab:utility both read this one file.
    _write(EXPERIMENTS_DIR / "prompt_method_comparison_reconstructed.csv",
           ["method", "per", "ac", "tsr", "per_ci_low", "per_ci_high", "prompts"],
           [{"method": PAPER_LABELS[k], "per": summary[k]["per"],
             "ac": summary[k]["ac"], "tsr": summary[k]["tsr"],
             "per_ci_low": summary[k]["per_ci_low"], "per_ci_high": summary[k]["per_ci_high"],
             "prompts": summary[k]["prompts"]}
            for k in METHOD_ORDER])

    # tab:pi_sensitivity: each profile is its own measured operating point.
    profile_rows = []
    for profile, tau in PROFILE_TAUS:
        if tau not in sweep:
            print(f"sweep is missing tau {tau} for the {profile} profile", file=sys.stderr)
            return 1
        row = sweep[tau]
        profile_rows.append({"profile": profile, "per": row["per"],
                             "upr": row["ac"], "tsr": row["tsr"], "tau": tau})
    _write(EXPERIMENTS_DIR / "policy_sensitivity_reconstructed.csv",
           ["profile", "per", "upr", "tsr", "tau"], profile_rows)

    # The figure's sweep, every point of it run rather than interpolated.
    _write(EXPERIMENTS_DIR / "policy_threshold_sweep_reconstructed.csv",
           ["tau", "per", "upr", "tsr"],
           [{"tau": tau, "per": sweep[tau]["per"], "upr": sweep[tau]["ac"], "tsr": sweep[tau]["tsr"]}
            for tau in sorted(sweep, key=float)])

    _write(EXPERIMENTS_DIR / "latency_overhead_reconstructed.csv",
           ["pipeline", "mean_ms", "p95_ms"],
           [{"pipeline": LATENCY_LABELS[k], "mean_ms": latency[k]["mean_ms"],
             "p95_ms": latency[k]["p95_ms"]}
            for k in LATENCY_LABELS if k in latency])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
