# Reference

This document lists commands, files, and formats. For the reasons behind them, see [design.md](design.md). For step-by-step usage, see [guide.md](guide.md).

## Commands

### `rehearse create [-p PROFILE] [-s SESSION] A B`

Creates a session and prints its ID.

- `-p PROFILE`: profile name. Default: `default`.
- `-s SESSION`: session ID. Default: the current UNIX time in seconds, increased by one until it is free. A given ID that already exists is an error.

Session IDs and profile names may contain letters, digits, `_`, `-`, and `.`, but must not be `.` or `..`.

`create` fails if `A` or `B` does not exist, is not a directory, is itself a symlink, or contains a symlink, or if `A` and `B` are on different filesystems.

### `rehearse run SESSION [-m MESSAGE]`

Starts the agent and waits for it to exit.

- `-m MESSAGE`: an extra message for this run only. Without it, the agent receives `Start working.` on the first run and `Resume working.` afterwards.

Exit status: `0` if the session ended as `done`, `1` if it ended as `failed`, `2` if the session cannot be run (for example, it is already running).

### `rehearse debug SESSION CMD [ARGS...]`

Starts the agent image like `run`, with the same mounts, user, and lock, but runs `CMD` instead of the agent. When run from a terminal, it is interactive. The session status is updated afterwards in the same way as after `run`.

Examples: `rehearse debug SESSION bash`, `rehearse debug SESSION /entrypoint.sh`.

### `rehearse exec SESSION CMD [ARGS...]`

Runs `CMD` on the host with the session's work directory as the current directory. Example: `rehearse exec SESSION tree`.

### `rehearse status [SESSION]`

Without `SESSION`, lists all sessions, one per line: ID, status, `A`, and `B`, separated by tabs. With `SESSION`, prints the session's metadata as JSON (see [`meta.json`](#metajson)).

### `rehearse commit SESSION`

Moves the real files according to the plan. Allowed in the `done`, `failed`, and `committed` states. Running it again after an interruption continues where it stopped.

Prints counts of moved files, already-moved files, skipped entries, symlinks still in `inbox/`, and files still in `A`. It warns if `inbox/` still contains files, or if `inbox/` is empty but `A` still has files (for example, files added to `A` after the session was created).

Exit status: `0` on success, `1` if the commit stopped (see [`commit.log`](#commitlog)), `2` if the session cannot be committed.

### `rehearse delete SESSION`

Deletes the session directory. Not allowed while the session is running. The deletion runs as root in a helper container, because the session contains files owned by the agent and guard users.

### `rehearse build-image AGENT [TAG] [--no-cache]`

Builds the bundled agent image for `AGENT` (`codex` or `claude`).

- `TAG`: image tag. Default: `rehearse-agent-codex:latest` or `rehearse-agent-claude:latest`.
- `--no-cache`: rebuild every layer. Use this to update the agent CLI, because a normal rebuild reuses the cached installation.

### `rehearse version`

Prints the rehearse version.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `REHEARSE_ROOT` | `~/.local/share/rehearse` | Root directory for sessions, profiles, skeletons, and locks |

This is the only setting read from the host environment. Everything else is set in profiles.

## Root directory layout

```
$REHEARSE_ROOT/
├── profiles/<name>.json   Profiles
├── skeletons/<name>/      Agent home templates
├── sessions/<id>/         Sessions
└── locks/                 Commit locks, one per B
```

`profiles/default.json` (containing `{}`) and `skeletons/default/` (empty) are created automatically when first needed.

## Profiles

A profile is a JSON object in `$REHEARSE_ROOT/profiles/<name>.json`. All fields are optional. Unknown fields are an error. Relative paths are resolved from `$REHEARSE_ROOT`.

The profile is copied into the session when it is created, so later edits to the profile do not affect existing sessions.

| Field | Default | Meaning |
|---|---|---|
| `agent` | `codex` | Agent type: `codex` or `claude`. Selects the default `agent_image`. |
| `agent_image` | `rehearse-agent-<agent>:latest` | Container image that runs the agent |
| `agent_runner` | bundled `scripts/docker-runner.sh` | Script that starts the agent container (see [Runner contract](#runner-contract)) |
| `agent_instructions` | bundled `instructions/default.md` | File installed as `AGENTS.md` in the work directory |
| `agent_timeout` | `3600` | Seconds before the agent CLI is stopped |
| `agent_extra_args` | none | Extra arguments for the agent CLI, separated by spaces |
| `agent_uid`, `agent_gid` | host user's UID and GID | User that runs the agent |
| `guard_uid`, `guard_gid` | `65534`, `65534` | User that owns the protected structure. Must differ from the agent's UID and GID. |
| `helper_image` | `busybox:latest` | Image for root operations (changing ownership, deleting sessions) |
| `skeleton` | `default` | Name of the skeleton copied into the agent home |

Example:

```json
{
  "agent": "claude",
  "skeleton": "claude",
  "agent_instructions": "instructions/music.md",
  "agent_timeout": 7200
}
```

## Skeletons

A skeleton is a directory in `$REHEARSE_ROOT/skeletons/<name>/`. When a session is created, it is copied into the agent home and given to the agent user. Symlinks are copied as symlinks. Changes the agent makes in its home are not written back to the skeleton.

Put files there in the agent CLI's own format, for example `.codex/auth.json` or `.codex/config.toml`.

If `.rehearse/agent/init.sh` exists, the image's entrypoint sources it before starting the agent CLI. Use it to export environment variables such as API keys, or to extend `PATH`.

Skeletons and agent homes can contain secrets. Treat them like passwords. A session's copy is removed when the session is deleted.

## Session directory

```
$REHEARSE_ROOT/sessions/<id>/
├── meta.json        Session metadata
├── commit.log       Commit log (after the first commit)
├── run.lock         Held while the agent runs
├── .git/            Review snapshot
├── .gitignore       Limits the snapshot to work/
├── home/agent/      Agent home, mounted as /home/agent
└── work/            Work directory
    ├── AGENTS.md    Agent instructions
    ├── refs/
    │   ├── a -> A
    │   └── b -> B
    ├── inbox/       Mirror of A
    └── outbox/      Mirror of B, plus the agent's placements
```

Ownership and modes right after creation:

| Path | Owner | Mode |
|---|---|---|
| `work/`, `work/refs/`, `work/AGENTS.md` | guard | umask default |
| `work/inbox/` and its contents | agent | directories `777` |
| `work/outbox/` and its contents | guard | directories `1777` (sticky) |
| `home/agent/` and its contents | agent | as copied |

### `meta.json`

| Field | Meaning |
|---|---|
| `session_id` | Session ID |
| `status` | `created`, `done`, `failed`, or `committed` |
| `created_at`, `started_at`, `ended_at` | Timestamps (UTC) of creation and of the last run |
| `a`, `b` | Absolute paths of `A` and `B` |
| `session_dir` | Absolute path of the session directory |
| `profile_name`, `profile` | Profile name and the profile as it was when the session was created |
| `exit_reason` | Result of the last run (see below) |

`running` is never stored. Commands report a session as `running` while `run.lock` is held.

`exit_reason` values:

| Value | Status | Meaning |
|---|---|---|
| `normal` | `done` | `outbox/.done` exists |
| `timeout` | `failed` | The runner exited with `124` or `137` |
| `exit=N` | `failed` | The runner exited with code `N` |
| `interrupted` | `failed` | rehearse itself stopped before the run finished |

### `commit.log`

One JSON object per line. Every entry has `ts` (UTC timestamp) and `op`.

| `op` | Other fields | Meaning |
|---|---|---|
| `moved` | `src`, `dst` | File moved |
| `already-moved` | `src`, `dst` | Moved by an earlier commit |
| `conflict` | `src`, `dst` | Both exist. The commit stopped. |
| `missing` | `src`, `dst` | Neither exists. The commit stopped. |
| `outside-a` | `target`, `src` | The resolved source is outside `A`. The commit stopped. |
| `unexpected-target` | `target` | The symlink does not point into `refs/a/` or `refs/b/`. The commit stopped. |
| `done` | counts | The commit finished |

## Agent conventions

These are the conventions the agent is asked to follow. The bundled instructions describe them.

- **`outbox/.done`**: an empty file the agent creates when it considers the work finished.

## Agent images

The bundled images are built from `docker/codex/` and `docker/claude/`. The agent CLI runs with its own sandbox and permission prompts disabled. The container is the boundary.

The images do not contain `rm`, `cp`, `ln`, `chmod`, `chown`, `dd`, or `truncate`. This only guides the agent; see [design.md](design.md#what-is-not-a-boundary).

The entrypoint:

1. Sources `~/.rehearse/agent/init.sh` if it exists.
2. Changes to the work directory.
3. Resumes the previous conversation if the agent home contains one, otherwise starts a new one.
4. Runs the agent CLI under `timeout`. After `agent_timeout` seconds it sends `SIGTERM`, and `SIGKILL` 10 seconds later.

> Note: The Claude Code image installs Anthropic's proprietary Claude Code. Built images are for local use only. Do not redistribute them unless Anthropic's license terms allow it.

## Runner contract

rehearse starts the runner (`agent_runner`) with these environment variables and waits for it to exit. The runner's exit code becomes the run's result.

| Variable | Meaning |
|---|---|
| `REHEARSE_RUNNER_MODE` | `run` or `debug` |
| `REHEARSE_SESSION_DIR` | Session directory |
| `REHEARSE_SESSION_A`, `REHEARSE_SESSION_B` | Paths of `A` and `B`. Mount them read-only at the same paths. |
| `REHEARSE_SESSION_RUN_LOCK` | Lock file. Hold it with `flock` while the agent runs, and exit with `75` if it is already held. |
| `REHEARSE_AGENT_WORK_DIR` | Work directory. Mount it read-write at the same path. |
| `REHEARSE_AGENT_HOME` | Agent home. Mount it read-write as `/home/agent`. |
| `REHEARSE_AGENT_IMAGE` | Image to run |
| `REHEARSE_AGENT_UID`, `REHEARSE_AGENT_GID` | User to run as |
| `REHEARSE_AGENT_TIMEOUT` | Timeout in seconds, for the entrypoint |
| `REHEARSE_AGENT_MESSAGE` | Message for this run (only if given) |
| `REHEARSE_AGENT_EXTRA_ARGS` | Extra agent CLI arguments (only if set) |
| `REHEARSE_DEBUG_ENTRYPOINT` | In `debug` mode, the command to run instead of the entrypoint. Its arguments are passed as the runner's arguments. |

Root operations use a separate helper script with `REHEARSE_HELPER_IMAGE` and `REHEARSE_HELPER_MOUNT`. It runs the given command as root with that directory mounted.
