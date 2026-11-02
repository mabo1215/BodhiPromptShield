#!/usr/bin/env python3
"""Break the attribute-recovery attack down by the kind of value that was blanked.

Reads only shipped records: the corrected per-question rows written by
``attribute_recovery_presence_audit.py`` for each attacker, the public
PrivacyLens cases (the unprotected release is the case's own instruction and
trajectory), and the downstream rows that stored the released instruction and
trajectory for two of the mediated conditions. No model is called.

The blank in each question is chosen by a priority rule (longest gold
identifier, else first number, else first capitalized entity), so the three
``span_kind`` values are very different populations. This script reports, per
attacker, condition and kind:

* recovery and literal value presence, as in the attack's own summary;
* recovery when the value is absent from the release;
* the same presence and absent-recovery numbers under a token-level presence
  rule, where a value also counts as present if any of its whitespace tokens of
  at least three characters survives as a whole word in the released text
  (only where the released text is in the records);
* recovery when absent, restricted to questions whose value was present
  verbatim in the unprotected release, i.e. the detector removed something;
* value presence under stricter rules, on the cases whose released text is in the
  records. The token-presence, presence-rules, and release-text-check outputs compare
  against the flag as first recorded (``survives_release_substring``); they document
  that flag's flaw. The presence audit corrects it on all 466 cases by regenerating
  the releases, and every other output here uses the corrected flag;
* a descriptive look at the entity answers;
* whether the answer's surface shape alone singles it out among the four
  options. The questions are rebuilt with the attack's own seeded
  ``_build_questions`` (no model involved) and checked against the rows.

Intervals are 95% percentile bootstrap intervals over cases (1,000 resamples,
seed 17), with the same ratio estimator and resampling order as the attack's
own summary, so the ``all`` rows reproduce the shipped summary exactly.

Outputs, next to the records:

* ``privacylens_attribute_recovery_breakdown_by_kind.csv``
* ``privacylens_attribute_recovery_breakdown_token_presence.csv``
* ``privacylens_attribute_recovery_breakdown_detector_removed.csv``
* ``privacylens_attribute_recovery_breakdown_entity_answers.csv``
* ``privacylens_attribute_recovery_breakdown_entity_person_like.csv``
* ``privacylens_attribute_recovery_breakdown_release_text_check.csv``
* ``privacylens_attribute_recovery_breakdown_option_shape.csv``
* ``privacylens_attribute_recovery_breakdown_presence_rules.csv``
"""
from __future__ import annotations

import collections
import csv
import json
import random
import re
import sys
from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENTS_DIR))

# Only the deterministic question builder is used; nothing here calls a model.
from privacylens_attribute_recovery_attack import _build_questions  # noqa: E402

PL_DATA = EXPERIMENTS_DIR / "external_data" / "privacylens" / "main_data.json"
ATTACKERS = ["qwen3_8b-q4km-hf", "qwen3_32b-q4km-hf", "llama3.3_70b-q4km-hf"]
CONDITIONS = ["no_protection", "placeholder:presidio", "casper_style", "placeholder:learned_lr"]
KINDS = ["all", "identifier", "identifier:user_name", "identifier:email", "identifier:digit_run",
         "number", "entity"]
N_BOOT = 1000
SEED = 17
MIN_TOKEN_LEN = 3
# Replacement tokens written by ``render_placeholders`` (``<PROTECTED_15>``).
REPLACEMENT_TOKEN = re.compile(r"<[A-Z_]+_\d+>")
TITLES = ("Mr.", "Mrs.", "Ms.", "Dr.", "Miss", "Mr", "Mrs", "Ms", "Dr")

# Downstream records that stored the released text, keyed by attack condition.
# casper_restored releases exactly what casper_style releases (restoration only
# acts on the agent's output); the privacy-enhanced prompt changes the agent's
# system prompt, not the mediation. Each mapping is validated question by
# question against the attack's own ``survives_release`` flag before use.
RELEASED_TEXT_SOURCES = {
    "casper_style": ("privacylens_downstream_rows_qwen3_32b-q4km-hf_casper_restored.csv",
                     "casper_restored"),
    "placeholder:learned_lr": ("privacylens_downstream_rows_qwen3_32b-q4km-hf_privacy_prompt.csv",
                               "pe/placeholder:learned_lr"),
}


def bootstrap_ratio_ci(pairs, n_boot=N_BOOT, seed=SEED, scale=100.0):
    """sum(num)/sum(den) with a percentile 95% CI under case resampling.

    A verbatim copy of ``mediation_baselines.bootstrap_ratio_ci`` so that this
    script needs no third-party package and reproduces the shipped intervals.
    """
    if not pairs:
        return float("nan"), float("nan"), float("nan")
    num = sum(p[0] for p in pairs)
    den = sum(p[1] for p in pairs)
    point = scale * num / den if den else 0.0
    rng = random.Random(seed)
    n = len(pairs)
    samples = []
    for _ in range(n_boot):
        s_num = s_den = 0.0
        for _ in range(n):
            a, b = pairs[rng.randrange(n)]
            s_num += a
            s_den += b
        samples.append(scale * s_num / s_den if s_den else 0.0)
    samples.sort()
    return point, samples[int(0.025 * (n_boot - 1))], samples[int(0.975 * (n_boot - 1))]


def rate(rows, num_key, keep=lambda r: True):
    """Case-clustered rate of ``num_key`` over ``rows`` passing ``keep``."""
    by_case: dict[str, list[float]] = {}
    for row in rows:
        if keep(row):
            by_case.setdefault(row["case"], []).append(float(row[num_key]))
    pairs = [(sum(v), float(len(v))) for v in by_case.values()]
    n = int(sum(d for _, d in pairs))
    point, lo, hi = bootstrap_ratio_ci(pairs)
    return n, len(pairs), point, lo, hi


def cell(point, lo, hi):
    if point != point:  # NaN: empty denominator
        return ""
    return f"{point:.1f} [{lo:.1f}, {hi:.1f}]"


def read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def whole_word(token: str, text: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(token) + r"(?!\w)", text) is not None


def token_present(answer: str, released: str) -> int:
    """Exact-substring presence, or any whitespace token of >= 3 chars as a whole word."""
    if answer in released:
        return 1
    return int(any(whole_word(t, released) for t in answer.split() if len(t) >= MIN_TOKEN_LEN))


def present_outside_replacements(answer: str, stripped: str) -> int:
    """The attack's substring rule, not counting matches inside replacement tokens."""
    return int(answer in stripped)


def present_whole_word(answer: str, stripped: str) -> int:
    """The full value as a whole word, not counting replacement tokens."""
    return int(whole_word(answer, stripped))


def released_texts() -> dict[str, dict[str, str]]:
    """Released text per condition and case, from the records that hold it."""
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
    cases = json.load(PL_DATA.open(encoding="utf-8"))
    texts: dict[str, dict[str, str]] = {"no_protection": {}}
    for case in cases:
        tr = case["trajectory"]
        texts["no_protection"][case["name"]] = (
            f"{tr.get('user_instruction', '')}\n\n{tr.get('executable_trajectory', '')}")
    for cond, (name, source_condition) in RELEASED_TEXT_SOURCES.items():
        texts[cond] = {}
        for row in read_rows(EXPERIMENTS_DIR / name):
            if row["condition"] == source_condition and row.get("released_trajectory"):
                texts[cond][row["case"]] = f"{row['released_instruction']}\n\n{row['released_trajectory']}"
    return texts


def coarse_shape(value: str) -> str:
    if "@" in value:
        return "email"
    if any(ch.isdigit() for ch in value):
        return "numeric"
    return "alphabetic"


def format_signature(value: str) -> str:
    """Letters runs become ``A`` and digits ``9``: ``123-45-6789`` -> ``999-99-9999``."""
    return re.sub(r"\d", "9", re.sub(r"[A-Za-z]+", "A", value))


def kind_filter(kind: str):
    if kind == "all":
        return lambda r: True
    if ":" in kind:
        return lambda r: r["fine_kind"] == kind
    return lambda r: r["span_kind"] == kind


def first_name_lexicon(cases: list[dict]) -> set[str]:
    """First names derived from the data: the user names and ``first.last`` e-mail addresses.

    The e-mail rule is a heuristic and admits some non-names (for example
    ``party.planner@``); the matched tokens are written out so the reader can
    see which ones did the matching.
    """
    names = set()
    for case in cases:
        tr = case["trajectory"]
        if tr.get("user_name"):
            names.add(tr["user_name"].split()[0])
        names.add(case["seed"].get("data_sender_name", ""))
        text = " ".join([tr.get("executable_trajectory", ""), tr.get("user_instruction", ""),
                         case["vignette"].get("story", "")])
        for first, _last in re.findall(r"\b([a-z]{2,})[._]([a-z]{2,})\d*@", text):
            names.add(first.capitalize())
    names.discard("")
    return names


def main() -> int:
    cases = json.load(PL_DATA.open(encoding="utf-8"))
    facts = {(c["name"], str(i)): f for c in cases
             for i, f in enumerate(c["trajectory"].get("sensitive_info_items", []))}
    texts = released_texts()
    lexicon = first_name_lexicon(cases)
    user_names = {c["name"]: c["trajectory"].get("user_name", "") for c in cases}
    questions, _dropped = _build_questions(cases, 4, SEED)
    question_by_key = {(q["case"], str(q["fact_index"])): q for q in questions}

    by_kind_out = EXPERIMENTS_DIR / "privacylens_attribute_recovery_breakdown_by_kind.csv"
    token_out = EXPERIMENTS_DIR / "privacylens_attribute_recovery_breakdown_token_presence.csv"
    removed_out = EXPERIMENTS_DIR / "privacylens_attribute_recovery_breakdown_detector_removed.csv"
    answers_out = EXPERIMENTS_DIR / "privacylens_attribute_recovery_breakdown_entity_answers.csv"
    person_out = EXPERIMENTS_DIR / "privacylens_attribute_recovery_breakdown_entity_person_like.csv"
    check_out = EXPERIMENTS_DIR / "privacylens_attribute_recovery_breakdown_release_text_check.csv"
    shape_out = EXPERIMENTS_DIR / "privacylens_attribute_recovery_breakdown_option_shape.csv"
    shape_rows = []
    rules_out = EXPERIMENTS_DIR / "privacylens_attribute_recovery_breakdown_presence_rules.csv"
    rules_rows = []
    stripped_texts = {cond: {case: REPLACEMENT_TOKEN.sub(" ", text) for case, text in by_case.items()}
                      for cond, by_case in texts.items()}

    by_kind_rows, token_rows, removed_rows, person_rows, check_rows = [], [], [], [], []
    entity_answers: collections.Counter = collections.Counter()
    entity_correct: dict[tuple[str, str, str], list[int]] = {}

    for attacker in ATTACKERS:
        every = read_rows(EXPERIMENTS_DIR / f"privacylens_attribute_recovery_rows_{attacker}_corrected.csv")
        control = {(r["case"], r["fact_index"]): r for r in every if r["condition"] == "no_protection"}
        for row in every:
            row["kind_all"] = "all"
            row["present_in_control"] = control[(row["case"], row["fact_index"])]["survives_release"]
            text = texts.get(row["condition"], {}).get(row["case"])
            row["has_text"] = text is not None
            if text is not None:
                row["exact_recomputed"] = int(row["answer"] in text)
                row["token_present"] = token_present(row["answer"], text)
                stripped = stripped_texts[row["condition"]][row["case"]]
                row["present_no_replacement"] = present_outside_replacements(row["answer"], stripped)
                row["present_strict"] = present_whole_word(row["answer"], stripped)
                row["present_in_control_strict"] = present_whole_word(
                    row["answer"], stripped_texts["no_protection"][row["case"]])
            fact = facts[(row["case"], row["fact_index"])]
            first = row["answer"].split()[0] if row["answer"].split() else ""
            row["first_name_hit"] = int(first in lexicon)
            row["title_hit"] = int(any(f"{t} {row['answer']}" in fact for t in TITLES))
            if row["span_kind"] == "identifier":
                if row["answer"] == user_names[row["case"]]:
                    row["fine_kind"] = "identifier:user_name"
                elif "@" in row["answer"]:
                    row["fine_kind"] = "identifier:email"
                else:
                    row["fine_kind"] = "identifier:digit_run"
            else:
                row["fine_kind"] = row["span_kind"]
            q = question_by_key[(row["case"], row["fact_index"])]
            if (q["answer"], str(q["correct_option"]), q["span_kind"]) != (
                    row["answer"], row["correct_option"], row["span_kind"]):
                raise SystemExit(f"rebuilt question differs from the record at {row['case']}/"
                                 f"{row['fact_index']}; refusing the option-shape analysis")
            others = [o for i, o in enumerate(q["options"], 1) if i != q["correct_option"]]
            row["coarse_unique"] = int(all(coarse_shape(o) != coarse_shape(row["answer"]) for o in others))
            row["format_unique"] = int(all(format_signature(o) != format_signature(row["answer"])
                                           for o in others))
            row["person_like_distractors"] = sum(
                1 for o in others if o.split() and o.split()[0] in lexicon)

        # Release-text validation: the recomputed exact rule must equal the
        # attack's survives_release flag on every question it is computed for.
        for cond in CONDITIONS:
            sub = [r for r in every if r["condition"] == cond]
            with_text = [r for r in sub if r["has_text"]]
            agree = sum(1 for r in with_text if str(r["exact_recomputed"]) == r["survives_release_substring"])
            check_rows.append([attacker, cond, len(sub), len({r["case"] for r in sub}),
                               len(with_text), len({r["case"] for r in with_text}),
                               agree, len(with_text) - agree])
        text_ok = {cond for cond in CONDITIONS
                   if any(r["has_text"] for r in every if r["condition"] == cond)
                   and all(str(r["exact_recomputed"]) == r["survives_release_substring"]
                           for r in every if r["condition"] == cond and r["has_text"])}

        for cond in CONDITIONS:
            every_c = [r for r in every if r["condition"] == cond]
            answered = [r for r in every_c if r["chosen_option"]]
            for kind in KINDS:
                in_kind = kind_filter(kind)
                rows_k = [r for r in answered if in_kind(r)]
                unparsed = sum(1 for r in every_c if in_kind(r) and not r["chosen_option"])
                n, n_cases, *rec = rate(rows_k, "correct")
                _, _, *pres = rate(rows_k, "survives_release")
                n_abs, _, *rabs = rate(rows_k, "correct", lambda r: r["survives_release"] == "0")
                by_kind_rows.append([attacker, cond, kind, n, n_cases, unparsed, cell(*rec), cell(*pres),
                                     n_abs, cell(*rabs)])

                # (c) token-level presence on the cases whose released text is in the records.
                if cond in text_ok:
                    sub = [r for r in rows_k if r["has_text"]]
                    sn, s_cases, *s_rec = rate(sub, "correct")
                    _, _, *ex = rate(sub, "survives_release_substring")
                    _, _, *tk = rate(sub, "token_present")
                    ex_abs_n, _, *ex_abs = rate(sub, "correct", lambda r: r["survives_release_substring"] == "0")
                    tk_abs_n, _, *tk_abs = rate(sub, "correct", lambda r: r["token_present"] == 0)
                    token_rows.append([attacker, cond, kind, sn, s_cases, cell(*s_rec), cell(*ex),
                                       cell(*tk), ex_abs_n, cell(*ex_abs), tk_abs_n, cell(*tk_abs)])

                # (e) the detector removed something: present verbatim without protection.
                if cond != "no_protection":
                    removed = lambda r: r["present_in_control"] == "1" and r["survives_release"] == "0"
                    never = lambda r: r["present_in_control"] == "0" and r["survives_release"] == "0"
                    rn, rc, *rrec = rate(rows_k, "correct", removed)
                    nn, nc, *nrec = rate(rows_k, "correct", never)
                    strict_rows = [dict(r, correct=r["correct"] or "0") for r in every_c if in_kind(r)]
                    sn_, _, *srec = rate(strict_rows, "correct", removed)
                    tok_cells = ["", ""]
                    if cond in text_ok:
                        tok_removed = lambda r: (r["has_text"] and r["present_in_control"] == "1"
                                                 and r["token_present"] == 0)
                        tn, _, *trec = rate(rows_k, "correct", tok_removed)
                        tok_cells = [tn, cell(*trec)]
                    removed_rows.append([attacker, cond, kind, rn, rc, cell(*rrec), sn_, cell(*srec),
                                         nn, nc, cell(*nrec), *tok_cells])

            # Presence under stricter rules, on the cases whose released text is in the records.
            if cond in text_ok:
                for kind in KINDS:
                    in_kind = kind_filter(kind)
                    sub = [r for r in answered if in_kind(r) and r["has_text"]]
                    n, n_cases, *rec = rate(sub, "correct")
                    _, _, *attack_rule = rate(sub, "survives_release_substring")
                    _, _, *no_rep = rate(sub, "present_no_replacement")
                    _, _, *strict = rate(sub, "present_strict")
                    n_a, _, *abs_attack = rate(sub, "correct", lambda r: r["survives_release_substring"] == "0")
                    n_r, _, *abs_no_rep = rate(sub, "correct", lambda r: r["present_no_replacement"] == 0)
                    n_s, _, *abs_strict = rate(sub, "correct", lambda r: r["present_strict"] == 0)
                    n_rm, _, *removed_strict = rate(
                        sub, "correct", lambda r: r["present_in_control_strict"] == 1 and r["present_strict"] == 0)
                    rules_rows.append([
                        attacker, cond, kind, f"{len({r['case'] for r in every_c if r['has_text']})}_cases_with_text",
                        n, n_cases, cell(*rec), cell(*attack_rule), cell(*no_rep), cell(*strict),
                        n_a, cell(*abs_attack), n_r, cell(*abs_no_rep), n_s, cell(*abs_strict),
                        n_rm, cell(*removed_strict)])

            # All 466 cases for the learned detector, assuming no number value
            # survives it (0 of 158 questions do on the cases with text). Entity
            # and identifier flags stay on the attack's rule, so this is the
            # replacement-index correction alone.
            if cond == "placeholder:learned_lr":
                for row in answered:
                    row["present_assumed"] = "0" if row["span_kind"] == "number" else row["survives_release_substring"]
                for kind in ("all", "number"):
                    in_kind = kind_filter(kind)
                    sub = [r for r in answered if in_kind(r)]
                    n, n_cases, *rec = rate(sub, "correct")
                    _, _, *attack_rule = rate(sub, "survives_release_substring")
                    _, _, *assumed = rate(sub, "present_assumed")
                    n_a, _, *abs_attack = rate(sub, "correct", lambda r: r["survives_release_substring"] == "0")
                    n_as, _, *abs_assumed = rate(sub, "correct", lambda r: r["present_assumed"] == "0")
                    rules_rows.append([attacker, cond, kind, "all_466_cases_assuming_no_number_value_survives",
                                       n, n_cases, cell(*rec), cell(*attack_rule), cell(*assumed), "",
                                       n_a, cell(*abs_attack), n_as, cell(*abs_assumed), "", "", "", ""])

            # Surface-shape cue: does the answer's shape alone single it out?
            for kind in ["all", "identifier", "identifier:user_name", "identifier:email",
                         "identifier:digit_run", "number", "entity"]:
                in_kind = kind_filter(kind)
                rows_k = [r for r in answered if in_kind(r)]
                for cue, keep in [
                    ("coarse_shape_unique", lambda r: r["coarse_unique"] == 1),
                    ("coarse_shape_shared", lambda r: r["coarse_unique"] == 0),
                    ("format_signature_unique", lambda r: r["format_unique"] == 1),
                    ("format_signature_shared", lambda r: r["format_unique"] == 0),
                ]:
                    n, n_cases, *rec = rate(rows_k, "correct", keep)
                    n_abs, _, *rabs = rate(rows_k, "correct",
                                           lambda r, k=keep: k(r) and r["survives_release"] == "0")
                    shape_rows.append([attacker, cond, kind, cue, n, len(rows_k), n_cases, cell(*rec),
                                       n_abs, cell(*rabs)])

            # (d) entity answers, described.
            ents = [r for r in answered if r["span_kind"] == "entity"]
            if attacker == ATTACKERS[0] and cond == "no_protection":
                entity_answers.update(r["answer"] for r in every_c if r["span_kind"] == "entity")
            for r in ents:
                entity_correct.setdefault((attacker, cond, r["answer"]), []).append(int(r["correct"]))
            groups = [
                ("first_token_in_data_first_name_lexicon", lambda r: r["first_name_hit"] == 1),
                ("preceded_by_title_in_fact", lambda r: r["title_hit"] == 1),
                ("person_like_either_rule", lambda r: r["first_name_hit"] == 1 or r["title_hit"] == 1),
                ("not_person_like", lambda r: r["first_name_hit"] == 0 and r["title_hit"] == 0),
                # Semantic-type cue, with the lexicon applied to answer and distractors alike.
                ("lexicon_person_answer_no_lexicon_person_distractor",
                 lambda r: r["first_name_hit"] == 1 and r["person_like_distractors"] == 0),
                ("lexicon_person_answer_with_lexicon_person_distractor",
                 lambda r: r["first_name_hit"] == 1 and r["person_like_distractors"] > 0),
            ]
            for name, keep in groups:
                n, n_cases, *rec = rate(ents, "correct", keep)
                n_abs, _, *rabs = rate(ents, "correct", lambda r, k=keep: k(r) and r["survives_release"] == "0")
                _, _, *pres = rate(ents, "survives_release", keep)
                person_rows.append([attacker, cond, name, n, n_cases, cell(*rec), cell(*pres),
                                    n_abs, cell(*rabs)])

    with by_kind_out.open("w", encoding="utf-8", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["attacker", "condition", "span_kind", "questions_answered", "cases", "unparsed_replies",
                    "recovery_percent", "value_present_percent", "questions_value_absent",
                    "recovery_when_value_absent_percent"])
        w.writerows(by_kind_rows)
    with token_out.open("w", encoding="utf-8", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["attacker", "condition", "span_kind", "questions_answered_with_released_text",
                    "cases_with_released_text", "recovery_percent_on_subset",
                    "value_present_percent_exact_full_string", "value_present_percent_token_level",
                    "questions_absent_exact", "recovery_when_absent_percent_exact",
                    "questions_absent_token_level", "recovery_when_absent_percent_token_level"])
        w.writerows(token_rows)
    with removed_out.open("w", encoding="utf-8", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["attacker", "condition", "span_kind",
                    "questions_present_unprotected_absent_here", "cases",
                    "recovery_percent_detector_removed", "questions_strict",
                    "recovery_percent_detector_removed_unparsed_as_failure",
                    "questions_absent_unprotected_and_here", "cases_absent_both",
                    "recovery_percent_absent_both",
                    "questions_present_unprotected_all_tokens_removed_here",
                    "recovery_percent_all_tokens_removed"])
        w.writerows(removed_rows)
    with person_out.open("w", encoding="utf-8", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["attacker", "condition", "entity_group", "questions_answered", "cases",
                    "recovery_percent", "value_present_percent", "questions_value_absent",
                    "recovery_when_value_absent_percent"])
        w.writerows(person_rows)
    with answers_out.open("w", encoding="utf-8", newline="") as handle:
        w = csv.writer(handle)
        header = ["rank", "entity_answer", "questions", "first_token_in_data_first_name_lexicon"]
        for attacker in ATTACKERS:
            for cond in CONDITIONS:
                header.append(f"recovery_percent_{attacker}_{cond}")
        w.writerow(header)
        for rank, (answer, count) in enumerate(entity_answers.most_common(30), 1):
            line = [rank, answer, count, int(answer.split()[0] in lexicon)]
            for attacker in ATTACKERS:
                for cond in CONDITIONS:
                    vals = entity_correct.get((attacker, cond, answer), [])
                    line.append(f"{100.0 * sum(vals) / len(vals):.1f}" if vals else "")
            w.writerow(line)
    with check_out.open("w", encoding="utf-8", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["attacker", "condition", "questions", "cases", "questions_with_released_text",
                    "cases_with_released_text", "exact_rule_agrees_with_survives_release",
                    "exact_rule_disagrees"])
        w.writerows(check_rows)

    with shape_out.open("w", encoding="utf-8", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["attacker", "condition", "span_kind", "shape_cue", "questions_answered_with_cue",
                    "questions_answered_in_kind", "cases", "recovery_percent",
                    "questions_value_absent", "recovery_when_value_absent_percent"])
        w.writerows(shape_rows)

    with rules_out.open("w", encoding="utf-8", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["attacker", "condition", "span_kind", "population", "questions_answered", "cases",
                    "recovery_percent", "value_present_percent_attack_rule_substring",
                    "value_present_percent_outside_replacement_tokens",
                    "value_present_percent_whole_word_outside_replacement_tokens",
                    "questions_absent_attack_rule", "recovery_when_absent_percent_attack_rule",
                    "questions_absent_outside_replacement_tokens",
                    "recovery_when_absent_percent_outside_replacement_tokens",
                    "questions_absent_whole_word", "recovery_when_absent_percent_whole_word",
                    "questions_whole_word_in_unprotected_absent_here",
                    "recovery_percent_whole_word_in_unprotected_absent_here"])
        w.writerows(rules_rows)

    total = sum(entity_answers.values())
    matched = collections.Counter()
    for answer, count in entity_answers.items():
        if answer.split()[0] in lexicon:
            matched[answer.split()[0]] += count
    print(f"[breakdown] entity questions {total}, distinct answers {len(entity_answers)}, "
          f"first token in lexicon {sum(matched.values())}")
    print("[breakdown] lexicon tokens that matched: "
          + ", ".join(f"{k}={v}" for k, v in matched.most_common()))
    for path in (by_kind_out, token_out, removed_out, answers_out, person_out, check_out, shape_out, rules_out):
        print(f"[breakdown] wrote {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
