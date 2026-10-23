# Design decisions

Each file here records one design decision: why rehearse works the way it does, and which alternatives were rejected. The code and [reference.md](../reference.md) say what rehearse does; these records say why it does not do something else. The lasting principles behind them are in [design.md](../design.md).

## When to write one

Write a record only when all of these hold:

- The decision chose between real alternatives.
- It constrains later changes, for example because it spans several parts or other decisions build on it.
- Its reason cannot be read from the code or the docs.

A good test: could someone later propose a rejected alternative in good faith? Most pull requests, including most bug fixes, do not need a record.

## How

- Discuss in the issue. When the decision is settled, add the record to the pull request that implements it.
- Name the file `NNNN-short-title.md` with the next number.
- Use these sections: Context, Decision, Alternatives considered, Consequences. Link the issue and the pull request.
- Keep the reasons, not the details of the behavior. Those belong in [reference.md](../reference.md).
- Do not rewrite an accepted record. To reverse a decision, add a new record and set the old one's status to `Superseded by N`.

## Records

- [1. Start a new agent conversation on every run](0001-new-conversation-each-run.md)
- [2. Let profiles set the default agent message](0002-profile-agent-message.md)
