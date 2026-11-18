# Code and records behind the paper

This tree holds the mediation implementation, every experiment that produced a
number in the manuscript, and the records those numbers were read from. It is
not a training pipeline: the only model it trains is a small DistilBERT token
classifier, fine-tuned in minutes for one comparison. The heavy runs
call an OpenAI-compatible local endpoint (`http://127.0.0.1:11434` by default)
serving the open-weight models named in the run manifests.

## Layout

- `algorithms/` — **not** the mediation layer. 123 lines of unrelated code (a Laplace
  mechanism, a substring-extraction routine) carried over from an earlier project and kept
  only because `run_all.py` imports them as an import smoke test. The mediation layer is the
  detector and sanitization-mode implementation in `experiments/mediation_baselines.py`,
  with the agent-pipeline element in `experiments/agentdojo_restoration_suite.py`.
- `experiments/` — every experiment, baseline, benchmark-construction and
  analysis script, together with the result records (`*_results.csv`,
  `*_rows_*.csv`, `*_summary_*.csv`) and the run manifests
  (`*_runtime_manifest_*.csv`, `*_manifest_*.csv`) that record model digests,
  quantization, decoding settings, seeds, context length, library versions and
  hardware. `experiments/README.md` is the file-by-file inventory.
- `figures/` — the scripts that draw the manuscript figures.

Scripts resolve the project root two levels above `experiments/` and read
`data/` from there, so an unzipped copy runs without path edits.

## Where each reported number comes from

The pooled summaries behind the main results are rebuilt from the shipped
per-document and per-case records by `experiments/aggregate_paper_results.py`,
which needs no third-party package and is the fastest way to check a reported
number against its record.

| Manuscript object | Produced by |
| --- | --- |
| `tab:measprop` — identifier exposure across boundaries, with span precision and fact retention | `propagation_suite.py` (per-document records under the `v2` tag), pooled by `aggregate_paper_results.py` |
| `tab:propints` — the same table with intervals on every column | `aggregate_paper_results.py` |
| `tab:downstream` — PrivacyLens downstream leakage and helpfulness, including the privacy-enhanced-prompt rows | `privacylens_downstream_suite.py` (`pe/` conditions for the privacy-enhanced prompt), pooled by `aggregate_paper_results.py`; paired tests by `downstream_paired_tests.py` |
| `tab:portability` — second downstream agent | `privacylens_downstream_suite.py` with a second agent model |
| `tab:livestack` — where mediation is applied in a live tool-using agent | `live_stack_placement_suite.py` (`--summarize-only`, `--versus-detector`) |
| `tab:inject` — AgentDojo under prompt injection | `agentdojo_restoration_suite.py` |
| `tab:evasion` — adaptive surface-form evasion and the language-model rewrite attacker | `canonicalization_hardening_suite.py`, `llm_rewrite_evasion_suite.py` |
| `tab:advmeas`, `tab:canon` — evasion per detector, and canonicalization | `measured_adaptive_adversary.py`, `canonicalization_hardening_suite.py` |
| `fig:inferability` — surface form against factual inferability | `figures/fact_retention_vs_inferability.py`, reading the 240-item records written by `semantic_inferability_agreement.py --extend-a semantic_inferability_extend40_collected_A_vgpu3090.csv --extend-b semantic_inferability_extend40_collected_B_vgpu3090.csv --pool-with-round1 A` (reader A is annotator 1, reader B annotator 3; also writes each method's difference from the control); the lexical flag is rescored by `semantic_inferability_rescore_lexical.py` |
| `tab:judgecap` — judge agreement with human labels across model capacity | `semantic_inferability_judge_capacity.py`; the human labels and the two automated proxies are scored by `semantic_inferability_agreement.py` |
| `tab:pljudge` — the benchmark's own judge against two annotators | the records in `privacylens_judge_agreement.csv` |
| `tab:contextattack` — case-identifiability control | `privacylens_context_inference_attack.py` |
| `tab:attrrecovery`, `tab:attrcompact` — attribute recovery against the released surface | `privacylens_attribute_recovery_attack.py` for the attacker rows; `attribute_recovery_presence_audit.py` regenerates the releases without a model, corrects the value-present flag, and writes the `*_corrected.csv` rows and summaries the tables read. `attribute_recovery_breakdown.py` gives the per-kind and candidate-shape figures |
| Injection payload accounting per suite (supplement) | `agentdojo_injection_per_suite.py` |
| Composition of the language-model rewrites (supplement) | `llm_rewrite_composition.py` |
| Judge against the lexical measure (main text) | `semantic_inferability_judge_vs_lexical.py` |
| `tab:matchedret` — exposure at matched retention | `ai4privacy_operating_points.py`, which sweeps detector thresholds on the held-out documents and refuses to write a summary unless its default-threshold counts equal the exposure records; `ai4privacy_parity_tagger.py` for the column with the transformer tagger trained on the same documents, and its transfer to clinical notes |
| Third-party person names as a second PrivacyLens gold set (supplement) | `privacylens_third_party_gold.py`, which refuses to summarize unless its identifier-gold counts equal the exposure records |
| `tab:controls`, `tab:controlkind` — release-free controls for the forced-choice value-recovery attack (the paper's name for the attribute-recovery instrument) | `privacylens_attribute_recovery_attack.py --conditions no_document,masked_document`, scored by `attribute_recovery_controls.py`; the supplement's finer subsets by `attribute_recovery_control_subsets.py` |
| `tab:judgeprompts` — judge agreement under three prompts | `semantic_inferability_judge_capacity.py --prompt-variant {reported,specific_bar,plain_reader} --output-tag 4c` |
| `tab:livestackints` — the live-stack result with intervals, three detector arms | `live_stack_placement_suite.py` (`--summarize-only`, `--versus-detector`) |
| Injection against the transformer detector, the attack written for the restoration boundary, and how far one attack outcome repeats | `agentdojo_restoration_suite.py --attack {important_instructions,restoration_oracle}`, summarized by `agentdojo_injection_extensions.py` |
| `tab:hostanchor` — recorded prompts rerun on the second host | `host_anchor.py`, with the steps `anchor8`, `anchor32`, `anchor27`, `anchorlive`, and `anchorinj` of `remaining_gpu_queue.sh` |
| Experiments that need a larger card, in priority order | `remaining_gpu_queue.sh` |
| `tab:attrcap` — attacker capacity | `attribute_recovery_capacity.py`, which pairs the attacker runs on the identical seeded questions and refuses to pair them if a shared question was posed differently |
| what the replacement tokens disclose, reported in prose | `placeholder_leakage_analysis.py` |
| `tab:crossdom` — cross-domain transfer of the learned detector | `cross_domain_detector.py` |
| `tab:ocrslice` — OCR-mediated slice | `cord_ocr_transfer_suite.py`, `funsd_ocr_transfer_suite.py`, `sroie_ocr_transfer_suite.py` |
| `tab:latency` — middleware latency | `latency_overhead_reconstructed.csv`; the execution environment is in `cppb_reconstructed_runtime_manifest_*.csv` (`latency_host_manifest.csv` describes an older local snapshot and is not the source of this table) |
| `fig:workflow` — the architecture figure | `figures/mediation_architecture.py` (drawn programmatically, no data) |

`fill_paper_tables.py` writes the tables it has records for back into the
manuscript source. It carries builders for labels the manuscript no longer
uses; a builder with no matching label in the `.tex` does nothing.

`tab:threat_map`, `tab:metrics`, `tab:pi_rules`, `tab:pi_profiles`,
`tab:mapping_surface` and `tab:models` are expository and have no record behind
them; they are not claimed as reproduced output.

## Commands

Rebuild the pooled summaries behind the main tables (no dependencies):

```bash
python src/experiments/aggregate_paper_results.py
```

Lightweight repository check, and the manuscript figures:

```bash
python src/run_all.py
python src/figures/run_all_figures.py --out-dir paper/figs
```

Fetch the public corpora the transfer slices need:

```bash
python src/experiments/acquire_external_resources.py
```

Rebuild the controlled benchmark surface and its Hugging Face bundle:

```bash
python src/experiments/build_cppb_manifest.py
python src/experiments/build_cppb_source_manifest.py
python src/experiments/build_hf_cppb_dataset.py --clean
```

Re-run a model-serving experiment (needs the local endpoint and the model named
in that experiment's run manifest — read the conditions off the manifest rather
than off the CLI defaults, which are not what every recorded run used):

```bash
python src/experiments/privacylens_downstream_suite.py --agent-model <model>
python src/experiments/privacylens_attribute_recovery_attack.py --attacker-model <model>
```

Write records back into the manuscript source:

```bash
python src/experiments/fill_paper_tables.py --paper paper/main.tex
python src/experiments/fill_paper_tables.py --paper paper/appendix.tex
```

## Dependencies

`src/requirements.txt`. The optional blind-review interface is in
`src/requirements-ui.txt` and is needed for no reported number; installing it
alongside the pinned stack does not resolve in useful time, which is why it is
a separate file.

## Live-stack placement experiment (not yet reported in the manuscript)

`experiments/live_stack_placement_suite.py`, with its components in
`experiments/live_stack_components.py`, measures whether *where* mediation is
applied changes exposure. The detector and the symbolic mapping operator stay
fixed, and the agent model itself writes every boundary artifact. The
propagation tables come from a deterministic reference agent whose boundaries
are projections of the mediated prompt, and there every method mediates at the
same point, so placement is never varied. This experiment varies it.

**Stack.** One session per case and condition:

- A tool-calling agent behind an OpenAI-compatible `/v1/chat/completions`
  endpoint, with native tool calls, temperature 0 and seed 17. Every
  completion is cached durably.
- The AgentDojo v1 `banking`, `slack` and `workspace` tools, executed against
  their sandboxed environments. Their outputs carry IBANs, e-mail addresses,
  contact names and customer records, and the suites' own environment-state
  checks score task success. A suite with more than 14 tools (`workspace`)
  exposes only the tool families the task needs, because a 4-bit 32B agent
  stopped calling tools when handed travel's 28 schemas.
- A BM25 knowledge-base index over the environment, queried with
  agent-written queries through `search_knowledge_base`.
- A persistent note store that the agent writes and reads back through
  `memory_write` and `memory_read`.
- A JSONL application log of every model message, tool call and tool result.

**Data.** Every AgentDojo task appears in two variants: the published prompt,
and the same prompt prefixed with the account holder's identifiers. This gives
77 tasks and 154 cases. Sensitive values enter at ingress (the user-context
line of the system prompt and the prompt) and mid-trajectory (tool outputs and
retrieved documents).

Gold values come from rules over the environment that share no code with any
detector: structured-identifier patterns, personal record fields, and names
taken from contact records and `first.last` addresses. Each case has a fixed
reference set made of two parts. The first is the ingress values. The second
is the values that the task's ground-truth plan and the index's answer to the
raw prompt expose. Separately, each run also records the values it actually
received, a denominator that depends on the trajectory.

**Conditions.** The detector is set by `--detector` (default `learned_lr`).

| Condition | What is mediated |
| --- | --- |
| `no_mediation` | Nothing. |
| `ingress_only` | The system prompt's user-context line and the user prompt. |
| `egress_only` | Only what is written: index queries, memory notes, tool arguments and log lines. |
| `per_edge` | The ingress text, plus every tool output and retrieved document before the agent reads it. |
| `ingress_only_plus_restore` | As `ingress_only`, with restoration (see below). This is the deployed configuration. |
| `per_edge_plus_restore` | As `per_edge`, with restoration. |
| `per_edge_plus_egress` | Optional. As `per_edge`, plus write-time mediation. |

Restoration puts tokens back only into the arguments of the user's own
services, and only after a recipient check (`--recipient-check`). It also
restores the final answer delivered to the user. The agent's history, the log,
the memory and the index never receive restored values.

**Measurements.** Each row is one case under one condition, and every count is
taken from what the agent generated:

- Gold-value survival in the model context, index queries, memory writes, tool
  arguments (as written and as executed), the log, and the final answer before
  and after restoration. Survival is counted per value, and per character with
  partial credit for identifying pieces. Each count is split into ingress,
  reference mid-trajectory and received mid-trajectory values.
- AgentDojo utility.
- Restoration success.
- Raw values reaching non-authorized boundaries.
- Detector character recall at the ingress and read edges.
- The largest prompt-token count, which flags silent context truncation.

Summaries are cluster-bootstrap intervals that resample AgentDojo tasks (the
two variants share a task), with 1,000 resamples and seed 17. Contrasts are
paired, for example `per_edge - ingress_only` and
`per_edge_plus_restore - ingress_only_plus_restore`.

**Resumability.** Rows are appended with flush and fsync, and `(case,
condition)` pairs already done are skipped. The cached completions make an
interrupted trajectory replay up to the point where it stopped. Free bytes and
inodes are checked before a run, and the run stops with exit code 2 if either
is tight.

**Commands.** Run these from the repository root.

```bash
# CPU smoke test of the whole pipeline. A deterministic stub replaces the model.
python src/experiments/live_stack_placement_suite.py --dry-run \
    --out-dir src/outputs/live_stack_smoke --cache-dir src/outputs/live_stack_smoke/cache

# Size the run without calling anything.
python src/experiments/live_stack_placement_suite.py --plan

# GPU host. Start Ollama with a context that holds the longest workspace
# trajectory. The /v1 endpoint cannot set num_ctx per request.
OLLAMA_CONTEXT_LENGTH=32768 OLLAMA_NUM_PARALLEL=4 OLLAMA_FLASH_ATTENTION=1 \
    OLLAMA_KEEP_ALIVE=2h ollama serve &
MODEL=qwen3:32b-q4km-hf   # the agent of the recorded AgentDojo runs; qwen3:32b from the Ollama library also works

# Pilot: 10 workspace tasks, unmediated. Check env_calls > 0 and max_prompt_tokens in the rows.
python src/experiments/live_stack_placement_suite.py --agent-model $MODEL --suites workspace \
    --max-tasks-per-suite 10 --variants task --conditions no_mediation --output-tag pilot

# Full run: four interleaved shards against one server, resumable.
for i in 0 1 2 3; do
  screen -dmS live$i bash -lc "python src/experiments/live_stack_placement_suite.py \
      --agent-model $MODEL --shard $i/4 --output-tag v1 >> src/experiments/live_stack_placement_v1_shard$i.out 2>&1"
done

# Pool the shards into one summary and one set of paired contrasts.
python src/experiments/live_stack_placement_suite.py --agent-model $MODEL --summarize-only \
    --rows-glob "src/experiments/live_stack_placement_rows_${MODEL//[:\/]/_}_learned_lr_v1_shard*of4.csv" --output-tag v1_pooled

# Second detector arm (Presidio, en_core_web_lg) after the first arm has finished.
# The completion cache is shared per model, so no_mediation replays without model calls.
for i in 0 1 2 3; do
  screen -dmS livep$i bash -lc "python src/experiments/live_stack_placement_suite.py --detector presidio \
      --agent-model $MODEL --shard $i/4 --output-tag v1 >> src/experiments/live_stack_placement_presidio_v1_shard$i.out 2>&1"
done
python src/experiments/live_stack_placement_suite.py --agent-model $MODEL --summarize-only --detector presidio \
    --rows-glob "src/experiments/live_stack_placement_rows_${MODEL//[:\/]/_}_presidio_v1_shard*of4.csv" --output-tag v1_pooled

# Per placement, Presidio minus the learned detector on the same cases.
python src/experiments/live_stack_placement_suite.py --agent-model $MODEL --summarize-only --detector presidio \
    --versus-detector learned_lr --output-tag v1_pooled \
    --rows-glob "src/experiments/live_stack_placement_rows_${MODEL//[:\/]/_}_*_v1_shard*of4.csv"
```

The pooling commands assume that the model tag's `:` and `/` characters become
`_` in file names. Output names carry the model and the detector; the
completion cache carries only the model. A rows file that already holds another
detector's rows is refused rather than resumed.

**Outputs.** The run writes these files under `experiments/`, each carrying the
model name, detector and tag:

- `live_stack_placement_rows_*.csv`, one row per case and condition.
- `live_stack_placement_summary_*.csv` and `live_stack_placement_paired_*.csv`.
- `live_stack_placement_runtime_manifest_*.csv`.
- `live_stack_placement_artifacts_*.jsonl`, the texts behind every row.
- `live_stack_placement_app_log_*.jsonl` and `live_stack_placement_memory_*.jsonl`,
  the stack's own log and memory.
- `live_stack_placement_detector_contrast_*.csv`, from `--versus-detector`.
- `ollama_cache/livestack__<model>.jsonl`, the completion cache.

**Size.** 154 cases × 6 conditions gives 924 trajectories. That comes to about
6,300 model calls (upper bound 13,900 at the 15-step cap), or 9 GPU-hours
serial at 5 s per call for a 4-bit 32B model on a 96 GB card. That rate is an
assumption, so measure it on the pilot. With four shards on
`OLLAMA_NUM_PARALLEL=4`, expect roughly 3–6 hours of wall-clock time. Memory is
about 20 GB of weights plus about 4 GB of KV cache per 16k-token slot. Disk is
under 0.5 GB across about ten files. Adding `--suites
banking,slack,workspace,travel` gives 194 cases and 1,164 trajectories, about
12 GPU-hours serial. The Presidio arm adds 770 trajectories that need the model
(its 154 `no_mediation` trajectories replay from the cache), about 7 GPU-hours
serial or 2.5–5 hours with four shards.
