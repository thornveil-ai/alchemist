#!/bin/bash
# bgstatus.sh NAME — one-shot status of a bgrun task (no blocking, no timeout risk).
name="$1"; log="/tmp/bg_${name}.log"
[ -f "$log" ] || { echo "no log for $name"; exit 0; }
if grep -q "__BGDONE__" "$log"; then echo "STATUS: DONE ($(grep __BGDONE__ "$log" | tail -1))"
elif tmux ls 2>/dev/null | grep -q "bg_${name}:"; then echo "STATUS: RUNNING"
else echo "STATUS: DEAD (no tmux session, no done-marker)"; fi
