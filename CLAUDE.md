# rehearse

AI エージェントに大容量ファイルの整理を任せるためのハーネス。 symlink をステージングに使い、実ファイルは人間のレビュー後まで一切動かさない。 agent は隔離された Docker コンテナの中で workspace の `inbox/` `outbox/` だけを操作する。

## 設計ドキュメント

設計の背景・詳細は [docs/](docs/) を参照。実装・変更前に必ず一読する:

- [docs/overview.md](docs/overview.md) — 問題設定、symlink ステージングの着想、不変条件
- [docs/architecture.md](docs/architecture.md) — workspace レイアウト、 Docker マウント、道具箱、 sticky bit によるパーミッションモデル
- [docs/lifecycle.md](docs/lifecycle.md) — セッションの状態、コマンド (`commit` / `discard` / `purge`)、 `.done` / `.FYI.md` 規約
- [docs/commit.md](docs/commit.md) — 冪等な commit アルゴリズム

## プロンプト

- [prompts/agent.md](prompts/agent.md) — Docker コンテナ内で起動する agent (Claude Code) に渡すシステムプロンプト

## 実装ステップ

設計議論の結論として、以下の順で実装を進める:

1. ✅ **エージェント向けシステムプロンプト** — [prompts/agent.md](prompts/agent.md)
2. ✅ **最小ハーネスのコード** — Python + uv + argparse。 CLI 6 コマンド (`create` / `run` / `status` / `discard` / `purge` / `commit`)。事前検証、 sticky bit 付き workspace 構築、 chown コンテナによる `inbox/` の agent UID ハンドオフ、 busybox placeholder の agent 実行、 git スナップショットまで。 pytest で lifecycle を end-to-end テスト
3. ✅ **Dockerfile + Claude Code 起動 + MCP 取り込み** — `node:20-slim` ベースの `rehearse-agent` image (`docker/agent/Dockerfile`)、禁則ツールを最終層で削除、 `/opt/rehearse/scripts/` をローカルツール置き場として PATH に登録。 `docker run` 本体は `scripts/run-agent-cc.sh` に外出しして profile の `agent_runner` で差し替え可能。 entrypoint が `timeout ${REHEARSE_AGENT_TIMEOUT} claude --print --permission-mode bypassPermissions ...` を起動。 MCP 設定は profile の `mcp_config` から RO mount で注入。 agent home は `workspace/home/agent` ↔ `/home/agent`
4. ✅ **commit スクリプトの実装** — [docs/commit.md](docs/commit.md) の擬似コードを実コードに。 `src/rehearse/commit.py` に冪等な commit アルゴリズム、 JSONL の `commit.log` で操作履歴を記録

コア 1〜4 だけでエンドツーエンドに動く。レビュー UI / TUI などの装飾はあとから。

## 開発メモ

- パッケージマネージャ: `uv`。 `uv sync` / `uv run rehearse …` / `uv run pytest`
- agent image のビルドは `bash scripts/build-agent-image.sh` (既定タグ `rehearse-agent:latest`)
- agent コンテナは profile の `agent_uid` (既定 10000) で起動するため、 `inbox/` の symlink や agent が `outbox/` に持ち込んだ symlink は **harness UID からは直接削除できない**。 cleanup はすべて `rehearse purge` 経由 (内部で root コンテナ越しに `rm -rf`)
- ユーザー向け環境変数は `REHEARSE_ROOT` のみ。 agent / Docker の設定は `$REHEARSE_ROOT/profiles/*.json` で管理
- Python (`docker.run_agent`) は docker コマンドを直接知らない。 agent 起動は bash script (`scripts/run-agent-cc.sh`) に外出しされており、 profile の `agent_runner` を差し替えるとテスト用 fake runner や別 agent (OpenCode 等) に切り替わる
- テストは `tests/fake-runner.sh` (busybox ベース) を使うので `rehearse-agent` image も `ANTHROPIC_API_KEY` も不要。 docker さえあれば `uv run pytest` が回る

## 現在の状態

2026-04-12: Step 4 完了。コア 4 ステップすべて揃い、 end-to-end の実運用が可能。`resume` は `run` に統合済み (`run -m` で追加指示、entrypoint が会話履歴を自動検出して `--continue`)。残りはレビュー UI / TUI 等の装飾。
