# rehearse

AI エージェントに大容量ファイルの整理を任せるためのハーネス。 symlink をステージングに使い、実ファイルは人間のレビュー後まで一切動かさない。 agent は隔離された Docker コンテナの中で workspace の `c/` `d/` だけを操作する。

## 設計ドキュメント

設計の背景・詳細は [docs/](docs/) を参照。実装・変更前に必ず一読する:

- [docs/overview.md](docs/overview.md) — 問題設定、symlink ステージングの着想、不変条件
- [docs/architecture.md](docs/architecture.md) — workspace レイアウト、 Docker マウント、道具箱、 sticky bit によるパーミッションモデル
- [docs/lifecycle.md](docs/lifecycle.md) — セッションの状態、コマンド (`commit` / `discard` / `resume` / `purge`)、 `.done` / `.FYI.md` 規約
- [docs/commit.md](docs/commit.md) — 冪等な commit アルゴリズム

## プロンプト

- [prompts/agent.md](prompts/agent.md) — Docker コンテナ内で起動する agent (Claude Code) に渡すシステムプロンプト

## 実装ステップ

設計議論の結論として、以下の順で実装を進める:

1. ✅ **エージェント向けシステムプロンプト** — [prompts/agent.md](prompts/agent.md)
2. **最小ハーネスのコード** — workspace 作成と C/D 構築スクリプト (shell か Python)。事前検証 (同一 fs、 symlink 非混入、 flock) と sticky bit 付きの B-mirror 構築もここで
3. **Dockerfile の設計** — image に入れる道具箱、 Claude Code の呼び出し方、 MCP 経由の Web 検索セットアップ
4. **commit スクリプトの実装** — [docs/commit.md](docs/commit.md) の擬似コードを実コードに

コア 1〜4 だけでエンドツーエンドに動く。 `resume` / `purge` / レビュー UI / TUI などの装飾はあとから。

## 現在の状態

2026-04-11: Step 1 完了。次は Step 2 (最小ハーネスのコード) に着手する。
