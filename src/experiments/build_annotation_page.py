"""Build the blind annotation page for the inferability judge's kappa subset.

``semantic_inferability_judge`` emits a sheet of (released surface, fact)
pairs and a separate key holding the judge's verdicts. This renders the sheet
as a page a person can actually work through: the trajectory on one side, the
one fact in question on the other, two keys to answer, ninety-six times.

The key file is never read here. The page cannot show the judge's answer
because it does not contain it, which is what keeps the subset blind and the
resulting kappa meaningful.

Answers are written to the artifact's own store as they are made, so the work
survives closing the tab, and can be read back to score agreement.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

EXPERIMENTS_DIR = Path(__file__).resolve().parent

PAGE = """<title>Inferability Annotation</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
  :root {
    color-scheme: light;
    --ground: #f5f7f8;
    --surface: #ffffff;
    --surface-sunk: #eef1f4;
    --ink: #15191e;
    --muted: #616b77;
    --faint: #8a95a1;
    --line: #dbe0e6;
    --accent: #2f6f9f;
    --accent-soft: #e4eef6;
    --redact: #a7b1bd;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      color-scheme: dark;
      --ground: #131619;
      --surface: #1a1e23;
      --surface-sunk: #23282e;
      --ink: #e7ecf1;
      --muted: #97a2ae;
      --faint: #6f7a86;
      --line: #2b3138;
      --accent: #69abdb;
      --accent-soft: #1d2b36;
      --redact: #5d6874;
    }
  }
  :root[data-theme="dark"] {
    color-scheme: dark;
    --ground: #131619;
    --surface: #1a1e23;
    --surface-sunk: #23282e;
    --ink: #e7ecf1;
    --muted: #97a2ae;
    --faint: #6f7a86;
    --line: #2b3138;
    --accent: #69abdb;
    --accent-soft: #1d2b36;
    --redact: #5d6874;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--ground);
    color: var(--ink);
    font-family: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
    font-size: 15px;
    line-height: 1.5;
  }
  header {
    border-bottom: 1px solid var(--line);
    background: var(--surface);
    padding: 14px 22px;
    display: flex;
    align-items: baseline;
    gap: 18px;
    flex-wrap: wrap;
  }
  h1 { font-size: 15px; font-weight: 600; margin: 0; letter-spacing: -0.01em; }
  .sub { font-size: 12.5px; color: var(--muted); }
  .spacer { flex: 1 1 auto; }
  .counts { font-size: 12.5px; color: var(--muted); font-variant-numeric: tabular-nums; }
  .counts b { color: var(--ink); font-weight: 600; }
  .rail {
    height: 3px; background: var(--surface-sunk);
    position: relative; overflow: hidden;
  }
  .rail > i { display: block; height: 100%; background: var(--accent); width: 0; transition: width .18s ease; }

  main {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 340px;
    gap: 20px;
    padding: 20px 22px 40px;
    align-items: start;
    max-width: 1500px;
    margin: 0 auto;
  }
  @media (max-width: 900px) { main { grid-template-columns: minmax(0, 1fr); } }

  .panel {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 6px;
  }
  .panel > h2 {
    margin: 0;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--faint);
    padding: 11px 15px;
    border-bottom: 1px solid var(--line);
  }
  pre.traj {
    margin: 0;
    padding: 15px;
    font-family: "IBM Plex Mono", ui-monospace, "SF Mono", Menlo, monospace;
    font-size: 12.5px;
    line-height: 1.62;
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 68vh;
    overflow: auto;
  }
  pre.traj b { color: var(--redact); font-weight: 400; letter-spacing: -0.06em; }

  .side { position: sticky; top: 20px; display: flex; flex-direction: column; gap: 14px; }
  .fact {
    padding: 15px;
    font-size: 15.5px;
    line-height: 1.45;
    text-wrap: pretty;
  }
  .ask { padding: 0 15px 15px; font-size: 13px; color: var(--muted); }
  .answers { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; padding: 0 15px 15px; }
  /* Both answers get identical weight on purpose: colouring one of them
     would nudge the annotator, and the whole point of the subset is an
     independent judgement. */
  .answers button {
    font: inherit;
    font-weight: 500;
    padding: 11px 8px;
    border-radius: 5px;
    border: 1px solid var(--line);
    background: var(--surface-sunk);
    color: var(--ink);
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 3px;
  }
  .answers button kbd {
    font-family: "IBM Plex Mono", monospace;
    font-size: 10.5px;
    color: var(--faint);
    border: 1px solid var(--line);
    border-radius: 3px;
    padding: 0 4px;
    background: var(--surface);
  }
  .answers button:hover { border-color: var(--accent); }
  .answers button[aria-pressed="true"] {
    background: var(--accent-soft);
    border-color: var(--accent);
    box-shadow: inset 0 0 0 1px var(--accent);
  }
  .answers button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

  .nav { display: flex; gap: 8px; align-items: center; padding: 0 15px 15px; }
  .nav button {
    font: inherit; font-size: 13px;
    padding: 7px 11px; border-radius: 5px;
    border: 1px solid var(--line); background: var(--surface);
    color: var(--ink); cursor: pointer;
  }
  .nav button:hover:not(:disabled) { border-color: var(--accent); }
  .nav button:disabled { opacity: .4; cursor: default; }
  .nav button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .pos { margin-left: auto; font-size: 12.5px; color: var(--muted); font-variant-numeric: tabular-nums; }

  .grid { display: grid; grid-template-columns: repeat(16, 1fr); gap: 3px; padding: 15px; }
  @media (max-width: 900px) { .grid { grid-template-columns: repeat(24, 1fr); } }
  .grid i {
    aspect-ratio: 1; border-radius: 2px; cursor: pointer;
    background: var(--surface-sunk); border: 1px solid transparent;
  }
  .grid i[data-done="1"] { background: var(--accent); opacity: .55; }
  .grid i[data-cur="1"] { border-color: var(--ink); opacity: 1; }

  footer { padding: 0 15px 15px; display: flex; gap: 8px; flex-wrap: wrap; }
  footer button {
    font: inherit; font-size: 12.5px; padding: 7px 11px;
    border-radius: 5px; border: 1px solid var(--line);
    background: var(--surface); color: var(--ink); cursor: pointer;
  }
  footer button:hover { border-color: var(--accent); }
  footer button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .note { padding: 0 15px 15px; font-size: 12px; color: var(--faint); line-height: 1.45; }
  .status { font-size: 12px; color: var(--muted); padding: 0 15px 14px; min-height: 16px; }
</style>

<header>
  <h1>Inferability annotation</h1>
  <span class="sub">Blind subset &middot; the model's verdict is not in this page</span>
  <span class="spacer"></span>
  <span class="counts"><b id="done">0</b> of <b id="total">0</b> answered</span>
</header>
<div class="rail"><i id="railfill"></i></div>

<main>
  <section class="panel">
    <h2>Released agent trajectory &mdash; what a downstream reader sees</h2>
    <pre class="traj" id="traj"></pre>
  </section>

  <div class="side">
    <section class="panel">
      <h2>Sensitive fact</h2>
      <div class="fact" id="fact"></div>
      <div class="ask">Reading <strong>only</strong> the trajectory, would a reader learn this fact, or infer it with high confidence?</div>
      <div class="answers">
        <button id="btnYes" aria-pressed="false">Yes, still knowable <kbd>Y</kbd></button>
        <button id="btnNo" aria-pressed="false">No, it is gone <kbd>N</kbd></button>
      </div>
      <div class="nav">
        <button id="prev">&larr; Prev</button>
        <button id="next">Next &rarr;</button>
        <span class="pos" id="pos"></span>
      </div>
      <div class="status" id="status"></div>
    </section>

    <section class="panel">
      <h2>Progress</h2>
      <div class="grid" id="grid"></div>
      <footer>
        <button id="jump">Go to first unanswered</button>
        <button id="export">Download answers (CSV)</button>
      </footer>
      <div class="note">Answering moves to the next item automatically. Arrow keys navigate; a filled square is answered. Answers save as you make them.</div>
    </section>
  </div>
</main>

<script>
const ITEMS = __ITEMS__;
const LOCAL = "inferability-annotations-v1";
let answers = {};
let cur = 0;
let store = null;

const $ = (id) => document.getElementById(id);
const esc = (s) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

function loadLocal() {
  try { return JSON.parse(localStorage.getItem(LOCAL) || "{}"); } catch (e) { return {}; }
}
function saveLocal() {
  try { localStorage.setItem(LOCAL, JSON.stringify(answers)); } catch (e) { /* private mode */ }
}

function renderItem() {
  const it = ITEMS[cur];
  // The full block is the redaction marker; dim it so the eye reads structure
  // rather than counting blocks.
  $("traj").innerHTML = esc(it.text).replace(/\\u2588+/g, (m) => "<b>" + m + "</b>");
  $("traj").scrollTop = 0;
  $("fact").textContent = it.fact;
  const a = answers[it.id];
  $("btnYes").setAttribute("aria-pressed", String(a === 1));
  $("btnNo").setAttribute("aria-pressed", String(a === 0));
  $("pos").textContent = "Item " + (cur + 1) + " / " + ITEMS.length;
  $("prev").disabled = cur === 0;
  $("next").disabled = cur === ITEMS.length - 1;
  renderProgress();
}

function renderProgress() {
  const grid = $("grid");
  if (grid.children.length !== ITEMS.length) {
    grid.innerHTML = "";
    ITEMS.forEach((it, i) => {
      const cell = document.createElement("i");
      cell.title = "Item " + (i + 1);
      cell.addEventListener("click", () => { cur = i; renderItem(); });
      grid.appendChild(cell);
    });
  }
  let n = 0;
  ITEMS.forEach((it, i) => {
    const done = answers[it.id] === 0 || answers[it.id] === 1;
    if (done) n++;
    const cell = grid.children[i];
    cell.dataset.done = done ? "1" : "0";
    cell.dataset.cur = i === cur ? "1" : "0";
  });
  $("done").textContent = n;
  $("total").textContent = ITEMS.length;
  $("railfill").style.width = (100 * n / ITEMS.length) + "%";
}

async function answer(value) {
  const it = ITEMS[cur];
  answers[it.id] = value;
  saveLocal();
  renderProgress();
  if (cur < ITEMS.length - 1) { cur++; renderItem(); } else { renderItem(); }
  if (store) {
    try {
      await store.doc("annotations/" + it.id).set({
        item_id: it.id, human_inferable: value, at: new Date().toISOString(),
      });
      setStatus("Saved.");
    } catch (e) {
      setStatus("Saved on this device only \\u2014 the shared copy did not accept it.");
    }
  }
}

let statusTimer = null;
function setStatus(msg) {
  $("status").textContent = msg;
  clearTimeout(statusTimer);
  statusTimer = setTimeout(() => { $("status").textContent = ""; }, 2400);
}

function toCsv() {
  const rows = [["item_id", "human_inferable_YES_or_NO"]];
  ITEMS.forEach((it) => {
    const a = answers[it.id];
    rows.push([it.id, a === 1 ? "YES" : a === 0 ? "NO" : ""]);
  });
  return rows.map((r) => r.join(",")).join("\\n") + "\\n";
}

$("btnYes").addEventListener("click", () => answer(1));
$("btnNo").addEventListener("click", () => answer(0));
$("prev").addEventListener("click", () => { if (cur > 0) { cur--; renderItem(); } });
$("next").addEventListener("click", () => { if (cur < ITEMS.length - 1) { cur++; renderItem(); } });
$("jump").addEventListener("click", () => {
  const i = ITEMS.findIndex((it) => answers[it.id] !== 0 && answers[it.id] !== 1);
  if (i >= 0) { cur = i; renderItem(); } else { setStatus("Every item is answered."); }
});

document.addEventListener("keydown", (e) => {
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  const k = e.key.toLowerCase();
  if (k === "y") { e.preventDefault(); answer(1); }
  else if (k === "n") { e.preventDefault(); answer(0); }
  else if (e.key === "ArrowLeft" && cur > 0) { e.preventDefault(); cur--; renderItem(); }
  else if (e.key === "ArrowRight" && cur < ITEMS.length - 1) { e.preventDefault(); cur++; renderItem(); }
});

answers = loadLocal();
renderItem();

(async () => {
  const db = window.claude && window.claude.use ? await window.claude.use("db") : null;
  if (db) {
    store = db;
    try {
      const saved = await db.collection("annotations").get();
      let merged = 0;
      (saved || []).forEach((d) => {
        const v = d.human_inferable;
        if ((v === 0 || v === 1) && answers[d.item_id] === undefined) { answers[d.item_id] = v; merged++; }
      });
      if (merged) { saveLocal(); setStatus("Restored " + merged + " saved answers."); }
      renderItem();
    } catch (e) { /* first run has no collection yet */ }
  }
  const dl = window.claude && window.claude.use ? await window.claude.use("downloads") : null;
  $("export").addEventListener("click", async () => {
    const csv = toCsv();
    if (dl) {
      try { await dl.save({ filename: "human_annotations.csv", data: csv }); return; }
      catch (e) { /* declined or unavailable; fall through */ }
    }
    navigator.clipboard.writeText(csv).then(
      () => setStatus("Copied the CSV to the clipboard."),
      () => setStatus("Could not export here \\u2014 the answers are still saved.")
    );
  });
})();
</script>
"""


def build(sheet: Path, out: Path) -> None:
    with sheet.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    items = [
        {"id": r["item_id"], "text": r["released_text_shown_to_judge"], "fact": r["fact"]}
        for r in rows
    ]
    # The sheet legitimately names the text column after the judge; what must
    # never appear is a verdict column, which would unblind the annotator.
    verdicts = {"judge_inferable", "lexical_retained", "method_key", "doc_id"}
    leaked = verdicts & set(rows[0])
    assert not leaked, f"sheet carries fields that would unblind the annotator: {sorted(leaked)}"
    html = PAGE.replace("__ITEMS__", json.dumps(items, ensure_ascii=False))
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({len(items)} items, {len(html)/1024:.0f}KB)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="vgpu3090")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    suffix = f"_{args.tag}" if args.tag else ""
    build(EXPERIMENTS_DIR / f"semantic_inferability_human_sheet{suffix}.csv", Path(args.out))


if __name__ == "__main__":
    main()
