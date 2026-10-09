#!/usr/bin/env python3
"""What the replacement tokens themselves disclose, on the released PrivacyLens surface.

A placeholder removes a value but announces that one was there. This analysis
measures what the replacement tokens of each condition reveal about a case,
without any model call: the releases are rebuilt exactly as the downstream and
attack suites build them (same conditions, same detectors), and only the tokens
in them are read.

Per case and condition it records:

* the number of token mentions and their labels (typed placeholders carry an
  entity label such as ``PERSON``; the learned detector's carry the generic
  ``PROTECTED``; symbolic tokens carry none);
* for symbolic tokens, how many distinct values were mapped and how many tokens
  recur, since one value always maps to one token within a session, so a
  repeated token tells a reader that two mentions are the same entity. Typed
  placeholders are numbered per mention, so they never link two mentions.

The *signature* of a release is what an observer learns from the tokens alone:
for typed placeholders the count of mentions per label, for symbolic tokens the
sorted occurrence counts of the distinct tokens. The summary reports how many
cases share each signature: a signature held by one case alone singles that
case out among the 493 to anyone who sees only the tokens.

The symbolic namespace in these runs is a hash of the case identifier, kept so
that runs are reproducible; it is excluded from the signature here because a
deployment must draw it at random per session.

Rows are appended per case with flush and fsync and are resumed by
(condition, case).
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import re
import statistics
from pathlib import Path

from mediation_baselines import build_detectors
from privacylens_downstream_suite import PL_DATA, Condition, _train_learned_detector


EXPERIMENTS_DIR = Path(__file__).resolve().parent
ROWS_PATH = EXPERIMENTS_DIR / "placeholder_leakage_rows.csv"
SUMMARY_PATH = EXPERIMENTS_DIR / "placeholder_leakage_summary.csv"
DEFAULT_CONDITIONS = "placeholder:presidio,placeholder:learned_lr,placeholder:gliner_pii,symbolic_late:gliner_pii"
ROW_FIELDS = ["condition", "case", "mentions", "labels", "distinct_tokens", "recurring_tokens", "signature"]
SUMMARY_FIELDS = ["condition", "cases", "cases_with_tokens", "mean_mentions", "distinct_signatures",
                  "unique_signature_cases", "unique_signature_percent", "median_anonymity_set",
                  "cases_with_recurring_token", "recurring_token_percent", "label_counts"]

PLACEHOLDER_RE = re.compile(r"<([A-Z]+)_(\d+)>")
SYMBOLIC_RE = re.compile(r"BPSMAP-[0-9a-z]+-(\d+)")


def describe(kind: str, released: str) -> dict[str, object]:
    if kind == "placeholder":
        labels = collections.Counter(m.group(1) for m in PLACEHOLDER_RE.finditer(released))
        mentions = sum(labels.values())
        signature = ";".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return {"mentions": mentions, "labels": json.dumps(dict(sorted(labels.items()))),
                "distinct_tokens": "", "recurring_tokens": "", "signature": signature}
    counts = collections.Counter(m.group(1) for m in SYMBOLIC_RE.finditer(released))
    occurrences = sorted(counts.values(), reverse=True)
    return {"mentions": sum(occurrences), "labels": "", "distinct_tokens": len(counts),
            "recurring_tokens": sum(1 for c in occurrences if c > 1),
            "signature": ",".join(str(c) for c in occurrences)}


def summarize(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out = []
    for cond in dict.fromkeys(r["condition"] for r in rows):
        sub = [r for r in rows if r["condition"] == cond]
        sizes = collections.Counter(r["signature"] for r in sub)
        unique = sum(1 for r in sub if sizes[r["signature"]] == 1)
        anonymity = [sizes[r["signature"]] for r in sub]
        labels: collections.Counter = collections.Counter()
        for r in sub:
            if r["labels"]:
                labels.update(json.loads(r["labels"]))
        recurring = [r for r in sub if r["recurring_tokens"] not in ("", "0")]
        symbolic = cond.startswith("symbolic")
        out.append({
            "condition": cond, "cases": str(len(sub)),
            "cases_with_tokens": str(sum(1 for r in sub if int(r["mentions"]) > 0)),
            "mean_mentions": f"{statistics.mean(int(r['mentions']) for r in sub):.2f}",
            "distinct_signatures": str(len(sizes)),
            "unique_signature_cases": str(unique),
            "unique_signature_percent": f"{100.0 * unique / len(sub):.1f}",
            "median_anonymity_set": f"{statistics.median(anonymity):g}",
            "cases_with_recurring_token": str(len(recurring)) if symbolic else "",
            "recurring_token_percent": f"{100.0 * len(recurring) / len(sub):.1f}" if symbolic else "",
            "label_counts": json.dumps(dict(labels.most_common())),
        })
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--conditions", default=DEFAULT_CONDITIONS)
    parser.add_argument("--spacy-model", default="en_core_web_lg")
    parser.add_argument("--summarize-only", action="store_true")
    args = parser.parse_args()

    if not args.summarize_only:
        specs = [c.strip() for c in args.conditions.split(",") if c.strip()]
        needed = sorted({s.split(":", 1)[1] for s in specs if ":" in s})
        learned = _train_learned_detector() if "learned_lr" in needed else None
        detectors = {d.key: d for d in build_detectors(needed, learned_weights=learned, spacy_model=args.spacy_model)}
        conditions = [Condition(s, detectors, "http://127.0.0.1:11434", args.spacy_model) for s in specs]
        cases = json.load(open(PL_DATA, encoding="utf-8"))
        done = set()
        if ROWS_PATH.exists():
            with ROWS_PATH.open(encoding="utf-8", newline="") as handle:
                done = {(r["condition"], r["case"]) for r in csv.DictReader(handle)}
        new = not ROWS_PATH.exists()
        with ROWS_PATH.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=ROW_FIELDS)
            if new:
                writer.writeheader()
            for cond in conditions:
                for case in cases:
                    if (cond.spec, case["name"]) in done:
                        continue
                    tr = case["trajectory"]
                    instr_r, traj_r, _mapping, _mode = cond.apply(
                        case["name"], tr.get("user_instruction", ""), tr.get("executable_trajectory", ""))
                    writer.writerow({"condition": cond.spec, "case": case["name"],
                                     **describe(cond.kind if cond.kind == "placeholder" else "symbolic",
                                                f"{instr_r}\n\n{traj_r}")})
                    handle.flush()
                    os.fsync(handle.fileno())
                print(f"[{cond.spec}] done", flush=True)

    with ROWS_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    summary = summarize(rows)
    with SUMMARY_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(summary)
    for s in summary:
        print(f"  {s['condition']:28s} cases {s['cases']}, with tokens {s['cases_with_tokens']}, "
              f"mentions {s['mean_mentions']}, unique signature {s['unique_signature_percent']}% "
              f"(median anonymity set {s['median_anonymity_set']}), recurring token {s['recurring_token_percent'] or '-'}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
