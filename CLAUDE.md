# rehearse

AI エージェントに大容量ファイルの整理を任せるためのハーネス。 symlink をステージングに使い、実ファイルは人間のレビュー後まで一切動かさない。 agent は隔離された Docker コンテナの中で作業ディレクトリの `inbox/` `outbox/` だけを操作する。

## 設計ドキュメント

設計の背景・詳細は [docs/](docs/) を参照。実装・変更前に必ず一読する:

- [docs/overview.md](docs/overview.md) — 問題設定、symlink ステージングの着想、不変条件
- [docs/architecture.md](docs/architecture.md) — ディレクトリレイアウト、 Docker マウント、道具箱、 sticky bit によるパーミッションモデル
- [docs/lifecycle.md](docs/lifecycle.md) — セッションの状態、コマンド (`commit` / `purge`)、 `.done` / `.FYI.md` 規約
- [docs/commit.md](docs/commit.md) — 冪等な commit アルゴリズム

## Agent instructions

- [instructions/default.md](instructions/default.md) — session 作成時に agent work dir (`data/AGENTS.md`) へコピーする既定の agent instructions

## 実装ステップ

設計議論の結論として、以下の順で実装を進める:

1. ✅ **エージェント向け instructions** — [instructions/default.md](instructions/default.md)
2. ✅ **最小ハーネスのコード** — Python + uv + argparse。 CLI 6 コマンド (`create` / `run` / `status` / `purge` / `commit` / `exec`)。事前検証、 sticky bit による作業ディレクトリ保護、 chown コンテナによる `inbox/` の agent UID ハンドオフ、 busybox placeholder の agent 実行、 git スナップショットまで。 pytest で lifecycle を end-to-end テスト
3. ✅ **Dockerfile + agent 起動 + MCP 取り込み** — `node:20-slim` ベースの Codex CLI image (`docker/codex/Dockerfile`) と Claude Code image (`docker/claude/Dockerfile`)、禁則ツールを最終層で削除。 `docker run` 本体は runner script に外出しして profile の `agent` / `agent_runner` で差し替え可能。 Codex は既定 agent、Claude Code は `agent: "claude"` で選択。 agent home は `sessions/<id>/home/agent` ↔ `/home/agent`
4. ✅ **commit スクリプトの実装** — [docs/commit.md](docs/commit.md) の擬似コードを実コードに。 `src/rehearse/commit.py` に冪等な commit アルゴリズム、 JSONL の `commit.log` で操作履歴を記録

コア 1〜4 だけでエンドツーエンドに動く。レビュー UI / TUI などの装飾はあとから。

## 開発メモ

- パッケージマネージャ: `uv`。 `uv sync` / `uv run rehearse …` / `uv run pytest`
- Codex agent image のビルドは `bash scripts/build-agent-codex-image.sh` (既定タグ `rehearse-agent-codex:latest`)
- Claude Code agent image のビルドは `bash scripts/build-agent-claude-image.sh` (既定タグ `rehearse-agent-claude:latest`)
- agent コンテナは profile の `agent_uid/gid` (既定は host UID/GID) で起動する。 B mirror の初期構造は `guard_uid/gid` (既定 65534:65534) 所有の sticky directory で守り、agent が持ち込んだ配置物は host 側から手動編集しやすくする。 session directory cleanup は `rehearse purge` 経由 (内部で root コンテナ越しに `rm -rf`)
- ユーザー向け host 環境変数は `REHEARSE_ROOT` のみ。 agent / Docker の設定は `$REHEARSE_ROOT/profiles/*.json`、 agent home の雛形と agent process 用 secret / init は `$REHEARSE_ROOT/skeletons/*` で管理
- Python (`run.run_agent`) は docker コマンドを直接知らない。 agent 起動は bash script (`scripts/docker-runner.sh`) に外出しされており、 profile の `agent_runner` を差し替えるとテスト用 fake runner や別 runtime (Podman 等) に切り替わる
- テストは `tests/fake-runner.sh` (busybox ベース) を使うので agent image も API key も不要。 docker さえあれば `uv run pytest` が回る

## 現在の状態

2026-04-15: Codex CLI を既定 agent に変更し、Claude Code は profile の `agent: "claude"` で選択する構成に移行。`resume` は `run` に統合済み (`run -m` で追加指示、entrypoint が会話履歴を自動検出して agent ごとの再開モードを使う)。残りはレビュー UI / TUI 等の装飾。
