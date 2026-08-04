# ops/systemd — Forge-OH user-scoped systemd units

All units target user-scoped systemd (`systemctl --user`). Single-user,
local-first on Colossus. Do not install system-wide.

## On-demand self-eval harness

- `forge-oh-selfeval.service` — one-shot invocation of `python -m
  openhands_tools_ext.selfeval.cli`. On-demand only; no companion
  `.timer`. Launched by the BFF's `POST /api/selfeval/run` (Run-now
  button) or directly from a terminal.

See ADR-011 for the on-demand-only rationale.

### One-time install (Colossus)

```bash
mkdir -p ~/.config/systemd/user
ln -sf ~/dev/forge-oh/ops/systemd/forge-oh-selfeval.service ~/.config/systemd/user/
systemctl --user daemon-reload
```

That's it — no `enable`, because there's no `.timer` to enable and the unit
is started explicitly.

Verify the unit is loadable:

```bash
systemctl --user cat forge-oh-selfeval.service
systemd-analyze --user verify forge-oh-selfeval.service
```

### Run a cycle

**From the GUI:** hit **Run now** on the `/selfeval` page.

**From a terminal:**

```bash
systemctl --user start forge-oh-selfeval.service
# tail the run:
journalctl --user -u forge-oh-selfeval.service -f
# check the last run's exit + timing:
systemctl --user status forge-oh-selfeval.service
```

**Bypassing systemd** (to pass different flags without editing the unit):

```bash
cd ~/dev/forge-oh
.oh-venv/bin/python -m openhands_tools_ext.selfeval.cli \
    --limit 10 --sample random --seed 42
```

### Per-cycle overrides via drop-in

Change limit / sampling / timeout without editing tracked files:

```bash
systemctl --user edit forge-oh-selfeval.service
```

Then add e.g.:

```ini
[Service]
Environment=FORGE_SELFEVAL_LIMIT=10
Environment=FORGE_SELFEVAL_SAMPLE=random
```

Drop-ins live at `~/.config/systemd/user/forge-oh-selfeval.service.d/override.conf`
and are not tracked by git — safe to iterate on cadence and budget without
touching the repo.

### Dependency assumption

The unit assumes the BFF is reachable at `http://127.0.0.1:8081`. The
`.service` file names `forge-oh-bff.service` in `Wants=`/`After=`. That
unit does not exist in-repo yet — the harness will still run; the CLI's
per-task error verdict will fire cleanly if the BFF is down.

If/when `forge-oh-bff.service` is written, put it here so the
dependency graph is complete.
