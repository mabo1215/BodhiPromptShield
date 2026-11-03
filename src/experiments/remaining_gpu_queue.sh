#!/bin/bash
# Experiments that need a card larger than a workstation's, in priority order.
#
#   OLLAMA_URL=http://127.0.0.1:11434 HOST_TAG=4c bash src/experiments/remaining_gpu_queue.sh <step> [<step> ...]
#
# Steps: anchor8 anchor32 anchor27 anchorlive anchorinj controls8 controls32 controls70
#        judges8 judges27 judges32 judges70 live injection unprotected scopedregex oracleregex oraclegliner
#        oracleworkspace
#
# Every step is resumable: rerunning it skips the rows already written. It assumes an
# Ollama server at OLLAMA_URL holding the digests the supplement lists. An anchor step puts
# recorded prompts to this host and exits non-zero unless its answers agree with the
# records; run it first on any new host, because a queue that follows a failed anchor
# measures the host rather than the method.
set -u
cd "$(dirname "$0")" || exit 1
PY=${PY:-python}
URL=${OLLAMA_URL:-http://127.0.0.1:11434}
TAG=${HOST_TAG:-host}
AGENT=qwen3:32b-q4km-hf
SERVER_CONFIG="${SERVER_CONFIG:-}"

for space in "$(df -h . | tail -1)" "$(df -i . | tail -1)"; do echo "[space] $space"; done

anchor() {  # Recorded prompts on this host, compared with the recorded answers.
  local model=$1 safe=${1//:/_}
  $PY privacylens_attribute_recovery_attack.py --attacker-model "$model" --base-url "$URL" \
      --conditions placeholder:learned_lr --question-limit 150 --num-ctx 8192 --output-tag "anchor_$TAG" || return 2
  $PY semantic_inferability_judge_capacity.py --judge-model "$model" --ollama-url "$URL" --workers 1 \
      --prompt-variant reported --output-tag "$TAG" || return 2
  $PY host_anchor.py --attacker "$safe" --attack-tag "anchor_$TAG" --judge-tag "$TAG" \
      --output "host_anchor_${safe}_$TAG.csv"
}

anchor27() {  # The reported judge is not an attacker, so only its verdicts are compared.
  $PY semantic_inferability_judge_capacity.py --judge-model gemma2:27b --ollama-url "$URL" --workers 1 \
      --prompt-variant reported --output-tag "$TAG" || return 2
  $PY host_anchor.py --reported-judge --judge-tag "$TAG" --output "host_anchor_gemma2_27b_$TAG.csv"
}

anchorlive() {  # A recorded detector in the live stack, on a seeded sample of five tasks per suite.
  local tasks
  tasks=$($PY - <<'PY'
import csv, glob, random
tasks = {}
for path in sorted(glob.glob("live_stack_placement_rows_qwen3_32b-q4km-hf_learned_lr_v1_shard*of4.csv")):
    with open(path, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            tasks.setdefault(row["suite"], set()).add(row["task"])
rng = random.Random(17)
print(",".join(f"{suite}/{task}" for suite in sorted(tasks)
               for task in rng.sample(sorted(tasks[suite]), 5)))
PY
)
  echo "[anchorlive] $tasks"
  $PY live_stack_placement_suite.py --agent-model "$AGENT" --base-url "$URL" --detector learned_lr --tasks "$tasks" \
      --server-config "$SERVER_CONFIG" --output-tag "anchor15_$TAG" || return 2
  $PY host_anchor.py --live-tag "anchor15_$TAG" --output "host_anchor_live_$TAG.csv"
}

controls() {  # Release-free controls for the attribute-recovery attack, on the same questions as the records.
  $PY privacylens_attribute_recovery_attack.py --attacker-model "$1" --base-url "$URL" \
      --conditions no_document,masked_document --num-ctx 8192 --output-tag controls
}

judges() {  # Whether the judge disagreement moves with the prompt.
  for variant in specific_bar plain_reader; do
    $PY semantic_inferability_judge_capacity.py --judge-model "$1" --ollama-url "$URL" --workers 1 \
        --prompt-variant "$variant" --output-tag "$TAG"
  done
}

live() {  # The transformer detector in the live stack, so the named configuration has been run as a whole.
  for i in ${LIVE_SHARDS:-0 1 2 3}; do
    screen -dmS "livegl$i" bash -lc "$PY live_stack_placement_suite.py --agent-model $AGENT --base-url $URL --detector gliner_pii \
        --server-config '$SERVER_CONFIG' --output-tag v1 --shard $i/4; echo GLINER_SHARD_DONE"
  done
}

injection_arm() {  # suite, tag, attack, detector, modes, scope, extra flags
  local suite=$1 tag=$2 attack=$3 detector=$4 modes=$5 scope=$6 injections
  shift 6
  case $suite in
    banking) injections=injection_task_1,injection_task_8 ;;
    slack)   injections=injection_task_2,injection_task_4 ;;
    workspace) injections=injection_task_3,injection_task_4 ;;
  esac
  $PY agentdojo_restoration_suite.py --agent-model "$AGENT" --base-url "$URL" --suite "$suite" --with-injections --attack "$attack" \
      --injection-tasks "$injections" --detector "$detector" --modes "$modes" --restore-scope "$scope" \
      --output-tag "$tag" "$@"
}

anchorinj() {  # Two recorded arms on this host, read against the recorded attack counts before anything new.
  injection_arm banking "anchorinj_all_$TAG" important_instructions regex_only late all --mediate-tool-outputs
  injection_arm slack   "anchorinj_all_$TAG" important_instructions regex_only late all
}

injection() {  # Injection against a detector that covers more than structured values.
  injection_arm banking inj_all_gliner  important_instructions gliner_pii late all --mediate-tool-outputs
  injection_arm banking inj_scoped_gliner important_instructions gliner_pii late user-directed --mediate-tool-outputs
  injection_arm slack   inj_all_gliner  important_instructions gliner_pii late all
  injection_arm slack   inj_scoped_gliner important_instructions gliner_pii late user-directed
}

unprotected() {  # The unprotected arm on this host, so that the injection arms pair within one host.
  injection_arm banking "inj_none_$TAG" important_instructions regex_only none all
  injection_arm slack   "inj_none_$TAG" important_instructions regex_only none all
}

scopedregex() {  # Recipient-scoped restoration with the regex detector, one request at a time on this host.
  injection_arm banking "inj_scoped_$TAG" important_instructions regex_only late user-directed --mediate-tool-outputs
  injection_arm slack   "inj_scoped_$TAG" important_instructions regex_only late user-directed
}

oracle() {  # An injection written by someone who knows the boundary resolves tokens.
  local detector=$1 short=${1%%_*}
  injection_arm slack   "oracle_all_$short"    restoration_oracle "$detector" late all
  injection_arm slack   "oracle_scoped_$short" restoration_oracle "$detector" late user-directed
  injection_arm banking "oracle_all_$short"    restoration_oracle "$detector" late all --mediate-tool-outputs
  injection_arm banking "oracle_scoped_$short" restoration_oracle "$detector" late user-directed --mediate-tool-outputs
}

oracleworkspace() {  # The third suite, on the user tasks whose prompt holds a value the regex detector tokenizes.
  local tasks=user_task_1,user_task_4,user_task_5,user_task_6,user_task_7,user_task_8,user_task_9,user_task_11,user_task_12
  tasks=$tasks,user_task_13,user_task_19,user_task_20,user_task_21,user_task_23,user_task_27,user_task_32,user_task_37,user_task_38
  injection_arm workspace oracle_all_regex    restoration_oracle regex_only late all --mediate-tool-outputs --tasks "$tasks"
  injection_arm workspace oracle_scoped_regex restoration_oracle regex_only late user-directed --mediate-tool-outputs --tasks "$tasks"
}

for step in "$@"; do
  case $step in
    anchor8)    anchor qwen3:8b-q4km-hf || { echo "[queue] ANCHOR FAILED: $step"; exit 3; } ;;
    anchor32)   anchor qwen3:32b-q4km-hf || { echo "[queue] ANCHOR FAILED: $step"; exit 3; } ;;
    anchor27)   anchor27 || { echo "[queue] ANCHOR FAILED: $step"; exit 3; } ;;
    anchorlive) anchorlive || { echo "[queue] ANCHOR FAILED: $step"; exit 3; } ;;
    anchorinj)  anchorinj ;;
    controls8)  controls qwen3:8b-q4km-hf ;;
    controls32) controls qwen3:32b-q4km-hf ;;
    controls70) controls llama3.3:70b-q4km-hf ;;
    judges8)    judges qwen3:8b-q4km-hf ;;
    judges27)   judges gemma2:27b ;;
    judges32)   judges qwen3:32b-q4km-hf ;;
    judges70)   judges llama3.3:70b-q4km-hf ;;
    live)       live ;;
    injection)  injection ;;
    unprotected) unprotected ;;
    scopedregex) scopedregex ;;
    oracleregex) oracle regex_only ;;
    oraclegliner) oracle gliner_pii ;;
    oracleworkspace) oracleworkspace ;;
    *) echo "unknown step: $step"; exit 2 ;;
  esac
  echo "[queue] finished step $step"
done
