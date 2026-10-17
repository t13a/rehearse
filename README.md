# rehearse

A harness for letting an AI agent organize large files without risking them.

The agent never touches your real files. It rearranges symlinks inside an isolated container, and the resulting symlink tree is a plan. You review the plan with git or any tool you like, adjust it or ask the agent for more work, and only then let rehearse move the real files in one step.

## How it works

- `inbox/` holds a symlink for every file in the source directory `A`. `outbox/` mirrors the existing library `B`.
- The agent moves symlinks from `inbox/` into place in `outbox/`. Read-only mounts, file ownership, and the sticky bit keep it from changing anything else.
- You review the changes with git. Moved symlinks show up as renames.
- `rehearse commit` renames each real file from `A` to its planned place in `B`. An interrupted commit can be resumed.

The [design document](docs/design.md) explains why it works this way and what it protects against.

## Documentation

- [docs/design.md](docs/design.md): the problem, the core idea, and the security considerations
- [docs/guide.md](docs/guide.md): setting up agents, running sessions, reviewing, committing
- [docs/reference.md](docs/reference.md): commands, profiles, skeletons, file formats, the runner contract

## Requirements

- Linux
- Docker
- Python 3.11+ and [uv](https://docs.astral.sh/uv/) (to run from source)
- Credentials for Codex CLI or Claude Code

## Install

```bash
uv sync
```

This installs the dependencies into `.venv/` and makes `uv run rehearse` available.

To build a single executable instead:

```bash
uv run pyinstaller rehearse.spec
```

The executable is written to `dist/rehearse`. It includes the default agent instructions, the runner scripts, and the image build files. When you use it, replace `uv run rehearse` with its path in the examples below.

## Quick start

Build an agent image and prepare credentials as described in the [guide](docs/guide.md#set-up-an-agent). The default profile uses Codex CLI.

```bash
uv run rehearse build-image codex
```

Create sample directories and walk through a session:

```bash
mkdir -p /tmp/fakeA/sub /tmp/fakeB/existing
echo hello > /tmp/fakeA/file1.txt
echo nested > /tmp/fakeA/sub/file2.txt
echo legacy > /tmp/fakeB/existing/old.txt

SID=$(uv run rehearse create /tmp/fakeA /tmp/fakeB)
uv run rehearse run "$SID"        # the agent works; on success it creates outbox/.done
uv run rehearse status "$SID"
(cd ~/.local/share/rehearse/sessions/"$SID" && git status)   # review
uv run rehearse commit "$SID"     # move the real files from A to B
uv run rehearse delete "$SID"
```

## Development

```bash
uv run pytest
```

The tests use a fake runner, so they need Docker but no agent image or credentials. See [AGENTS.md](AGENTS.md) for development notes.

## License

MIT. The Claude Code agent image installs Anthropic's proprietary Claude Code, which this license does not cover. Built Claude Code images are for local use only; do not redistribute them unless Anthropic's license terms allow it.
