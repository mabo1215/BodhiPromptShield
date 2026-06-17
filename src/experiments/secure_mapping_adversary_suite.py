#!/usr/bin/env python3
"""Execute a minimal secure-mapping-table adversary suite.

Reviewer 541A asks what an attacker against the secure symbolic mapping table
sees, what unlinkability the tokens provide, and how cross-task isolation is
enforced. The manuscript answers this at the design level (token format, table
visibility, cross-task isolation, restoration boundary, audit trail). This
script promotes that design analysis into a small, deterministic, executable
sanity check so the appendix can report measured numbers rather than prose only.

The suite implements a reference ``SecureMappingTable`` that follows the design
described in the paper:

* a protected span is replaced by an opaque per-session token
  ``BPSMAP-<nonce>-<ctr>`` that carries no raw value and no entity type;
* the nonce is derived from a per-session secret, so the same raw value in two
  different sessions yields two unrelated tokens (cross-task isolation);
* restoration requires the per-session credential and only succeeds at an
  authorized boundary; retrieval / memory / log boundaries hold no credential.

Three adversary scenarios are then exercised and logged:

1. Unauthorized restoration -- can a non-authorized agent boundary dereference
   tokens without the per-session credential?
2. Partial table read -- if an attacker reads ``k`` of ``N`` rows of one
   session table, how many spans are recovered, and does that leak into other
   sessions?
3. Cross-session token unlinkability -- can a token-only observer link the same
   raw value across two sessions?

All randomness is seeded, so the artifact is reproducible from repository files.
"""
from __future__ import annotations

import csv
import hashlib
import hmac
from dataclasses import dataclass, field
from pathlib import Path


EXPERIMENTS_DIR = Path(__file__).resolve().parent
SUMMARY_OUTPUT_PATH = EXPERIMENTS_DIR / "secure_mapping_adversary_results.csv"
DETAIL_OUTPUT_PATH = EXPERIMENTS_DIR / "secure_mapping_adversary_scenario_log.csv"
RUNTIME_OUTPUT_PATH = EXPERIMENTS_DIR / "secure_mapping_adversary_runtime_manifest.csv"

# Deterministic master seed for the reference deployment. In a real deployment
# this would be a master wrapping key held in a secret manager / HSM / TEE and
# never checked into the repository; here it only makes the demo reproducible.
MASTER_SEED = b"bodhipromptshield-reference-master-seed-v1"

# A small fixed set of protected raw values used across the probe sessions.
PROTECTED_VALUES = [
    "Jane Doe",
    "jane.doe@example.com",
    "+1-202-555-0143",
    "4111 1111 1111 1111",
    "123-45-6789",
    "10 Downing Street, London",
    "DOB 1984-07-22",
    "Patient MRN 88213",
]


@dataclass
class SecureMappingTable:
    """Reference per-session secure mapping table.

    The table stores token -> raw-value rows for one session only. Tokens are
    opaque and derived from a per-session secret, so they cannot be linked to
    another session's tokens without reading this session's rows.
    """

    session_id: str
    _secret: bytes = field(init=False)
    _counter: int = field(default=0, init=False)
    _rows: dict[str, str] = field(default_factory=dict, init=False)
    _reverse: dict[str, str] = field(default_factory=dict, init=False)
    # The per-session restoration credential. Only an authorized boundary that
    # holds this value may dereference tokens.
    credential: str = field(init=False)

    def __post_init__(self) -> None:
        self._secret = hmac.new(
            MASTER_SEED, self.session_id.encode("utf-8"), hashlib.sha256
        ).digest()
        self.credential = hashlib.sha256(self._secret + b"-restore").hexdigest()

    def _make_token(self, raw_value: str) -> str:
        nonce = hmac.new(
            self._secret,
            f"{self.session_id}:{self._counter}:{raw_value}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()[:16]
        token = f"BPSMAP-{nonce}-{self._counter:03d}"
        self._counter += 1
        return token

    def protect(self, raw_value: str) -> str:
        """Map a raw value to an opaque per-session token."""
        if raw_value in self._reverse:
            return self._reverse[raw_value]
        token = self._make_token(raw_value)
        self._rows[token] = raw_value
        self._reverse[raw_value] = token
        return token

    def restore(self, token: str, presented_credential: str | None) -> str | None:
        """Dereference a token only when the correct credential is presented."""
        if presented_credential != self.credential:
            return None
        return self._rows.get(token)

    def rows(self) -> dict[str, str]:
        return dict(self._rows)


def _fmt(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def run_unauthorized_restoration() -> tuple[dict[str, str], list[dict[str, str]]]:
    """Authorized boundary restores; retrieval/memory/log boundaries cannot."""
    session = SecureMappingTable("session-unauth-001")
    tokens = [session.protect(value) for value in PROTECTED_VALUES]

    boundaries = [
        ("Authorized tool boundary", session.credential),
        ("Retrieval boundary", None),
        ("Memory boundary", None),
        ("Log boundary", None),
        ("Adaptive prompt adversary (guessed credential)", "deadbeef"),
    ]

    detail: list[dict[str, str]] = []
    authorized_success = 0
    unauthorized_attempts = 0
    unauthorized_success = 0
    for boundary_name, presented in boundaries:
        recovered = 0
        for token in tokens:
            value = session.restore(token, presented)
            if value is not None:
                recovered += 1
        authorized = boundary_name.startswith("Authorized")
        rate = recovered / len(tokens)
        detail.append(
            {
                "scenario": "Unauthorized restoration",
                "probe": boundary_name,
                "authorized": "yes" if authorized else "no",
                "tokens": str(len(tokens)),
                "recovered": str(recovered),
                "recovery_rate": _fmt(rate),
            }
        )
        if authorized:
            authorized_success += recovered
        else:
            unauthorized_attempts += len(tokens)
            unauthorized_success += recovered

    summary = {
        "scenario": "Unauthorized restoration",
        "metric": "Unauthorized restoration rate / authorized restoration rate",
        "value": (
            f"{_fmt(unauthorized_success / unauthorized_attempts)} unauthorized; "
            f"{_fmt(authorized_success / len(tokens))} authorized"
        ),
        "interpretation": (
            "Retrieval, memory, log, and credential-guessing boundaries recover "
            "0% of tokens; only the authorized boundary that holds the "
            "per-session credential restores values."
        ),
    }
    return summary, detail


def run_partial_table_read() -> tuple[dict[str, str], list[dict[str, str]]]:
    """Reading k of N rows of one session table recovers exactly those k rows."""
    target = SecureMappingTable("session-partial-target")
    other = SecureMappingTable("session-partial-other")
    target_tokens = [target.protect(value) for value in PROTECTED_VALUES]
    # The other session protects the same raw values, producing unrelated tokens.
    for value in PROTECTED_VALUES:
        other.protect(value)

    total = len(target_tokens)
    detail: list[dict[str, str]] = []
    headline_rate = 0.0
    for k in (0, 2, 4, total):
        leaked_rows = dict(list(target.rows().items())[:k])
        recovered_in_target = sum(1 for token in target_tokens if token in leaked_rows)
        # Cross-session leakage: can the leaked target rows recover any of the
        # other session's tokens? Tokens differ, so this must be zero.
        cross_session_recovered = sum(
            1 for token in other.rows() if token in leaked_rows
        )
        detail.append(
            {
                "scenario": "Partial table read",
                "probe": f"Attacker reads {k}/{total} target rows",
                "authorized": "no",
                "tokens": str(total),
                "recovered": str(recovered_in_target),
                "recovery_rate": _fmt(recovered_in_target / total),
            }
        )
        detail.append(
            {
                "scenario": "Partial table read",
                "probe": f"Cross-session recovery from {k} leaked rows",
                "authorized": "no",
                "tokens": str(len(other.rows())),
                "recovered": str(cross_session_recovered),
                "recovery_rate": _fmt(cross_session_recovered / len(other.rows())),
            }
        )
        if k == total // 2:
            headline_rate = recovered_in_target / total

    summary = {
        "scenario": "Partial table read",
        "metric": "Recovered span fraction vs. fraction of rows read",
        "value": (
            f"Recovery equals rows read (e.g., {_fmt(headline_rate)} at half the "
            "table); cross-session recovery 0.000"
        ),
        "interpretation": (
            "A partial read leaks exactly the rows read and nothing more; leaked "
            "rows of one session cannot restore another session's tokens, so the "
            "blast radius is confined to the compromised session."
        ),
    }
    return summary, detail


def run_cross_session_unlinkability() -> tuple[dict[str, str], list[dict[str, str]]]:
    """The same raw value in two sessions yields unrelated tokens."""
    session_a = SecureMappingTable("session-link-a")
    session_b = SecureMappingTable("session-link-b")

    detail: list[dict[str, str]] = []
    token_collisions = 0
    token_only_links = 0
    for value in PROTECTED_VALUES:
        token_a = session_a.protect(value)
        token_b = session_b.protect(value)
        collides = token_a == token_b
        # A token-only observer can only link by token string equality.
        linked_by_token = token_a == token_b
        if collides:
            token_collisions += 1
        if linked_by_token:
            token_only_links += 1
        detail.append(
            {
                "scenario": "Cross-session unlinkability",
                "probe": f"Same value across two sessions: {value[:18]}",
                "authorized": "no",
                "tokens": "2",
                "recovered": "1" if linked_by_token else "0",
                "recovery_rate": _fmt(1.0 if linked_by_token else 0.0),
            }
        )

    total = len(PROTECTED_VALUES)
    summary = {
        "scenario": "Cross-session unlinkability",
        "metric": "Token-only cross-session linkage rate for identical raw values",
        "value": (
            f"{_fmt(token_only_links / total)} linkage; "
            f"{_fmt(token_collisions / total)} token collision"
        ),
        "interpretation": (
            "A token-only observer links 0% of identical raw values across "
            "sessions because per-session nonces produce unrelated tokens; "
            "linkage requires reading the per-session table, not just tokens. "
            "This is an unlinkability sanity check, not a cryptographic proof."
        ),
    }
    return summary, detail


def build_artifacts() -> tuple[Path, Path, Path]:
    scenario_runners = [
        run_unauthorized_restoration,
        run_partial_table_read,
        run_cross_session_unlinkability,
    ]

    summaries: list[dict[str, str]] = []
    details: list[dict[str, str]] = []
    for runner in scenario_runners:
        summary, detail = runner()
        summaries.append(summary)
        details.extend(detail)

    with open(SUMMARY_OUTPUT_PATH, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["scenario", "metric", "value", "interpretation"]
        )
        writer.writeheader()
        writer.writerows(summaries)

    with open(DETAIL_OUTPUT_PATH, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "scenario",
                "probe",
                "authorized",
                "tokens",
                "recovered",
                "recovery_rate",
            ],
        )
        writer.writeheader()
        writer.writerows(details)

    runtime_rows = [
        {"field": "token_format", "value": "BPSMAP-<16-hex-nonce>-<3-digit-counter>"},
        {"field": "nonce_derivation", "value": "HMAC-SHA256(per-session secret, session:counter:value)"},
        {"field": "session_secret", "value": "HMAC-SHA256(master seed, session_id)"},
        {"field": "restoration_credential", "value": "SHA256(session secret || '-restore')"},
        {"field": "protected_values", "value": str(len(PROTECTED_VALUES))},
        {"field": "scenarios", "value": "unauthorized-restoration; partial-table-read; cross-session-unlinkability"},
        {"field": "randomness", "value": "Deterministic; seeded from fixed master seed"},
        {"field": "scope", "value": "Reference design sanity check; not a full table-compromise evaluation"},
    ]
    with open(RUNTIME_OUTPUT_PATH, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["field", "value"])
        writer.writeheader()
        writer.writerows(runtime_rows)

    return SUMMARY_OUTPUT_PATH, DETAIL_OUTPUT_PATH, RUNTIME_OUTPUT_PATH


def main() -> int:
    summary_path, detail_path, runtime_path = build_artifacts()
    print(f"Secure-mapping adversary summary written to {summary_path}")
    print(f"Secure-mapping adversary scenario log written to {detail_path}")
    print(f"Secure-mapping adversary runtime manifest written to {runtime_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
