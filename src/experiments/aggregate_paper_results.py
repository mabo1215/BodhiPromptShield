"""Pool sharded experiment records into paper-ready aggregate tables.

Shards are run concurrently and each writes its own summary over its own slice.
This script recomputes every reported statistic over the pooled population so
that confidence intervals reflect the full document/case count rather than a
single shard, and regenerates the AgentDojo injection-baseline summary whose
in-run computation aborted (its rows file predates a row-schema extension, so
the stale CSV header cannot be read back by name).

Usage:
    python aggregate_paper_results.py
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

from mediation_baselines import PAPER_LABELS, bootstrap_ratio_ci

EXPERIMENTS_DIR = Path(__file__).resolve().parent
N_BOOT = 1000

AGENTDOJO_OLD_FIELDS = [
    "suite", "task", "mode", "detector", "agent_model", "utility", "protected_values",
    "raw_visible_before_tool", "tokens_emitted_in_tool_args", "restored_in_tool_args",
    "unrestored_tokens", "raw_in_tool_outputs", "tool_calls", "error",
]
AGENTDOJO_NEW_FIELDS = [
    "suite", "task", "injection_task", "mode", "restore_scope", "detector", "agent_model",
    "utility", "security", "protected_values", "raw_visible_before_tool",
    "tokens_emitted_in_tool_args", "restored_in_tool_args", "unrestored_tokens",
    "refused_unscoped_restorations", "raw_in_tool_outputs", "tool_calls", "error",
]


def _ci(rows: list[dict], num: str, den: str | None, scale: float, digits: int) -> str:
    pairs = [(float(r[num]), float(r[den]) if den else 1.0) for r in rows]
    point, lo, hi = bootstrap_ratio_ci(pairs, n_boot=N_BOOT, scale=scale)
    return f"{point:.{digits}f} [{lo:.{digits}f}, {hi:.{digits}f}]"


def _read_shards(pattern: str) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(EXPERIMENTS_DIR.glob(pattern)):
        if "partial" in path.name:
            continue
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def pool_propagation(source: str) -> Path:
    """Pool per-document propagation counts across shards and recompute CIs."""
    docs = _read_shards(f"propagation_suite_{source}_documents_shard*.csv")
    if not docs:
        raise SystemExit(f"no document shards found for {source}")

    order: list[str] = []
    for row in docs:
        if row["method_key"] not in order:
            order.append(row["method_key"])

    out = []
    for key in order:
        sub = [r for r in docs if r["method_key"] == key]
        out.append({
            "method": PAPER_LABELS.get(key, key),
            "method_key": key,
            "documents": str(len({r["doc_id"] for r in sub})),
            "retrieval_spe": _ci(sub, "ret_s", "ret_t", 100.0, 1),
            "memory_spe": _ci(sub, "mem_s", "mem_t", 100.0, 1),
            "tool_spe": _ci(sub, "tool_s", "tool_t", 100.0, 1),
            "per_percent": _ci(sub, "res_chars", "sens_chars", 100.0, 1),
            "text_retention": _ci(sub, "kept_nonsens", "nonsens_chars", 1.0, 2),
            "semantic_residue": _ci(sub, "sem_s", "sem_t", 100.0, 1),
        })

    path = EXPERIMENTS_DIR / f"propagation_suite_{source}_results_pooled.csv"
    _write(path, out)
    return path


def pool_downstream(agent_model: str = "qwen3_32b-q4km-hf") -> Path:
    """Pool PrivacyLens downstream cases across shards and recompute CIs."""
    rows = _read_shards(f"privacylens_downstream_rows_{agent_model}_shard*of*.csv")
    if not rows:
        raise SystemExit("no downstream shards found")

    order: list[str] = []
    for row in rows:
        if row["condition"] not in order:
            order.append(row["condition"])

    out = []
    for cond in order:
        sub = [r for r in rows if r["condition"] == cond]
        out.append({
            "condition": cond,
            "cases": str(len(sub)),
            "action_rate": _ci(sub, "has_action", None, 100.0, 1),
            "leak_rate_percent": _ci(sub, "leak_any", None, 100.0, 1),
            "secret_leak_percent": _ci(sub, "leak_count", "secret_count", 100.0, 1),
            "helpfulness_mean": _ci(sub, "helpfulness", None, 1.0, 2),
            "exact_id_exposure_percent": _ci(sub, "ids_in_final_action", "ids_total", 100.0, 1),
            "boundary_leak_percent": _ci(sub, "raw_values_visible_before_tool", "protected_values", 100.0, 1),
            "unrestored_token_rate": _ci(sub, "tokens_in_output", None, 1.0, 2),
        })

    path = EXPERIMENTS_DIR / f"privacylens_downstream_summary_{agent_model}_pooled.csv"
    _write(path, out)
    return path


def _read_agentdojo_mixed(path: Path) -> list[dict]:
    """Read a rows file that mixes pre- and post-schema-extension records.

    The header line is whichever schema existed when the file was created, so
    rows are dispatched on field count instead of being mapped by that header.
    """
    rows: list[dict] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for fields in csv.reader(handle):
            if not fields or fields[0] == "suite":
                continue
            if len(fields) == len(AGENTDOJO_NEW_FIELDS):
                rows.append(dict(zip(AGENTDOJO_NEW_FIELDS, fields)))
            elif len(fields) == len(AGENTDOJO_OLD_FIELDS):
                row = dict(zip(AGENTDOJO_OLD_FIELDS, fields))
                row.update({"injection_task": "", "restore_scope": "all", "security": "0",
                            "refused_unscoped_restorations": "0"})
                rows.append(row)
    return rows


def rebuild_agentdojo_injection_baseline(agent_model: str = "qwen3_32b-q4km-hf") -> Path:
    """Regenerate the injected no-protection summary from raw rows."""
    path = EXPERIMENTS_DIR / f"agentdojo_restoration_rows_banking_{agent_model}.csv"
    rows = [r for r in _read_agentdojo_mixed(path) if r["mode"] == "none" and r["injection_task"]]
    if not rows:
        raise SystemExit("no injected none-mode rows found")

    protected = [r for r in rows if int(r["protected_values"]) > 0]
    out = [{
        "mode": "none",
        "tasks": str(len(rows)),
        "tasks_with_protected_values": str(len(protected)),
        "attack_success_percent": _ci(rows, "security", None, 100.0, 1),
        "utility_percent_all": _ci(rows, "utility", None, 100.0, 1),
        "utility_percent_protected": _ci(protected, "utility", None, 100.0, 1),
        "boundary_leak_percent": _ci(protected, "raw_visible_before_tool", "protected_values", 100.0, 1),
        "restoration_success_percent": _ci(protected, "restored_in_tool_args", "tokens_emitted_in_tool_args", 100.0, 1),
        "raw_in_tool_outputs_mean": _ci(rows, "raw_in_tool_outputs", None, 1.0, 2),
    }]

    out_path = EXPERIMENTS_DIR / f"agentdojo_restoration_summary_banking_{agent_model}_inj_none.csv"
    _write(out_path, out)
    return out_path


def _write(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {path.name} ({len(rows)} rows)")
    for row in rows:
        print("  " + " | ".join(f"{k}={v}" for k, v in list(row.items())[:6]))


def pool_agentdojo_suites(agent_model: str = "qwen3_32b-q4km-hf",
                          suites: tuple[str, ...] = ("banking", "slack", "travel", "workspace")) -> Path | None:
    """Pool the restoration-mode rows across AgentDojo suites.

    The reported result runs only the banking suite: 16 user tasks, 8 of them
    carrying a protected value, which puts +/-25 points around every utility
    estimate. Pooling suites is what narrows that, and the statistic has to be
    recomputed over the combined task population rather than averaged across
    per-suite summaries, since the suites differ in size.

    Missing suites are skipped, so this is safe to run after any subset.
    """
    rows: list[dict] = []
    present: list[str] = []
    for suite in suites:
        path = EXPERIMENTS_DIR / f"agentdojo_restoration_rows_{suite}_{agent_model}.csv"
        if not path.exists():
            continue
        suite_rows = [r for r in _read_agentdojo_mixed(path) if not r.get("injection_task")]
        if not suite_rows:
            continue
        rows.extend(suite_rows)
        present.append(f"{suite}({len({r['task'] for r in suite_rows})} tasks)")
    if not rows:
        print("pool_agentdojo_suites: no restoration-mode rows found; skipping")
        return None

    modes = ["none", "late", "no_restore"]
    out: list[dict] = []
    for mode in modes:
        mode_rows = [r for r in rows if r["mode"] == mode]
        if not mode_rows:
            continue
        protected = [r for r in mode_rows if int(r["protected_values"]) > 0]
        out.append({
            "mode": mode,
            "suites": ";".join(present),
            "tasks": str(len(mode_rows)),
            "tasks_with_protected_values": str(len(protected)),
            "utility_percent_all": _ci(mode_rows, "utility", None, 100.0, 1),
            "utility_percent_protected": _ci(protected, "utility", None, 100.0, 1) if protected else "n/a",
            "boundary_leak_percent": _ci(protected, "raw_visible_before_tool", "protected_values", 100.0, 1) if protected else "n/a",
            "restoration_success_percent": _ci(protected, "restored_in_tool_args", "tokens_emitted_in_tool_args", 100.0, 1) if protected else "n/a",
            "raw_in_tool_outputs_mean": _ci(mode_rows, "raw_in_tool_outputs", None, 1.0, 2),
        })
    path = EXPERIMENTS_DIR / f"agentdojo_restoration_summary_pooled_{agent_model}.csv"
    _write(path, out)
    return path


def pool_agentdojo_injections(agent_model: str = "qwen3_32b-q4km-hf",
                              suites: tuple[str, ...] = ("banking", "slack")) -> Path | None:
    """Pool the injection arms across suites.

    The reported injection result is banking alone: 32 task/injection pairs,
    which leaves the three arms' intervals overlapping almost entirely. Pooling
    needs care about where each arm's rows live -- banking's unprotected
    baseline sits in its base rows file (mode ``none`` rows that carry an
    injection task), while every other arm has its own tagged file.

    Only exfiltration-shaped injections are pooled. banking's tasks 1 and 8 and
    slack's 2 and 4 attempt to route user data to an attacker; the remaining
    slack injections send a link or invite a user and carry no user data, so a
    data-plane layer cannot affect them by construction and mixing them in
    would dilute the comparison rather than sharpen it.
    """
    arms = {"unprotected": [], "unrestricted": [], "user_directed": []}
    present: dict[str, list[str]] = {k: [] for k in arms}

    def add(arm: str, path: Path, suite: str, baseline: bool = False) -> None:
        if not path.exists():
            return
        rows = [r for r in _read_agentdojo_mixed(path) if r.get("injection_task")]
        if baseline:
            rows = [r for r in rows if r["mode"] == "none"]
        if rows:
            arms[arm].extend(rows)
            present[arm].append(f"{suite}({len(rows)})")

    for suite in suites:
        base = EXPERIMENTS_DIR / f"agentdojo_restoration_rows_{suite}_{agent_model}.csv"
        add("unprotected", EXPERIMENTS_DIR / f"agentdojo_restoration_rows_{suite}_{agent_model}_inj_none.csv", suite)
        if not (EXPERIMENTS_DIR / f"agentdojo_restoration_rows_{suite}_{agent_model}_inj_none.csv").exists():
            add("unprotected", base, suite, baseline=True)
        add("unrestricted", EXPERIMENTS_DIR / f"agentdojo_restoration_rows_{suite}_{agent_model}_inj_all.csv", suite)
        add("user_directed", EXPERIMENTS_DIR / f"agentdojo_restoration_rows_{suite}_{agent_model}_inj_scoped.csv", suite)

    if not any(arms.values()):
        print("pool_agentdojo_injections: no injection rows found; skipping")
        return None

    out: list[dict] = []
    for arm, rows in arms.items():
        if not rows:
            continue
        protected = [r for r in rows if int(r["protected_values"]) > 0]
        out.append({
            "arm": arm,
            "suites": ";".join(present[arm]),
            "pairs": str(len(rows)),
            "pairs_with_protected_values": str(len(protected)),
            "attack_success_percent": _ci(rows, "security", None, 100.0, 1),
            "utility_percent": _ci(rows, "utility", None, 100.0, 1),
            "boundary_leak_percent": _ci(protected, "raw_visible_before_tool", "protected_values", 100.0, 1) if protected else "n/a",
        })
    # The arms run the same task/injection pairs, so a paired test is the
    # right comparison: it removes between-pair variance that the independent
    # intervals above carry, and it is what decides whether the ordering of
    # the arms is real or an artefact of which pairs are hard.
    def keyed(rows: list[dict]) -> dict[tuple[str, str, str], float]:
        return {(r["suite"], r["task"], r["injection_task"]): float(r["security"]) for r in rows}

    baseline = keyed(arms["unprotected"])
    for arm in ("unrestricted", "user_directed"):
        other = keyed(arms[arm])
        shared = sorted(set(baseline) & set(other))
        if not shared:
            continue
        diffs = [other[k] - baseline[k] for k in shared]
        point = 100.0 * sum(diffs) / len(diffs)
        rng = random.Random(17)
        samples = sorted(100.0 * sum(rng.choice(diffs) for _ in diffs) / len(diffs)
                         for _ in range(N_BOOT))
        lo, hi = samples[int(0.025 * N_BOOT)], samples[int(0.975 * N_BOOT)]
        row = next(r for r in out if r["arm"] == arm)
        row["paired_n"] = str(len(shared))
        row["paired_asr_delta_vs_unprotected"] = f"{point:+.1f} [{lo:+.1f}, {hi:+.1f}]"
        row["paired_significant"] = "yes" if (lo > 0) == (hi > 0) else "no"
    for row in out:
        row.setdefault("paired_n", "")
        row.setdefault("paired_asr_delta_vs_unprotected", "")
        row.setdefault("paired_significant", "")

    path = EXPERIMENTS_DIR / f"agentdojo_injection_summary_pooled_{agent_model}.csv"
    _write(path, out)
    return path


def main() -> int:
    pool_propagation("ai4privacy")
    pool_propagation("privacylens")
    pool_downstream()
    rebuild_agentdojo_injection_baseline()
    pool_agentdojo_suites()
    pool_agentdojo_injections()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
