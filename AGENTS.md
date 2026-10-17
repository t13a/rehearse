# rehearse

AI エージェントに大容量ファイルの整理を任せるためのハーネス。 symlink をステージングに使い、実ファイルは人間のレビュー後まで一切動かさない。 agent は隔離された Docker コンテナの中で作業ディレクトリの `inbox/` `outbox/` だけを操作する。

## ドキュメント

下記を必要に応じて参照する。

- [README.md](README.md) — 本プロジェクトの概要説明とチュートリアル
- [instructions/default.md](instructions/default.md) — ハーネス内で動作する AI エージェントの既定の指示

## 開発メモ

- パッケージマネージャ: `uv`。 `uv sync` / `uv run rehearse …` / `uv run pytest`
- Codex agent image のビルドは `bash scripts/build-agent-codex-image.sh` (既定タグ `rehearse-agent-codex:latest`)
- Claude Code agent image のビルドは `bash scripts/build-agent-claude-image.sh` (既定タグ `rehearse-agent-claude:latest`)
- agent コンテナは profile の `agent_uid/gid` (既定は host UID/GID) で起動する。 B mirror の初期構造は `guard_uid/gid` (既定 65534:65534) 所有の sticky directory で守り、agent が持ち込んだ配置物は host 側から手動編集しやすくする。 session directory cleanup は `rehearse delete` 経由 (内部で root コンテナ越しに `rm -rf`)
- ユーザー向け host 環境変数は `REHEARSE_ROOT` のみ。 agent / Docker の設定は `$REHEARSE_ROOT/profiles/*.json`、 agent home の雛形と agent process 用 secret / init は `$REHEARSE_ROOT/skeletons/*` で管理
- Python (`run.run_agent`) は docker コマンドを直接知らない。 agent 起動は bash script (`scripts/docker-runner.sh`) に外出しされており、 profile の `agent_runner` を差し替えるとテスト用 fake runner や別 runtime (Podman 等) に切り替わる
- テストは `tests/fake-runner.sh` (busybox ベース) を使うので agent image も API key も不要。 docker さえあれば `uv run pytest` が回る
