#!/bin/bash
# bgrun.sh NAME WORKDIR CMD...  — run a long task in a detached tmux session.
# Survives ssh disconnect (requires `loginctl enable-linger <user>`, done once) and is NOT
# bounded by any ssh/client timeout. Logs to /tmp/bg_NAME.log and appends "__BGDONE__ exit=N"
# on completion. Launch returns immediately; poll the log/marker from any later short ssh.
set -euo pipefail
name="$1"; wd="$2"; shift 2
log="/tmp/bg_${name}.log"
: > "$log"
tmux kill-session -t "bg_${name}" 2>/dev/null || true
tmux new-session -d -s "bg_${name}" \
  "cd '$wd' && export ALCHEMIST_ENDPOINT=http://127.0.0.1:8086/v1 && { $*; } >> '$log' 2>&1; echo \"__BGDONE__ exit=\$?\" >> '$log'"
echo "launched bg_${name} (tmux, survives disconnect); log=$log"
