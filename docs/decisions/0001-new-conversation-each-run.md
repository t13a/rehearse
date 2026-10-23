# 1. Start a new agent conversation on every run

- Status: Accepted
- Date: 2026-10-22
- Issue: [#27](https://github.com/t13a/rehearse/issues/27), PR: [#28](https://github.com/t13a/rehearse/pull/28)

## Context

`rehearse run` used to resume the agent's previous conversation when one existed. The whole earlier conversation was then sent again on every turn, so each follow-up run with `-m` cost more than the one before, even when the follow-up was short. In one trial, three consecutive runs used about 70k, 150k, and 280k tokens; the last one had the fewest turns.

Prompt caching lowers the price of resent input but not always the amount counted against quotas, so the cost of a run grows with the number of turns times the size of the conversation.

## Decision

Every run starts a new conversation. The state of the work lives in the work directory (the placed symlinks and the agent's notes), not in the conversation, so a new conversation can pick the work up from there.

## Alternatives considered

- **Keep resuming.** Rejected: cost grows with every follow-up.
- **Resume only on request (`run --resume`).** Rejected: no concrete use case, and the runner contract stays simpler without it.

## Consequences

- The agent loses its earlier reasoning. Anything a later run needs belongs in notes in the work directory.
- A `-m` message must stand on its own.
- Follow-up runs are cheap: in the same kind of trial, a follow-up that fixed placements used less than half the tokens of the first run.
