# 2. Let profiles set the default agent message

- Status: Accepted
- Date: 2026-10-23
- Issue: [#29](https://github.com/t13a/rehearse/issues/29), PR: [#30](https://github.com/t13a/rehearse/pull/30)

## Context

Without `-m`, the agent always received `Start working.`. Two problems came from this.

- **The agent did not reliably use the skill it needed.** In trials with a skill for organizing files, some models skipped the skill in about half of the runs and moved files by hand, copying the layout already in `outbox/`. Rewording the skill's `description` helped in one run but not in the next.
- **The language of the conversation.** An English first message makes the agent answer in English, which is harder to review for users who work in another language.

Both supported agent CLIs can invoke a skill explicitly from the user's message (`$skill-name` in Codex, `/skill-name` at the start of the message in Claude Code). A test skill whose `description` forbids using it unless invoked by name confirmed that this works in non-interactive mode, and that the control runs without the invocation did not use the skill.

## Decision

Add the profile field `agent_message`, sent when `rehearse run` has no `-m`. `-m` replaces it; the two are never combined. rehearse passes the message on unchanged and does not know how each CLI invokes a skill.

## Alternatives considered

- **Prepend the profile's message to every `-m`.** This would invoke the skill in follow-up runs automatically. Rejected: the prepended text could get in the way of a `-m` message that must stand on its own (see [decision 1](0001-new-conversation-each-run.md)).
- **Ask for the skill in the instructions** (`instructions/default.md` or a profile's `agent_instructions`). Rejected: instructions become `AGENTS.md`, and explicit invocation works only in the user's message. Stronger wording there has the same weakness as a stronger `description`.

## Consequences

- A profile can invoke a skill on every first run.
- A follow-up `-m` must invoke the skill again if it needs it.
