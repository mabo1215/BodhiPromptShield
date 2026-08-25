# Revision-cycle experiment plan for `AESuggestion`

Date: 2026-08-25 (Pacific/Auckland)

The new decision letter is a rejection rather than a continuation of the
previous revision.  Its requested evidence is therefore treated as a new
audit cycle.  The plan below is written before implementation, and separates
executed evidence from claims that must be withdrawn or left as future work.

## Review-to-action map

| Review issue | Action | Evidence status / claim boundary |
| --- | --- | --- |
| Close prior work (PrivacyRestore, Casper) is missing | Add primary citations, a comparison matrix, and an explicit novelty boundary in the related-work section | Manuscript comparison; no claim that placeholder substitution or local restoration is new |
| CPPB has 256 prompts from 32 templates and full-dataset scores | Run a template-disjoint split-integrity and score-provenance audit; retain only the structural split result unless a live end-to-end rerun exists | The audit reports zero template overlap and flags legacy score logs; no new generalization claim from synthetic/generated logs |
| Deterministic agent and semantic leakage | Re-run exact surface-form propagation on the bundled PrivacyLens trajectories and retain a separate semantic-residue measure; preserve the local context-inference result as an attack probe | Surface-form PER/SPE and semantic residue are separate measurements; neither is a guarantee against inference |
| Enterprise redaction has lower PER and utility gains are small | Recompute the paired baseline gaps from the released comparison CSV and revise the paper to state that the proposed method does not win direct exposure; add an independent utility-proxy limitation | Evidence supports a trade-off, not superiority or validated practical utility improvement |
| Weak detector and withheld model/OCR/runtime details | Report the learned detector's exact features/hyperparameters and run metadata; audit portability/OCR manifests for missing identifiers and disclose omissions in the paper | The recommended learned detector is a reproducible lightweight baseline; alias-only/legacy backend claims are downgraded |
| Span-level LDP does not cover the evaluated system | Remove LDP from the central technical contribution and replace it with an explicit no-guarantee scope statement | No end-to-end DP, recovery, or semantic-inference guarantee is claimed |

## Planned experiments and scripts

1. `src/experiments/measured_agent_propagation.py` and
   `src/experiments/measured_privacylens_propagation.py` will be rerun from
   the bundled public exports.  These are exact character-coverage
   measurements and do not require an LLM in the loop.
2. `src/experiments/review_revision_audit.py` will be added.  It will validate
   template disjointness, compare the released dev/test score logs while
   recording their provenance, compute the enterprise-vs-proposed gaps, and
   audit model/OCR/runtime metadata completeness.  The output is an audit
   artifact, not a fabricated replacement for a live CPPB rerun.
3. `src/experiments/build_cppb_full_annotations.py` reconstructs a new,
   deterministic prompt/annotation surface from the public CPPB stubs.  It
   provides exact Python-style `[start, end)` character offsets, but it does
   not recover the historical raw CPPB prompts.  Text-only rows are available
   for a separately frozen reconstructed protocol; OCR rows remain blocked by
   the missing render package and OCR assets.
4. The local GPU smoke test will exercise the learned-detector path and a
   small CUDA tensor operation.  It is only an execution check; it is not
   used to manufacture new paper numbers.  The full LLM attack rerun is
   optional; an available endpoint alone does not remove the prompt-asset and
   frozen-agent-stack prerequisites.

## Resource feasibility (checked 2026-08-25)

| Experiment or task | Local feasibility | RTX 3090 requirement | Blocking condition |
| --- | --- | --- | --- |
| Measured AI4Privacy propagation | Runs locally on CPU from the bundled export | Not required | None for the planned deterministic measurement |
| Measured PrivacyLens propagation | Runs locally on CPU from the bundled trajectories | Not required | None for exact surface-form and semantic-residue measurement |
| CPPB split/provenance/baseline audit | Runs locally on CPU and uses repository CSVs | Not required | It audits legacy artifacts; it cannot replace a fresh live rerun |
| Learned detector baseline | Runs locally on CPU; the local GPU is sufficient for a smoke test | Not required | None for the current lightweight classifier |
| OCR transfer reruns | CPU-capable; local execution is sufficient for small pinned slices | Optional for throughput | OCR/data/runtime provenance must be available |
| Fresh live CPPB or agent-stack rerun | Technically possible only with a callable model and complete prompt/agent assets | Recommended for larger local models or parallel runs | Current prompt manifest is still lightweight stubs; a 3090 alone does not resolve this |
| Named cross-model rerun | Requires the target model/API and exact disclosure metadata | Not a GPU problem | Vendor/model access, digest, decoding, and hosting metadata |
| Independent utility validation | Human/task-level evaluation is CPU-only | Not required | A reference set and independent scoring protocol are still needed |

The three planned evidence-producing scripts and their acceptance criteria are
therefore local tasks. The vGPU 3090 should be reserved for an explicitly
approved live-model rerun, larger-model inference, or throughput-sensitive
OCR batch; it is not a prerequisite for the current revision-cycle evidence.

## Manuscript changes gated by evidence

- Rename the title to make the evaluated OCR-mediated scope explicit and
  avoid implying a full VLM-loop evaluation.
- Add PrivacyRestore and Casper to related work and explain that the paper's
  distinct object is agent-boundary propagation measurement plus restoration
  governance, not placeholder substitution itself.
- Replace the current CPPB leave-template-out generalization wording with the
  audit result and a limitation when the underlying score log is not a live
  rerun.
- Put measured PrivacyLens semantic residue and context-inference accuracy in
  the main results/limitations, explicitly distinguishing literal span
  survival from contextual disclosure.
- Change the enterprise comparison prose from “better” to an evidence-bounded
  privacy--utility trade-off, because the proposed configuration has higher
  PER (9.3% vs. 8.1%) and only +0.02 AC / +0.02 TSR in the current artifact.
- Disclose exact lightweight-classifier configuration, runtime fields, and
  remaining missing provenance; remove unsupported portability language.
- Replace the optional span-level LDP subsection with a short scope statement
  that the evaluated deterministic pipeline has no end-to-end formal privacy
  guarantee.

## Acceptance criteria

- Every new numeric claim in the paper has a bundled CSV/runtime record or is
  explicitly labeled as a limitation/protocol status.
- The audit script runs with the repository's Python dependencies and writes a
  deterministic CSV.
- The propagation scripts and audit pass locally; a CUDA smoke test is
  recorded when the local GPU is available.
- `paper/main.tex` builds successfully with the repository's build script.
