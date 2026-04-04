# Artifact Metadata Notes

## CPPB Benchmark Card Extension

- Benchmark unit: one prompt instance created from a deterministic pair of template family and privacy category, then expanded into eight fixed variants.
- Current scale: 32 templates x 8 variants = 256 prompts.
- Template families: Direct requests, Document-oriented, Retrieval-style, Tool-oriented agent.
- Privacy categories: Person names, Contact details, Postal addresses, National/account identifiers, Financial references, Medical content, Organization/project terms, Context-dependent confidential spans.
- Split semantics: V1-V4 are Essential-privacy variants and V5-V8 are Incidental-privacy variants; V4 and V8 are the OCR-mediated text-plus-image slice.
- Prompt/source provenance in the public snapshot is benchmark-authored and template-derived. The released files describe prompt stubs and accounting metadata rather than raw third-party user data.
- `cppb_release_card.md` consolidates release scope, provenance, annotation examples, wrapper specification, and known omissions into one benchmark-card-style companion note.

## Annotation And Label Semantics

- `primary_privacy_category` is assigned by benchmark construction and names the dominant protected content carried by each prompt template.
- `subset` marks whether the sensitive content is task-critical or incidental to downstream task completion.
- `modality` distinguishes text-only prompts from OCR-mediated text-plus-image prompts.
- Template- and prompt-level assignments are documented in `cppb_template_inventory.csv` and `cppb_prompt_manifest.csv`.

## Multimodal Slice Note

- The OCR-mediated slice contains 64 prompts: variant V4 and V8 across all 32 templates.
- The public snapshot exposes multimodal slice membership through the prompt manifest and accounting summary.
- `multimodal_analysis.csv` reconstructs the current supporting table from bundled slice accounting plus recorded OCR-mediated summary values.
- `multimodal_provenance_card.md` now consolidates slice construction, rendering boundary, OCR-facing provenance, and the still-missing source-image/runtime metadata in one note.
- The current repository still does not ship raw OCR engine/version manifests or document-rendering assets for a full end-to-end multimodal rerun.

## Cross-Model Portability Note

- `crossmodel_portability_results.csv` reconstructs the current appendix portability slice from a bundled alias-level supporting record.
- `crossmodel_runtime_log.csv` records the public alias-level runtime surface for that slice while keeping vendor identities anonymized.
- `crossmodel_named_rerun_manifest_template.csv` now defines the minimum vendor/model/version and runtime fields required before promoting the slice to a named rerun.
- Exact backend names, versions, and vendor-specific decoding fields are still not bundled in the current snapshot.
- `crossmodel_portability_manifest.md` makes the current portability evidence boundary explicit while preserving anonymous reporting.

## Public TAB Transfer Note

- `tab_transfer_results.csv` and `tab_transfer_document_metrics.csv` provide the first executable public-benchmark transfer slice in the current repository snapshot.
- `tab_transfer_execution_manifest.csv` records which comparator families are executed from the current public snapshot and which remain protocol-only.
- `tab_transfer_run_log.csv` now records the bundled public input scope, split counts, generated outputs, and rerun command template for each TAB comparator.
- `tab_zero_shot_prompt_template.txt` and `external_baseline_runtime_manifest_template.csv` now define the fixed zero-shot prompt surface and an Ollama-based public local runtime logging template used by the released TAB and synthetic i2b2 pilots.
- `tab_ollama_zero_shot_baseline.py` now executes that fixed zero-shot surface on a 32-document public TAB pilot slice and writes summary, per-document, runtime-manifest, and run-log artifacts without overwriting the released full TAB heuristic roster.
- `ollama_zero_shot_stability.py` now snapshots repeat reruns of that TAB surface and writes a three-observation mean/std/CI summary for the local semantic baseline path.
- This TAB slice is intentionally text-only and reports span precision/recall/F1, PER, and non-sensitive text retention rather than CPPB-style AC/TSR.
- The current runner now includes raw, regex, NER, two Presidio-class heuristic approximations, one released hybrid de-identification comparator, and the released BodhiPromptShield heuristic mediator; prompted zero-shot LLM de-identification is now also backed by a separate executed local pilot artifact chain.

## i2b2 Clinical Transfer Note

- `i2b2_transfer_execution_manifest.csv` records the current clinical comparator roster and distinguishes methods that are executable once a licensed normalized export is supplied from methods that still require external runtime support.
- `i2b2_transfer_run_log.csv` records the exact result schema, rerun command template, and current waiting-for-licensed-data state for the clinical wrapper roster.
- `i2b2_matched_baseline_suite.py` now provides the exact result schema and heuristic runner used for clinical transfer once user-supplied normalized i2b2 notes are available.
- `build_i2b2_synthea_synthetic_export.py` converts the public i2b2-Synthea sample tables into a schema-compatible synthetic note export with span offsets for a fully public rehearsal path.
- `i2b2_synthea_prompt_wrapped_manifest.csv` and `i2b2_ollama_zero_shot_baseline.py` now provide a prompt-wrapped synthetic clinical slice and an executed local Ollama zero-shot pilot on 32 synthetic notes.
- `ollama_zero_shot_stability.py` now also writes a three-observation mean/std/CI summary for that fixed synthetic clinical zero-shot surface.
- `i2b2_zero_shot_prompt_template.txt` and `external_baseline_runtime_manifest_template.csv` now define the fixed zero-shot surface and an Ollama-based public local runtime logging template shared by the synthetic pilot and the waiting-state licensed route.
- `external_wrapper_release_card.md` now consolidates the wrapper invariants, comparator roster, output files, and licensing boundary shared by TAB and i2b2 transfer.
- The repository still does not redistribute licensed i2b2 notes, so the executed clinical-style pilot should be read as a synthetic schema rehearsal rather than as a licensed benchmark rerun.

## Latency Measurement Note

## Paired Comparison Note

- `paired_method_significance.py` now computes paired bootstrap comparisons over the released five-seed CPPB method prompt logs.
- `paired_method_significance.csv` records mean direct-exposure differences in percentage points, 95% bootstrap confidence intervals, and tail probabilities for the key method pairs discussed in the manuscript.
- The current summary confirms that enterprise staged redaction remains lower on direct PER than the full utility-constrained setting, while the proposed method's main advantage is the propagation-aware privacy--utility operating point rather than single-boundary PER alone.

- `latency_overhead.csv` should be read as a prototype middleware-overhead summary for the controlled CPPB setting.
- The timing rows are intended for single-request serial processing comparisons across the listed mediation pipelines.
- `latency_environment_manifest.md` records the current interpretation boundary for those timing rows.
- `latency_host_manifest_template.csv` now defines the minimum host, scheduling, and prompt-scope fields required before promoting the latency slice to a portable infrastructure claim.
- `latency_host_manifest.csv` now records the actual local workstation, OS, Python runtime, and scheduling mode used for the bundled latency snapshot.
- The current repository still does not bundle service-scale concurrency traces or memory telemetry, so the latency table remains a comparative prototype slice rather than a portable infrastructure benchmark.

## External Resource Acquisition Note

- `external_resource_acquisition_card.md` now consolidates official access paths for public OCR/document benchmarks, request-gated datasets, open baseline repositories, OCR engines, and closed-model documentation sources.
- `external_resource_acquisition_manifest.json` records the machine-readable acquisition surface for those resources, including which ones are directly downloadable and which remain landing-page-only or licensed access.
- Acquisition metadata should be read as reproducibility support rather than as executed benchmark evidence.

## OCR-Heavy External Transfer Note

- `ocr_external_transfer.py` now writes an OCR-heavy transfer tracking surface that separates executed public slices from still-tracked benchmarks across CORD, FUNSD, SROIE, and DocILE.
- `ocr_transfer_protocol.json` now records the shared wrapper invariants plus which OCR-heavy benchmarks are already executed under pinned public snapshots versus which remain acquisition-tracked.
- `ocr_transfer_resource_manifest.csv` records the current cache state, access mode, helper-repo availability, and outstanding OCR/runtime requirements for each OCR-heavy benchmark, including the executed CORD/FUNSD/SROIE slices.
- `ocr_engine_runtime_manifest_template.csv` remains the rerun template for OCR surfaces that still need fresh host/runtime disclosure, while the repository now also ships filled CORD, FUNSD, and SROIE OCR runtime manifests for the executed public slices.
- `acquire_cord_snapshot.py` now pins the public CORD Hugging Face mirror at revision `4f51527df44a7f7f915bee494f1129915118d0e1`, records the archive SHA-256, and writes `cord_snapshot_manifest.json`.
- `acquire_funsd_snapshot.py` now pins the public FUNSD Hugging Face parquet mirror at revision `ccd2a77745b0dc9f154a91db1219ec05c86ce7ec`, records split counts plus per-file hashes, and writes `funsd_snapshot_manifest.json`.
- `acquire_sroie_snapshot.py` now pins the public `rajistics/sroie_processed` mirror at revision `b9bc49bf5eb8b06528c810d02a4f7c766474fbad`, records split counts plus per-file hashes, and writes `sroie_snapshot_manifest.json`.
- `build_cord_transfer_surface.py` and `cord_prompt_wrapped_manifest.csv` now build a benchmark-specific wrapper surface directly from that pinned snapshot rather than from the earlier sample-only repository archive.
- `cord_ocr_transfer_suite.py` now executes a real OCR-heavy CORD rerun on the pinned `valid:100` slice and writes `cord_transfer_results.csv`, `cord_transfer_document_metrics.csv`, `cord_transfer_execution_manifest.csv`, `cord_transfer_run_log.csv`, `cord_transfer_protocol.json`, and `cord_ocr_runtime_manifest.csv`.
- `funsd_ocr_transfer_suite.py` now executes a second public OCR-heavy rerun on the pinned `test:50` FUNSD slice and writes `funsd_transfer_results.csv`, `funsd_transfer_document_metrics.csv`, `funsd_transfer_execution_manifest.csv`, `funsd_transfer_run_log.csv`, `funsd_transfer_protocol.json`, and `funsd_ocr_runtime_manifest.csv`.
- `sroie_ocr_transfer_suite.py` now executes a third public OCR-heavy rerun on the pinned `test:63` SROIE processed slice and writes `sroie_transfer_results.csv`, `sroie_transfer_document_metrics.csv`, `sroie_transfer_execution_manifest.csv`, `sroie_transfer_run_log.csv`, `sroie_transfer_protocol.json`, and `sroie_ocr_runtime_manifest.csv`.
- The executed CORD slice uses `rapidocr-onnxruntime==1.2.3` as the declared OCR engine and now reports raw OCR text, OCR+regex masking, OCR+generic de-identification, Presidio-backed named OCR de-identification, spaCy-backed named OCR de-identification, and the released policy-aware mediation heuristic.
- The executed FUNSD slice reuses the same declared `rapidocr-onnxruntime==1.2.3` stack, treats `B-ANSWER` / `I-ANSWER` form tokens as the protected public transfer slice, and now also reports a spaCy-backed named OCR de-identification comparator beside the Presidio form comparator.
- The executed SROIE slice reuses the same declared OCR stack, protects the structured `company` / `address` / `date` fields while retaining `total`, and records that the current gold-span surface is an OCR-token approximation derived from the processed snapshot's structured target sequence.

## CPPB Source-Level Provenance Note

- `build_cppb_source_manifest.py` now writes `cppb_source_licensing_manifest.csv`, a deterministic source-level provenance summary derived from the released template inventory and prompt manifest.
- The source manifest records prompt-source counts, OCR slice counts, downstream task types, provenance summaries, and licensing boundaries for the four benchmark-authored CPPB source families.