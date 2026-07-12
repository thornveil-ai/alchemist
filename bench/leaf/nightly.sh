#!/usr/bin/env bash
# P0.12 — nightly real-pipeline benchmark (box-local cron entry point).
#
# Runs the leaf benchmark against the LOCAL model (the whole pipeline: analyze →
# extract → architect → implement (model fills) → verify → report), then appends
# a timestamped scorecard summary to a history log OUTSIDE the repo (so a
# `git reset --hard` sync never wipes the trend) and, if ALCHEMIST_NTFY_URL is
# set, posts a one-line result. Fail-loud: a down model or a regression is
# recorded, never silently swallowed. This is the standing gap P0.12 closes —
# CI that actually runs the model, not just the green unit suite.
#
# Install (on the box):
#   crontab -l 2>/dev/null | grep -q alchemist-nightly || \
#     (crontab -l 2>/dev/null; echo "0 4 * * * bash /data/rigrun/projects/alchemist/bench/leaf/nightly.sh  # alchemist-nightly") | crontab -
#
# Env overrides: ALCHEMIST_REPO, ALCHEMIST_ENDPOINT, ALCHEMIST_NIGHTLY_LOG,
# ALCHEMIST_NTFY_URL.
set -uo pipefail

REPO="${ALCHEMIST_REPO:-/data/rigrun/projects/alchemist}"
ENDPOINT="${ALCHEMIST_ENDPOINT:-http://localhost:8086/v1}"
PY="$REPO/.venv/bin/python"
LOG="${ALCHEMIST_NIGHTLY_LOG:-/data/rigrun/alchemist_nightly_history.log}"

cd "$REPO" || { echo "alchemist-nightly: no repo at $REPO"; exit 1; }
STAMP="$("$PY" -c 'import datetime;print(datetime.datetime.now().isoformat(timespec="seconds"))' 2>/dev/null || date -Iseconds)"

notify() { [ -n "${ALCHEMIST_NTFY_URL:-}" ] && curl -s -m 10 -d "$1" "$ALCHEMIST_NTFY_URL" >/dev/null 2>&1 || true; }

# 1. Model reachable? A nightly that "passes" against a dead model is a lie.
if ! curl -s -m 10 "$ENDPOINT/models" >/dev/null 2>&1; then
    line="$STAMP  MODEL DOWN ($ENDPOINT) — benchmark skipped"
    echo "$line" | tee -a "$LOG"
    notify "alchemist nightly: MODEL DOWN"
    exit 2
fi

# 2. Run the real pipeline over every leaf subject.
ALCHEMIST_ENDPOINT="$ENDPOINT" "$PY" bench/leaf/run_leafbench.py > /tmp/alchemist_nightly.log 2>&1
rc=$?

# 3. Summarize from the scorecard the runner just wrote.
summary="$("$PY" - "$REPO/bench/leaf/scorecard.json" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    print(f"OVERALL_PASS {d['subjects_overall_pass']}/{d['subjects']} "
          f"verified {d['verified_rate']*100:.1f}% "
          f"first-pass {d['first_pass_rate']*100:.1f}% "
          f"refusal {d['refusal_rate']*100:.1f}%")
except Exception as e:
    print(f"scorecard unreadable: {e}")
PY
)"

line="$STAMP  rc=$rc  $summary"
echo "$line" | tee -a "$LOG"
notify "alchemist nightly: $summary"
exit "$rc"
