# Code and records behind the paper

This tree holds the mediation implementation, every experiment that produced a
number in the manuscript, and the records those numbers were read from. It is
not a training pipeline: nothing here trains a language model. The heavy runs
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
| `tab:measprop`, `fig:propagation` — cross-boundary propagation | `measured_privacylens_propagation.py`, `mediation_baselines.py`; pooled by `aggregate_paper_results.py`, drawn by `figures/propagation_and_fact_gap.py` |
| `tab:propints` — the same table with intervals on every column | `aggregate_paper_results.py` |
| `tab:downstream` — PrivacyLens downstream leakage and helpfulness | `privacylens_downstream_suite.py` |
| `tab:inject` — AgentDojo under prompt injection | `agentdojo_restoration_suite.py` |
| `fig:inferability` — surface form against factual inferability | `figures/fact_retention_vs_inferability.py` |
| `tab:judge` — lightweight learned privacy-judge baseline on the controlled benchmark | `cppb_privacy_judge_baseline.py` |
| `tab:judgecap` — judge agreement with human labels across model capacity | `semantic_inferability_judge_capacity.py`; the human labels and the two automated proxies are scored by `semantic_inferability_agreement.py` |
| `tab:contextattack` — case-identifiability control | `privacylens_context_inference_attack.py` |
| `tab:attrrecovery` — attribute recovery against the released surface | `privacylens_attribute_recovery_attack.py`; `--score-only` rebuilds the summary and the paired differences from the shipped rows without calling a model |
| attacker-capacity comparison, reported in the same appendix section | `attribute_recovery_capacity.py`, which pairs the attacker runs on the identical seeded questions and refuses to pair them if a shared question was posed differently |
| `tab:advmeas` — adaptive adversary against the actual detectors | `measured_adaptive_adversary.py` |
| `tab:mapcompromise` — mapping-table compromise curve | `secure_mapping_compromise.py` |
| `tab:crossdom` — cross-domain transfer of the learned detector | `cross_domain_detector.py` |
| `tab:lightclf` — learned-baseline slice on AI4Privacy | `ai4privacy_lightweight_classifier_baseline.py` |
| TAB external transfer, reported in prose | `tab_matched_baseline_suite.py` |
| `tab:ocrslice` — OCR-mediated slice | `cord_ocr_transfer_suite.py`, `funsd_ocr_transfer_suite.py`, `sroie_ocr_transfer_suite.py` |
| `tab:portability` — second downstream model | `privacylens_downstream_suite.py` with a second agent model |
| `tab:cppb_card` — controlled-benchmark accounting | `build_cppb_manifest.py` |
| `tab:per`, `tab:utility`, `tab:pi_sensitivity`, `tab:latency` — the controlled-benchmark appendix, re-measured on the reconstructed surface | `cppb_reconstructed_paper_tables.py`; the execution environment behind the latency table is in `latency_host_manifest.csv` |
| `tab:restore`, `tab:ablation` — restoration-boundary and sanitization-mode ablations | recorded in `restoration_boundary_analysis.csv` and `sanitization_mode_ablation.csv`; no generating script remains in the tree, so they are records rather than reproducible output |
| `fig:operating_points` — policy operating points | `policy_threshold_sweep.py`, `figures/prompt_privacy_operating_points.py` |

`fill_paper_tables.py` writes the tables it has records for back into the
manuscript source. It carries builders for labels the manuscript no longer
uses; a builder with no matching label in the `.tex` does nothing.

`fig:workflow` is a drawn diagram, not a generated one. `tab:threat_map`,
`tab:pi_rules`, `tab:prior_comparison`, `tab:mapping_surface`, `tab:models` and
`tab:app-examples` are expository and have no record behind them; they are not
claimed as reproduced output.

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
