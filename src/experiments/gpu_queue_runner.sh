#!/usr/bin/env bash
# Wait for a shared GPU to be free of other people's work, then run this
# paper's queued jobs.
#
# The host is shared. Starting a 32B attacker beside a training run would slow
# that run down even when memory is free, because the contention that matters
# is for SMs rather than for bytes. So this waits instead: it polls for compute
# processes that are not our own Ollama server, requires the card to stay clear
# for several consecutive checks rather than firing in a gap between two of
# someone else's jobs, and only then starts.
#
# It never kills anything, and it never powers the host off -- other work may
# be queued behind ours, and that decision is not this script's to make.
#
# Every job below is resumable, so a killed runner loses at most one row.
set -u

LOGDIR=${LOGDIR:-/root/autodl-tmp/caplogs}
LOG="$LOGDIR/paperqueue.log"
REPO=${REPO:-/root/autodl-tmp/BodhiPromptShield}
INTERVAL=${INTERVAL:-60}          # seconds between checks
STABLE_CHECKS=${STABLE_CHECKS:-5} # consecutive clear checks before starting
IDLE_MIB=${IDLE_MIB:-4000}        # below this, the card counts as idle
OLLAMA_MODELS_DIR=${OLLAMA_MODELS_DIR:-/root/autodl-tmp/ollama/models}

mkdir -p "$LOGDIR"
say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

foreign_gpu_pids() {
    # Compute-app PIDs that are not our Ollama server.
    local ours pids out=""
    ours=" $(pgrep -x ollama | tr '\n' ' ') "
    pids=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | tr -d ' ')
    for p in $pids; do
        case "$ours" in *" $p "*) continue ;; esac
        out="$out $p"
    done
    echo "$out"
}

used_mib() {
    nvidia-smi --query-gpu=memory.used --format=csv,noheader 2>/dev/null | tr -dc '0-9'
}

say "queue runner started; waiting for the card to clear"
say "initial occupants:$(foreign_gpu_pids)  used=$(used_mib) MiB"

clear_streak=0
while :; do
    foreign=$(foreign_gpu_pids)
    used=$(used_mib)
    if [ -z "${foreign// /}" ] && [ "${used:-0}" -lt "$IDLE_MIB" ]; then
        clear_streak=$((clear_streak + 1))
        say "card clear ($clear_streak/$STABLE_CHECKS), used=${used} MiB"
        [ "$clear_streak" -ge "$STABLE_CHECKS" ] && break
    else
        [ "$clear_streak" -gt 0 ] && say "occupied again, resetting streak"
        clear_streak=0
    fi
    sleep "$INTERVAL"
done

say "card is free; starting Ollama and the queue"
if ! pgrep -x ollama >/dev/null; then
    OLLAMA_MODELS="$OLLAMA_MODELS_DIR" OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_MAX_LOADED_MODELS=2 OLLAMA_NUM_PARALLEL=4 OLLAMA_KEEP_ALIVE=8h \
        nohup ollama serve >"$LOGDIR/ollama_serve.log" 2>&1 &
    for _ in $(seq 1 30); do
        curl -s -m 5 http://127.0.0.1:11434/api/tags >/dev/null && break
        sleep 2
    done
fi
curl -s -m 5 http://127.0.0.1:11434/api/tags >/dev/null \
    && say "ollama up" || { say "ollama FAILED to start; stopping"; exit 1; }

cd "$REPO/src/experiments" || { say "repo not found at $REPO"; exit 1; }

run_job() {
    local name="$1"; shift
    say "job $name: starting"
    if "$@" >>"$LOGDIR/$name.log" 2>&1; then
        say "job $name: finished ok"
    else
        say "job $name: FAILED (exit $?); continuing with the next job"
    fi
}

# --- queue -----------------------------------------------------------------
run_job context_attack python privacylens_context_inference_attack.py \
    --attacker-model qwen3:32b-q4km-hf --num-ctx 8192 --options 4

say "queue drained; leaving the host running"
