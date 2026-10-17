# rehearse

A harness for letting an AI agent organize large files. The agent rearranges symlinks inside an isolated container. The real files are not moved until a human reviews and commits the plan.

## Documentation

- [README.md](README.md): overview and quick start
- [docs/design.md](docs/design.md): the problem, the core idea, security considerations, and design decisions. Read this before changing behavior.
- [docs/guide.md](docs/guide.md): how to use rehearse
- [docs/reference.md](docs/reference.md): commands, profiles, file formats, and the runner contract
- [instructions/default.md](instructions/default.md): the default instructions for the agent running inside rehearse

Write all documentation, code comments, commit messages, and GitHub issues and pull requests in English.

## Development

- Package manager: `uv`. Use `uv sync`, `uv run rehearse ...`, and `uv run pytest`.
- Tests use `tests/fake-runner.sh` (based on busybox) instead of a real agent, so they need Docker but no agent image or credentials.
- Build the agent images with `uv run rehearse build-image codex|claude`. Add `--no-cache` to update the agent CLI.
- `docs/design.md` lists the security properties and the mechanisms behind them. Changes to mounts, ownership, permissions, or the commit logic must keep that table true, or update it.

## Code map

| Module | Role |
|---|---|
| `cli.py` | Command-line interface |
| `session.py` | Session creation, `meta.json`, and status |
| `mirror.py` | Builds `refs/`, `inbox/`, and `outbox/` |
| `commit.py` | The commit algorithm and the per-`B` lock |
| `run.py` | Starts the runner script with the runner environment |
| `profile.py` | Loads profiles and applies defaults |
| `skeleton.py` | Copies skeletons into the agent home |
| `instruction.py` | Installs `AGENTS.md` into the work directory |
| `helper.py` | Root operations (chown, delete) through the helper script |
| `validate.py` | Checks `A` and `B` before a session is created |
| `lock.py` | Advisory file locks |
| `config.py`, `resource.py` | Defaults, paths, and bundled files |

Python does not run `docker` for the agent itself. The runner script (`scripts/docker-runner.sh`) builds the container command, and the helper script (`scripts/docker-helper.sh`) runs root operations. Replacing the runner through the profile's `agent_runner` switches to a fake runner for tests or to another container runtime.
