# Isolation

- **Docker container** を採用 (systemd-nspawn / bubblewrap も候補だが情報量と既存 tooling で Docker が有利)
- **network**: 必要に応じて有効 (Web 検索を MCP 経由でさせる場合)
- **timeout**: 外部 watcher が N 分後に `docker kill` する
- **リソース制限**: cgroup 経由で cheap に付けられる (必要に応じて)
- **user namespace**: エージェントの UID は host の unprivileged user にマップする

## Docker マウント設計

**原則: ホストとコンテナで同じパスを使う**

symlink の target はただの文字列で、 解決時に絶対パスとして評価される。ホストとコンテナでパスが食い違うと、片側から symlink が壊れて見える。したがってコンテナ内のマウント先はホストのパスをそのまま使う。

マウントするのは **agent work dir (`data/`) のみ**。 session directory ルート直下の `.git/` や `meta.json` は container から見えないので、 agent が git の存在を観測することも、 harness のメタに触れることもできない。

```bash
docker run --rm \
  -v $HOME/.local/share/rehearse/sessions/<id>/data:$HOME/.local/share/rehearse/sessions/<id>/data:rw \
  -v /host/path/A:/host/path/A:ro \
  -v /host/path/B:/host/path/B:ro \
  --network=... \
  --user <agent-uid>:<agent-gid> \
  rehearse-agent-codex:latest
```

コンテナ内の view:

```
$HOME/.local/share/rehearse/sessions/<id>/
└── data/                    (sessions/<id>/data のみがマウントされる)
    ├── refs/
    │   ├── a -> /host/path/A    (ro マウント経由で読める)
    │   └── b -> /host/path/B    (ro マウント経由で読める)
    ├── inbox/
    └── outbox/
```

ホスト側の commit スクリプトも同じパスを使って symlink を辿れる。

### agent home: `sessions/<id>/home/agent` ↔ `/home/agent`

Codex CLI や Claude Code は agent home 配下に認証情報、設定、会話履歴を置く。これがコンテナ揮発領域にあると `--rm` で消えてしまうので、 agent の HOME を **session directory 内に永続化**する:

- `rehearse create` がセッションごとに `sessions/<id>/home/agent/` を掘り、 `inbox/` と一緒に agent UID へ chown ハンドオフする
- profile の `skeleton` で指定された `$REHEARSE_ROOT/skeletons/<name>/` を `sessions/<id>/home/agent/` にコピーする。未指定時は `default`。 `skeletons/default/` は空ディレクトリとして自動作成される
- runner script はこれを `/home/agent` に rw で bind mount し、 `HOME=/home/agent` を `-e` で渡す
- FHS に沿った `/home/agent` を選んだのは、一般的な CLI agent が前提とする「ホームディレクトリらしい場所」と整合させるため
- ホスト側のパスが `sessions/<id>/home/agent` なのは session directory レイアウトの対称性を取るため

コピーは symlink を symlink のまま保つ。 skeleton は雛形で、 agent home は独立したコピーなので、 agent が `.codex/auth.json` などを更新しても skeleton 側には書き戻さない。 session directory は `purge` まで残るため copied secret も残る。 `purge` で session directory を消すと agent home も一緒に消える。短期セッションでは履歴を後から振り返れるし、長期では `purge` 一発で掃除できる。

セッション開始時の git snapshot は `data/` だけを追跡するので、 `home/agent/.codex/auth.json` のような agent home 配下のファイルは session git repo に入らない。

## Docker 環境変数設計

harness は以下の環境変数を runner にエクスポートする:

| 変数 | 意味 |
|---|---|
| `REHEARSE_SESSION_DIR` | session directory (host path) |
| `REHEARSE_AGENT_WORK_DIR` | agent work dir (`data/`) の host path |
| `REHEARSE_AGENT_HOME` | agent home (`home/agent/`) の host path (= container 内 `/home/agent` の bind 元) |
| `REHEARSE_SESSION_RUN_LOCK` | run 中だけ runner が `flock` で保持する session lock |
| `REHEARSE_SESSION_A` | A の host path (RO mount に使う) |
| `REHEARSE_SESSION_B` | B の host path (RO mount に使う) |
| `REHEARSE_AGENT_IMAGE` | 使う image |
| `REHEARSE_AGENT_UID` / `REHEARSE_AGENT_GID` | container user |
| `REHEARSE_AGENT_TIMEOUT` | container 内で `timeout` が agent CLI に与える秒数 |
| `REHEARSE_RUNNER_MODE` | `run` または `debug` |
| `REHEARSE_DEBUG_ENTRYPOINT` | debug mode で Docker entrypoint にする command |

runner は上記だけを使って `docker run` を組み立て、 container の exit code を自分の exit code としてそのまま返す。 harness はその数字だけを観察する。`debug` は同じ runner 契約で agent image を起動し、Docker の entrypoint だけを差し替える。これにより `/bin/bash` で agent home を確認したり、`/opt/rehearse/entrypoint.sh` を手動起動して通常 run と同じ経路を再現できる。

`running` は Docker など特定の runtime ではなく、 `REHEARSE_SESSION_RUN_LOCK` の `flock` から導出する。 runner が lock を握っている間だけ `status` / `commit` / `purge` は session を実行中として扱う。プロセス終了時には OS が lock を解放するため、 `Ctrl+C` や runner crash の後に stale な `running` が残らない。

これらの `REHEARSE_AGENT_*` は harness と runner の内部契約であり、ユーザー向け設定ではない。ユーザーは `$REHEARSE_ROOT/profiles/<name>.json` に `agent` / `agent_image` / `agent_uid` / `guard_uid` / `agent_timeout` などを書き、 `rehearse create -p <name> ...` で session に転記する。 guard UID/GID は create 時の ownership setup にだけ使い、 runner には渡さない。

provider API key のような agent process 用の環境変数は runner から pass-through しない。 skeleton に `.rehearse/agent/init.sh` を置くと、 entrypoint が agent CLI 起動前に source する。これにより `.codex/config.toml` や Claude Code の agent home 配下設定と、 `OPENROUTER_API_KEY` のような provider 固有設定を同じ skeleton に閉じ込められる。`init.sh` は通常の shell script なので、agent process に渡したい値は `export` する。

## agent runner: harness と agent の境界

`docker run` の組み立ては **bash スクリプト (`scripts/docker-runner.sh`) に外出し**してある。 Python (`run.run_agent`) はもはや agent コンテナの docker コマンドを知らず、 runner を `subprocess.run` で起動して exit code を受け取るだけの薄い wrapper になっている。

同じ方針で、 root 権限が必要な `chown` / `cleanup` は `scripts/docker-helper.sh` に外出ししている。 Python は helper image、広めに mount する親ディレクトリ、実行したいコマンドだけを渡す。Docker 以外へ寄せる場合は runner と helper の 2 箇所が runtime 境界になる。

理由は二つ:

1. **テスタビリティ**: 本物の agent image と API key / auth cache を要求すると lifecycle テストが回せない。 profile の `agent_runner` を `tests/fake-runner.sh` に差し替えると、 busybox だけで Step 2 相当のテストが動く
2. **agent の交換可能性**: 将来 Codex CLI / Claude Code を OpenCode やローカル LLM ベースの agent に差し替えるとき、 Python 側を一切いじらず、 runner script を新しい agent 用に書き直すだけで済む
