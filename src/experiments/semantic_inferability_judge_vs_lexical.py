#!/usr/bin/env python3
"""Agreement between the language-model judge and the lexical fact-retention flag.

The two automated proxies of inferability are scored against human labels by
``semantic_inferability_agreement.py``, but not against each other. This script
reports their raw agreement and Cohen's kappa on the 240 human-annotated items
(the round-one key plus the extension key, 40 per method) and over all judged
items, overall and per method. Both lexical flags in the records are scored:
the current whole-word flag (``lexical_retained``) and the earlier substring
flag (``lexical_retained_substring``).

Intervals are 95% percentile bootstrap intervals over documents (1,000
resamples, seed 17), because the items of one document are not independent.
Items whose judge reply could not be parsed have an empty ``judge_inferable``
and are excluded.

Reads records only; no model is called. The key files' flags are checked
against the judged rows before anything is written.

Output, next to the records:
``semantic_inferability_judge_vs_lexical_vgpu3090.csv``
"""
from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parent
TAG = "vgpu3090"
ROWS_PATH = EXPERIMENTS_DIR / f"semantic_inferability_rows_{TAG}.csv"
KEY_PATHS = [EXPERIMENTS_DIR / f"semantic_inferability_human_key_{TAG}.csv",
             EXPERIMENTS_DIR / f"semantic_inferability_human_key_extend40_{TAG}.csv"]
OUT_PATH = EXPERIMENTS_DIR / f"semantic_inferability_judge_vs_lexical_{TAG}.csv"
N_BOOT = 1000
SEED = 17
METHODS = ["no_protection", "regex_only", "presidio", "casper_style", "heuristic_mediator", "learned_lr"]
FLAGS = ["lexical_retained", "lexical_retained_substring"]


def read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def cells(pairs: list[tuple[int, int]]) -> list[int]:
    """[judge 0 lex 0, judge 0 lex 1, judge 1 lex 0, judge 1 lex 1]."""
    out = [0, 0, 0, 0]
    for a, b in pairs:
        out[2 * a + b] += 1
    return out


def kappa_from_cells(table: list[int]) -> tuple[float, float]:
    """Cohen's kappa and raw agreement; the same formula as ``semantic_inferability_agreement._kappa``."""
    n = sum(table)
    if n == 0:
        return float("nan"), float("nan")
    observed = (table[0] + table[3]) / n
    expected = ((table[0] + table[1]) * (table[0] + table[2]) + (table[2] + table[3]) * (table[1] + table[3])) / (n * n)
    kappa = (observed - expected) / (1 - expected) if expected < 1 else float("nan")
    return kappa, observed


def bootstrap(items: list[dict], flag: str) -> tuple[list[float], list[float]]:
    """Percentile intervals of raw agreement (%) and kappa over documents."""
    by_doc: dict[str, list[int]] = {}
    for item in items:
        table = by_doc.setdefault(item["doc_id"], [0, 0, 0, 0])
        table[2 * int(item["judge_inferable"]) + int(item[flag])] += 1
    tables = list(by_doc.values())
    rng = random.Random(SEED)
    raw, kap = [], []
    for _ in range(N_BOOT):
        total = [0, 0, 0, 0]
        for _ in range(len(tables)):
            table = tables[rng.randrange(len(tables))]
            for i in range(4):
                total[i] += table[i]
        k, o = kappa_from_cells(total)
        raw.append(100.0 * o)
        if k == k:
            kap.append(k)
    raw.sort()
    kap.sort()
    pick = lambda v, q: v[int(q * (len(v) - 1))] if v else float("nan")
    return [pick(raw, 0.025), pick(raw, 0.975)], [pick(kap, 0.025), pick(kap, 0.975)]


def score(universe: str, method: str, items: list[dict]) -> list[dict]:
    out = []
    for flag in FLAGS:
        table = cells([(int(i["judge_inferable"]), int(i[flag])) for i in items])
        kappa, observed = kappa_from_cells(table)
        raw_ci, kappa_ci = bootstrap(items, flag)
        n = sum(table)
        out.append({
            "universe": universe, "method": method, "lexical_flag": flag, "n": n,
            "documents": len({i["doc_id"] for i in items}),
            "raw_agreement_percent": f"{100.0 * observed:.1f}",
            "raw_agreement_ci": f"[{raw_ci[0]:.1f}, {raw_ci[1]:.1f}]",
            "cohens_kappa": f"{kappa:.3f}" if kappa == kappa else "",
            "cohens_kappa_ci": f"[{kappa_ci[0]:.3f}, {kappa_ci[1]:.3f}]" if kappa == kappa else "",
            "judge_no_lexical_no": table[0], "judge_no_lexical_yes": table[1],
            "judge_yes_lexical_no": table[2], "judge_yes_lexical_yes": table[3],
            "judge_yes_percent": f"{100.0 * (table[2] + table[3]) / n:.1f}",
            "lexical_yes_percent": f"{100.0 * (table[1] + table[3]) / n:.1f}",
        })
    return out


def main() -> int:
    rows = read_rows(ROWS_PATH)
    parsed = [r for r in rows if r["judge_inferable"] != ""]
    index = {(r["method_key"], r["doc_id"], r["fact_index"]): r for r in rows}

    annotated = []
    for path in KEY_PATHS:
        for key in read_rows(path):
            row = index[(key["method_key"], key["doc_id"], key["fact_index"])]
            for field in ["judge_inferable", *FLAGS]:
                if row[field] != key[field]:
                    raise SystemExit(f"{path.name} item {key['item_id']}: {field} disagrees with the judged rows")
            annotated.append(key)

    out = []
    for universe, items in (("human_annotated_240", annotated), ("all_judged", parsed),
                            ("all_judged_excluding_truncated", [r for r in parsed if r["truncated"] == "0"])):
        out += score(universe, "all", items)
        for method in METHODS:
            out += score(universe, method, [i for i in items if i["method_key"] == method])
    with OUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(out[0].keys()))
        writer.writeheader()
        writer.writerows(out)
    print(f"[judge-vs-lexical] {len(rows)} judged rows, {len(parsed)} parsed, {len(annotated)} annotated")
    for r in out:
        print(f"  {r['universe']:<32} {r['method']:<20} {r['lexical_flag']:<28} n={r['n']:>4} "
              f"raw {r['raw_agreement_percent']:>5} {r['raw_agreement_ci']:<15} "
              f"kappa {r['cohens_kappa']:>6} {r['cohens_kappa_ci']:<18} "
              f"[{r['judge_no_lexical_no']},{r['judge_no_lexical_yes']},"
              f"{r['judge_yes_lexical_no']},{r['judge_yes_lexical_yes']}]")
    print(f"wrote {OUT_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
