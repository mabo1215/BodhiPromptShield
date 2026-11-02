#!/bin/bash
# Local queue on the RTX 3070: the anchor attack and the judge prompts, then the anchor
# check, and the release-free controls only if the workstation copy passes it.
cd /mnt/c/source/BodhiPromptShield/src/experiments || exit 1
PY=~/.venvs/bps/bin/python
MODEL=qwen3:8b-q4km-hf
$PY privacylens_attribute_recovery_attack.py --attacker-model $MODEL --conditions placeholder:learned_lr --question-limit 150 --num-ctx 8192 --output-tag anchor_local || { echo ANCHOR_RUN_FAILED; exit 2; }
for v in reported specific_bar plain_reader; do
  $PY semantic_inferability_judge_capacity.py --judge-model $MODEL --workers 1 --prompt-variant $v --output-tag local || echo "judge $v failed"
done
echo JUDGE_DONE
$PY local_hardware_anchor.py || { echo ANCHOR_FAILED; exit 3; }
echo ANCHOR_PASSED
$PY privacylens_attribute_recovery_attack.py --attacker-model $MODEL --conditions no_document,masked_document --num-ctx 8192 --output-tag controls
echo CONTROLS_DONE
