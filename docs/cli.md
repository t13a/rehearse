# CLI

## Commands

### `rehearse create [-p <profile>] [-s <session>] <A> <B>`

- 新しい session directory を作成する
- `-p` で profile、`-s` で session id を指定できる
- session directory の構造と採番規則は [sessions.md](sessions.md)
- profile JSON と skeleton は [profiles.md](profiles.md)
- 初期 git snapshot は [review.md](review.md)

### `rehearse run <session> [-m <message>]`

- session に紐づく agent runner を起動し、終了後に session state を更新する
- `-m "text"` でその実行に限った追加指示を渡せる
- 状態更新、再実行、timeout の扱いは [sessions.md](sessions.md)
- runner の環境変数契約と Docker 境界は [isolation.md](isolation.md)

### `rehearse debug <session> CMD [ARGS...]`

- `run` と同じ agent image、mount、UID/GID、`run.lock` を使い、Docker entrypoint だけを `CMD` に差し替える
- 端末から実行した場合は interactive TTY を渡す
- `CMD` は必須。shell に入りたい場合は `rehearse debug <session> /bin/bash` を明示する
- 終了後の finalization は `run` と同じ。詳細は [sessions.md](sessions.md)

### `rehearse status [<session>]`

- 引数なし: 全セッションの一覧 (id, 状態, 起動時刻, A / B の要約)
- セッション指定: `meta.json` の内容 (状態、タイムスタンプ、 exit reason 等) を表示

配置計画そのもののレビューは [review.md](review.md) の手順で行う。 `status` コマンドはセッション管理に徹し、 content には踏み込まない。

### `rehearse commit <session>`

- `outbox/` の symlink を辿って実ファイルを A→B に rename
- 冪等な実装 (中断しても再実行で残りを処理)
- `meta.json` の status を `committed` に更新
- 詳細: [commit.md](commit.md)

### `rehearse purge <session>`

- session directory を物理削除
- どの永続状態からでも実行可能 (`created` / `done` / `failed` / `committed`)
- 実ファイルへの影響なし

## Environment variables

ユーザー向けの host 環境変数は `REHEARSE_ROOT` だけ。 agent / Docker / skeleton の設定は profile JSON と skeleton に書く。 provider API key は host から pass-through せず、 skeleton の `.rehearse/agent/init.sh` か agent ネイティブ設定 (`.claude/` や `.codex/` 等) に置く。

| 変数 | 既定値 | 用途 |
|---|---|---|
| `REHEARSE_ROOT` | `$HOME/.local/share/rehearse` | session / lock / profile / skeleton の置き場 |

agent / Docker / skeleton の設定は [profiles.md](profiles.md) を参照。
