# rehearse

A harness for delegating complex file organization to AI agents. rehearse uses symlinks as a staging layer, protects the file layout with sticky-bit permissions, and isolates the agent workspace with Docker. During human review, you can inspect the agent's result, which is a move plan, with Git or any other tool you like. You can also make manual adjustments or send follow-up instructions to the agent. Once the plan is approved, rehearse moves all files in one commit step.

## Documentation

- [docs/overview.md](docs/overview.md) — Problem statement, symlink-staging idea, and invariants
- [docs/cli.md](docs/cli.md) — Commands and environment variables
- [docs/sessions.md](docs/sessions.md) — Directory layout, state transitions, and conventions
- [docs/mirroring.md](docs/mirroring.md) — Agent work directory roles and the sticky-bit permission model
- [docs/isolation.md](docs/isolation.md) — Docker mounts and toolbox
- [docs/profiles.md](docs/profiles.md) — Runtime configuration for sessions
- [docs/review.md](docs/review.md) — Human review workflow
- [docs/commit.md](docs/commit.md) — Idempotent commit algorithm

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Docker daemon
- Agent credentials, such as `~/.codex/auth.json`

## Setup

```bash
uv sync
```

This installs dependencies into `.venv/` and makes the `rehearse` command available through `uv run`.

## Build a Single-File Executable

Use PyInstaller when you want to distribute `rehearse` as one executable:

```bash
uv run pyinstaller rehearse.spec
```

The executable is written to `dist/rehearse`. The bundle includes the default agent instructions, runner/helper scripts, and Docker image build files.

## Build Agent Images

Build the agent images locally before first use:

```bash
uv run rehearse build-image codex  # for Codex CLI
uv run rehearse build-image claude # for Claude Code
```

When using the single-file executable, replace `uv run rehearse` with `dist/rehearse` or the installed executable path.

> Note: The Claude Code agent image is intended for local use only. The Dockerfile installs Anthropic's proprietary Claude Code software, which is not covered by this repository's MIT license. Do not redistribute built Claude Code agent images; follow Anthropic's license terms.

## Tests

```bash
uv run pytest -v
```

## Manual Run

The following example uses Codex CLI.

Build the image first:

```bash
uv run rehearse build-image codex
```

Prepare Codex CLI credentials. For ChatGPT login cache and provider API key setup, see "Agent home skeleton" in [docs/profiles.md](docs/profiles.md).

Create sample `A` and `B` directories, then run through `create` -> `run` -> `status` -> `commit` -> `delete`:

```bash
mkdir -p /tmp/fakeA/sub /tmp/fakeB/existing
echo hello > /tmp/fakeA/file1.txt
echo nested > /tmp/fakeA/sub/file2.txt
echo legacy > /tmp/fakeB/existing/old.txt

SID=$(uv run rehearse create /tmp/fakeA /tmp/fakeB)
uv run rehearse status
uv run rehearse run "$SID"            # Starts Codex CLI. On success, outbox/.done appears.
uv run rehearse status "$SID"
ls ~/.local/share/rehearse/sessions/"$SID"/work/outbox/
(cd ~/.local/share/rehearse/sessions/"$SID" && git status)
uv run rehearse commit "$SID"         # Moves files from A to B according to the outbox/ plan.
uv run rehearse delete "$SID"
```

Use `-s` when you want to choose the session ID yourself. Session IDs use the same character set as profile names: letters, digits, `_`, `-`, and `.`.

```bash
uv run rehearse create -s music-2026-04 /tmp/fakeA /tmp/fakeB
```

To inspect a session's agent work directory:

```bash
uv run rehearse exec "$SID" pwd
uv run rehearse exec "$SID" tree
uv run rehearse exec "$SID" git status -u
```

To enter the Docker container, inspect the agent work directory, or run the agent manually:

```bash
uv run rehearse debug "$SID" bash
uv run rehearse debug "$SID" codex --help
uv run rehearse debug "$SID" /entrypoint.sh
```

## Cleanup

Session work directories can contain files that the host user cannot delete directly. This is a side effect of the [sticky-bit permission model](docs/mirroring.md). To delete a session work directory, run:

```bash
uv run rehearse delete <session_id>
```

Internally, rehearse starts a Docker container as root and runs `rm -rf` for that session.
