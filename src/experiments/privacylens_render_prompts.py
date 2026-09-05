#!/usr/bin/env python3
"""Render the PrivacyLens naive agent prompt prefix for every case using PrivacyLens's own code.

PrivacyLens (Shao et al., 2024) builds its agent prompt with the ToolEmu prompt
modules and toolkit specifications vendored in its repository.  This script
imports that code from a local checkout so the prompt text is byte-identical to
the released evaluation, and writes one JSON record per case containing the
instruction-free prefix (everything before "## Start the Execution"), the
expected final tool, and the tool-name list.  The downstream suite composes the
prefix with a mediated user instruction and trajectory at evaluation time.

Requires the checkout's pinned dependencies (langchain 0.0.277, pydantic<2,
procoder, pandas, tiktoken, rouge_score, tenacity); run it inside a dedicated
environment, e.g. ``~/.venvs/pl``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


EXPERIMENTS_DIR = Path(__file__).resolve().parent
DEFAULT_DATA = EXPERIMENTS_DIR / "external_data" / "privacylens" / "main_data.json"
DEFAULT_OUTPUT = EXPERIMENTS_DIR / "external_data" / "privacylens" / "agent_prompts_naive.jsonl"
START_MARK = "## Start the Execution"


def render_prefix(tr: dict) -> tuple[str, str]:
    from procoder.functional import add_refnames, format_multiple_prompts
    from toolemu.prompts.agent import AGENT_DUMMY_VARS, AGENT_NAIVE_PROMPT, AGENT_NAIVE_SYSTEM_INFO
    from toolemu.tools import get_toolkits_by_names

    toolkits = get_toolkits_by_names(tr["toolkits"])
    all_tools = [t for tk in toolkits for t in tk.tools]
    inputs = dict(
        toolkit_descriptions="\n".join(tk.create_description("medium") for tk in toolkits),
        tool_names=", ".join(t.name for t in all_tools),
    )
    add_refnames(AGENT_DUMMY_VARS, inputs, include_brackets=False)
    system_info, instr = format_multiple_prompts(
        [AGENT_NAIVE_SYSTEM_INFO, AGENT_NAIVE_PROMPT], inputs, include_brackets=[False, True]
    )
    instr = instr.format(
        user_name=tr["user_name"], user_email=tr["user_email"], input=tr["user_instruction"],
        agent_scratchpad=tr["executable_trajectory"],
    )
    prompt = system_info + "\n\n" + instr
    return prompt[: prompt.find(START_MARK)], inputs["tool_names"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--privacylens-dir", type=Path, required=True, help="Path to a PrivacyLens checkout")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    construction_dir = args.privacylens_dir / "data_construction"
    sys.path.insert(0, str(construction_dir))
    os.chdir(construction_dir)  # their prompt modules resolve relative asset paths

    data = json.load(open(args.data, encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as out:
        for ex in data:
            tr = ex["trajectory"]
            prefix, tool_names = render_prefix(tr)
            out.write(json.dumps({"name": ex["name"], "prefix": prefix, "final_action": tr["final_action"],
                                  "tool_names": tool_names}, ensure_ascii=False) + "\n")
    print(f"Rendered {len(data)} prompt prefixes to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
