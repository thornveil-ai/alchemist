# Long-running task tools (RigRun box)

The dev box (`exx@100.109.172.64`) kills processes when the launching ssh session closes and
its client caps ssh at ~600s, so a naive `ssh '<long translate>'` gets cut mid-run and
`nohup/setsid &` gets orphaned+killed. Root cause: systemd-logind was NOT lingering the user
session. Fixed once with `loginctl enable-linger exx` (persists across reboots).

Use these instead of holding an ssh open for a long task:

- **`bgrun NAME WORKDIR CMD...`** — runs CMD in a detached `tmux` session that survives ssh
  disconnect and is unbounded by any ssh/client timeout. Logs to `/tmp/bg_NAME.log`; appends
  `__BGDONE__ exit=N` when finished. Sets `ALCHEMIST_ENDPOINT` automatically.
- **`bgstatus NAME`** — one-shot RUNNING/DONE/DEAD (no blocking).

Pattern: `ssh 'bgrun x <dir> <cmd>'` (returns instantly) → later `ssh 'bgstatus x'` /
`ssh 'tail /tmp/bg_x.log'` from short calls. Installed at `~/.local/bin/{bgrun,bgstatus}` on
the box; sources kept here for versioning.
