# src/AGENTS.md

## Scope

This file governs all code, experiment scripts, utilities, generated summaries,
configs, outputs, and comments under `src/`.

The purpose of `src/` is to support manuscript revisions required by
`docs/revision_suggestions.tex`.

This rule file may be copied into a destination repo from a template-only
repository. When manuscript-facing files are absent in the template repo, treat
the paths below as destination-repo conventions.

---

## English-only rule

Everything under `src/` must be English only.

This includes:
- source code
- comments
- docstrings
- config keys and descriptions
- filenames
- directory names created under `src/`
- printed messages
- logs
- markdown or text notes placed under `src/`

Chinese is forbidden inside `src/`.

---

## Primary objective

Implement, run, and organize experiments needed to support the manuscript in
`paper/`.

When `USAGE_codex.md` declares a target venue through the line
`目标会议和期刊：...`, use that venue's likely experimental and reporting
expectations to judge which baselines, ablations, robustness checks, and
reproducibility artifacts are missing.

If a revision item requires empirical support, `src/` must provide:
- runnable code
- reproducible outputs
- paper-ready figures or tables
- clean organization

This support role may run in parallel with other agents as part of a
repository-wide revision loop.

---

## Directory usage guidance

Prefer the current repository structure:

- `src/algorithms/` for reusable algorithmic components and mediation logic
- `src/experiments/` for experiment pipelines, manifests, CSV summaries, and
  evaluation scripts
- `src/figures/` for figure-generation scripts that export final assets to
  `paper/figs/`
- `src/run_all.py` for top-level orchestration when it remains the most natural
  entrypoint

If a new temporary output directory is needed, prefer `src/outputs/`.

Do not place final paper figures in `src/`.
Final paper-ready figures must be exported or copied to:
- `paper/figs/`

---

## Coding standards

- Write clear, maintainable, minimal code.
- Prefer extending existing modules over creating redundant scripts.
- Add comments only when they improve clarity.
- Keep function and variable names descriptive.
- Use reproducible seeds when appropriate.
- Avoid hardcoding paths unless repository conventions require them.
- Keep experiment code easy to rerun.

---

## Parallel execution policy

Multiple agents may work under `src/` in parallel when that helps complete a
revision cycle faster.

When doing so:
- assign disjoint ownership for experiment pipelines, figures, manifests, or
  analysis scripts
- do not revert another agent's useful changes
- adapt to new files or outputs produced by other agents
- merge results back into one reproducible experiment story for the paper

---

## Experiment execution rules

When implementing a new experiment:
1. identify the specific manuscript claim it supports
2. add or update code under `src/`
3. run the experiment if feasible
4. save temporary raw outputs under `src/outputs/` if needed
5. generate final publication-ready figure or table data
6. export final paper-ready figures to `paper/figs/`
7. ensure the manuscript can describe:
   - setup
   - metrics
   - result
   - interpretation

Do not leave experiment code unconnected to the paper narrative.

---

## Reproducibility rules

When possible:
- fix random seeds
- save config snapshots
- log dataset split details
- save exact output file names consistently
- use deterministic naming for generated figures

Suggested naming style for final paper assets:
- `prompt_privacy_operating_points.png`
- `agent_propagation_curves.png`
- `agent_pipeline_summary.png`
- `cppb_accounting_summary.csv`

---

## Local data and resources

### Local dataset search
If local experimental data are required, first inspect:
- `F:\\work\\datasets`

Document assumptions in English where needed.

### External image or tool generation
If `fal.ai` Nano Banana is needed, load credentials from:
- `C:\\source\\phdthesis\\.env`

Never print or store raw secret values.

---

## Quality rules for outputs

Paper-facing outputs must be:
- readable
- reproducible
- analytically meaningful
- consistent with manuscript terminology

Do not generate figures that are visually noisy or unexplained.

Prefer:
- clean axis labels
- readable legends
- consistent naming
- paper-ready export formats already used by the repository

---

## When to stop coding in a revision cycle

Stop coding for the current cycle only after one of the following is true:
1. all currently actionable experiment needs are completed, or
2. remaining work is blocked by missing data, missing credentials, or a needed
   user decision

If blocked, ensure the repository-wide process records the blockage in
`docs/progress.md`.

If the repository-wide process determines that only blocked or non-actionable
revision items remain, hand off to the fresh independent review cycle defined in
the root `AGENTS.md`.

---

## Safety and cleanliness

- Do not leak credentials.
- Do not overwrite unrelated user files.
- Do not delete useful outputs unless they are clearly temporary and
  reproducible.
- Do not create unnecessary duplicate experiment pipelines.

---

## Default behavior for short user prompts

If the user gives a short prompt asking to continue the current rule-driven
revision process, interpret it inside `src/` as:

"Check whether new or updated experiments are needed to satisfy
`docs/revision_suggestions.tex`; if yes, implement them in English-only code
under `src/`, run them if feasible, save final paper-ready figures to
`paper/figs/`, and support the manuscript revision process. Work in parallel
with other agents when helpful, and keep iterating until the current revision
guidance has no remaining actionable experiment work. If only blocked items
remain, defer to the root fresh-review reset protocol."
