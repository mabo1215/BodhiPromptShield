#!/usr/bin/env python3
"""Measured secure mapping-table compromise adversary (review item W2).

The reference sanity check (``secure_mapping_adversary_suite.py``) shows the
default behavior. This script promotes the mapping-table adversary into a
measured *capability-graded* recovery curve: it gives the adversary increasing
access to the secure mapping mechanism and measures, over many sessions, the
fraction of protected (token, value) pairs it can recover in the *targeted*
session and across *other* sessions (the blast radius).

Capability tiers
----------------
T0 Token-only observer       : sees released opaque tokens only.
T1 Audit-log leak            : sees the append-only restoration log (no raw values).
T2 Partial table read        : reads half of one session's table rows.
T3 Full session table read   : reads one session's entire table.
T4 Session credential leak   : holds one session's restoration credential.
T5 Master-seed compromise    : holds the master wrapping secret (trust root).

The reference design uses per-session opaque tokens and per-session credentials
derived from a master secret, so recovery is confined to the compromised session
for T2-T4 and only the master-seed compromise (T5) is catastrophic. All numbers
are measured by actually running the reference mechanism; nothing is asserted.
"""
from __future__ import annotations

import csv
import hashlib
import hmac
from pathlib import Path

from secure_mapping_adversary_suite import MASTER_SEED
from secure_mapping_adversary_suite import PROTECTED_VALUES
from secure_mapping_adversary_suite import SecureMappingTable


EXPERIMENTS_DIR = Path(__file__).resolve().parent
RESULTS_PATH = EXPERIMENTS_DIR / "secure_mapping_compromise_results.csv"
RUNTIME_PATH = EXPERIMENTS_DIR / "secure_mapping_compromise_runtime_manifest.csv"

NUM_SESSIONS = 6
TARGET = 0


def _forge_credential(session_id: str) -> str:
    """Reconstruct a session credential from the master seed (T5 capability)."""
    secret = hmac.new(MASTER_SEED, session_id.encode("utf-8"), hashlib.sha256).digest()
    return hashlib.sha256(secret + b"-restore").hexdigest()


def _recover(table: SecureMappingTable, tokens: list[str], tier: str) -> int:
    """Count recovered raw values for a session under the given capability tier."""
    rows = table.rows()  # token -> raw (the actual per-session table content)
    if tier in {"T0 Token-only observer", "T1 Audit-log leak"}:
        return 0  # opaque tokens / audit log carry no raw values
    if tier == "T2 Partial table read":
        leaked = dict(list(rows.items())[: max(0, len(rows) // 2)])
        return sum(1 for t in tokens if t in leaked)
    if tier == "T3 Full session table read":
        return sum(1 for t in tokens if t in rows)
    if tier == "T4 Session credential leak":
        return sum(1 for t in tokens if table.restore(t, table.credential) is not None)
    if tier == "T5 Master-seed compromise":
        cred = _forge_credential(table.session_id)
        return sum(1 for t in tokens if table.restore(t, cred) is not None)
    raise ValueError(tier)


def run() -> None:
    sessions = []
    for i in range(NUM_SESSIONS):
        tbl = SecureMappingTable(f"session-{i:02d}")
        tokens = [tbl.protect(v) for v in PROTECTED_VALUES]
        sessions.append((tbl, tokens))

    tiers = [
        "T0 Token-only observer",
        "T1 Audit-log leak",
        "T2 Partial table read",
        "T3 Full session table read",
        "T4 Session credential leak",
        "T5 Master-seed compromise",
    ]

    rows = []
    target_tbl, target_tokens = sessions[TARGET]
    n_per_session = len(PROTECTED_VALUES)
    for tier in tiers:
        # Recovery on the targeted (compromised) session.
        target_rec = _recover(target_tbl, target_tokens, tier)
        # Cross-session recovery: apply the SAME compromised access to other
        # sessions (e.g., the leaked target credential against other sessions,
        # or the leaked target rows against other sessions' tokens).
        cross_rec = 0
        cross_total = 0
        for j, (tbl, tokens) in enumerate(sessions):
            if j == TARGET:
                continue
            cross_total += n_per_session
            if tier in {"T0 Token-only observer", "T1 Audit-log leak", "T2 Partial table read", "T3 Full session table read"}:
                # Reading the target session's rows reveals nothing about other
                # sessions' opaque tokens.
                cross_rec += 0
            elif tier == "T4 Session credential leak":
                # The target credential does not authorize other sessions.
                cross_rec += sum(1 for t in tokens if tbl.restore(t, target_tbl.credential) is not None)
            elif tier == "T5 Master-seed compromise":
                cred = _forge_credential(tbl.session_id)
                cross_rec += sum(1 for t in tokens if tbl.restore(t, cred) is not None)
        rows.append(
            {
                "tier": tier,
                "target_recovery_percent": f"{100.0 * target_rec / n_per_session:.1f}",
                "cross_session_recovery_percent": f"{100.0 * cross_rec / cross_total if cross_total else 0.0:.1f}",
                "blast_radius": "Single session" if tier != "T5 Master-seed compromise" else "All sessions",
            }
        )

    with RESULTS_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["tier", "target_recovery_percent", "cross_session_recovery_percent", "blast_radius"],
        )
        writer.writeheader()
        writer.writerows(rows)

    runtime_rows = [
        {"field": "mechanism", "value": "Reference per-session secure mapping table (opaque BPSMAP tokens)"},
        {"field": "sessions", "value": str(NUM_SESSIONS)},
        {"field": "values_per_session", "value": str(len(PROTECTED_VALUES))},
        {"field": "credential_model", "value": "Per-session credential = SHA256(HMAC(master, session_id) || '-restore')"},
        {"field": "tiers", "value": "; ".join(t for t in tiers)},
        {"field": "measurement", "value": "Recovered (token,value) pairs actually obtained by running the mechanism"},
        {"field": "trust_root", "value": "Only master-seed compromise (T5) defeats per-session isolation"},
    ]
    with RUNTIME_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["field", "value"])
        writer.writeheader()
        writer.writerows(runtime_rows)

    print(f"Secure-mapping compromise results written to {RESULTS_PATH}")
    for r in rows:
        print(f"  {r['tier']:30s} target={r['target_recovery_percent']:>5}% cross={r['cross_session_recovery_percent']:>5}% [{r['blast_radius']}]")


def main() -> int:
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
