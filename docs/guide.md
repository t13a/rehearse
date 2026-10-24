# Guide

This guide shows how to use rehearse for real work. For a quick tour with sample files, see the [README](../README.md#quick-start). For exact options and formats, see [reference.md](reference.md).

The examples call `rehearse` directly. In a source checkout, use `uv run rehearse` instead.

## Set up an agent

rehearse needs three things for each agent: an image, a skeleton with credentials, and a profile that connects them.

### 1. Build the image

```bash
rehearse build-image codex    # Codex CLI
rehearse build-image claude   # Claude Code
```

To update the agent CLI later, rebuild with `--no-cache`. A normal rebuild keeps the previously installed version.

### 2. Prepare a skeleton

A skeleton is the initial home directory of the agent. Put credentials and settings there in the agent CLI's own format.

Codex CLI, using the login cache from the host (see [OpenAI's guide for headless devices](https://developers.openai.com/codex/auth#login-on-headless-devices)):

```bash
mkdir -p ~/.local/share/rehearse/skeletons/codex/.codex
cp ~/.codex/auth.json ~/.local/share/rehearse/skeletons/codex/.codex/
```

Claude Code, using an API key:

```bash
mkdir -p ~/.local/share/rehearse/skeletons/claude/.rehearse/agent
cat > ~/.local/share/rehearse/skeletons/claude/.rehearse/agent/init.sh <<'SH'
export ANTHROPIC_API_KEY='sk-ant-...'
SH
chmod 600 ~/.local/share/rehearse/skeletons/claude/.rehearse/agent/init.sh
```

`.rehearse/agent/init.sh` is sourced before the agent CLI starts, so it can set any environment variable. Anything else the agent CLI reads from its home directory, such as settings, plugins, or skills, can also be placed in the skeleton.

Skeletons contain secrets. Keep their permissions tight.

### 3. Create a profile

```bash
cat > ~/.local/share/rehearse/profiles/claude.json <<'JSON'
{
  "agent": "claude",
  "skeleton": "claude"
}
JSON
```

Without `-p`, `create` uses the `default` profile, which runs Codex CLI with the `default` skeleton.

## Write instructions for your library

The bundled instructions ([instructions/default.md](../instructions/default.md) in this repository) explain the workflow and rules to the agent, but know nothing about your library. For real work, copy them and add what the agent needs to know: naming conventions, where things belong, what to do when unsure.

```bash
mkdir -p ~/.local/share/rehearse/instructions
cp instructions/default.md ~/.local/share/rehearse/instructions/music.md
# edit music.md
```

Then point a profile at the file:

```json
{
  "agent": "claude",
  "skeleton": "claude",
  "agent_instructions": "instructions/music.md"
}
```

## Run a session

```bash
SID=$(rehearse create -p claude /path/to/A /path/to/B)
rehearse run "$SID"
```

`run` blocks until the agent exits. Use `rehearse status "$SID"` to see the result: `done` if the agent finished on its own, `failed` otherwise. `exit_reason` tells you why.

To give more instructions, run again with a message. Each run starts a new conversation, and the agent picks up the state of the work from the work directory. It does not see the earlier conversation, so the message must stand on its own:

```bash
rehearse run "$SID" -m "Put live recordings under live/ instead of albums/."
```

The message replaces the profile's `agent_message`. If the profile invokes a skill there (for example `$organizing-media`), invoke it again in the message when the follow-up needs the skill.

## Follow the log

Each run's output is also saved to a log file in the session directory. `rehearse status "$SID"` shows its path as `log`. To follow a run from another terminal:

```bash
LOG=$(rehearse status "$SID" | jq -r .log)
```

How readable the log is depends on the agent CLI.

**Codex** writes plain text: each command, its full output, and the agent's messages. Follow it as it is:

```bash
tail -n +1 -F "$LOG"
```

**Claude Code** with `--print` writes only the final answer. Add `--output-format stream-json --verbose` to the profile's `agent_extra_args` to log every step as JSON lines, then show the messages (💬), tool calls (🔧), and full tool results (↳) with `jq`:

```bash
tail -n +1 -F "$LOG" | jq -rR --unbuffered 'fromjson? // empty
  | if .type == "assistant" then .message.content[]
      | if .type == "text" then "💬 " + .text
        elif .type == "tool_use" then "🔧 " + .name + ": " + ((.input.command // .input) | tostring)
        else empty end
    elif .type == "user" then .message.content[]? | select(.type == "tool_result")
      | (.content | if type == "array" then map(.text? // "") | join("\n") else tostring end | rtrimstr("\n")) as $out
      | ($out | split("\n") | length) as $n
      | if $n > 1 then "↳ \($n) lines:\n" + $out else "↳ " + $out end
    else empty end'
```

A one-line tool result is shown after `↳`. A longer one starts with `↳ N lines:`, followed by the output from the next line.

`fromjson? // empty` skips the lines that are not JSON, such as warnings.

## Review the plan

The session directory is a git repository that tracks the work directory. Everything the agent changed shows up as a change:

```bash
cd ~/.local/share/rehearse/sessions/"$SID"
git status                   # moved symlinks, files the agent created, .done
git diff --find-renames      # where each file came from and where it went
find work/outbox -type f ! -name .done    # files the agent created
```

Regular files in `outbox/` other than `.done` are by-products of the agent's work, such as notes on its choices. The commit leaves them in the session (see [design.md](design.md#design-decisions)).

Any git tool works: `tig`, `lazygit`, VS Code, and so on.

You can fix the plan by hand. The agent's placements belong to your user by default, so you can move them with `mv` like the agent did. You can also commit your own changes in the review repository to keep track of them.

Files the agent could not place stay in `work/inbox/`. They are not moved by the commit.

## Commit

```bash
rehearse commit "$SID"
```

The real files are moved from `A` to `B` according to `outbox/`. The output shows how many files were moved and warns about files left in `inbox/` or `A`.

If the commit stops, it prints the reason, and the last line of `commit.log` in the session directory shows the entry that caused it. Typical causes:

- `conflict`: a file already exists at the destination in `B`. Move the symlink in `outbox/` to another name, or move the existing file away.
- `missing`: the source file disappeared from `A`, for example because another program moved it.
- `outside-a` or `unexpected-target`: the plan contains a symlink that does not point to a file in `A` or `B`. Remove or fix it.

Then run `rehearse commit` again. Files that were already moved are skipped.

## Clean up

```bash
rehearse delete "$SID"
```

This deletes the session directory, including the copy of the skeleton. Real files are not affected. Keeping old sessions is also fine: after a commit, the dangling symlinks record where every file came from and where it went.

## Look inside a session

```bash
rehearse exec "$SID" tree             # on the host, in the work directory
rehearse debug "$SID" bash            # in the agent image, as the agent user
rehearse debug "$SID" /entrypoint.sh  # start the agent manually
```
