# rehearse

AI エージェントに複雑なファイル整理を任せるためのハーネス。 symlink をステージングに使い、 sticky bit でファイルレイアウトを保護し、 Docker で AI エージェントの作業環境を隔離する。人間によるレビューでは AI エージェントの作業結果 (移動計画) を Git 等の好きなツールで確認でき、手動による微調整や AI エージェントへの追加指示が可能。移動計画の確定後、全ファイルを一気に移動する。

## ドキュメント

- [docs/overview.md](docs/overview.md) — 問題設定、symlink ステージングの着想、不変条件
- [docs/cli.md](docs/cli.md) — コマンドと環境変数
- [docs/sessions.md](docs/sessions.md) — ディレクトリレイアウト、状態遷移、規約
- [docs/mirroring.md](docs/mirroring.md) — 作業ディレクトリの役割、 sticky bit によるパーミッションモデル
- [docs/isolation.md](docs/isolation.md) — Docker マウント、道具箱
- [docs/profiles.md](docs/profiles.md) — セッションの実行時設定
- [docs/review.md](docs/review.md) — 人間によるレビュー方法
- [docs/commit.md](docs/commit.md) — 冪等な commit アルゴリズム

## 必要環境

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Docker Daemon
- agent の認証情報 (`~/.codex/auth.json` 等)

## セットアップ

```bash
uv sync
```

`.venv/` に依存を入れて、 `rehearse` コマンドが `uv run` 経由で呼べる状態になる。

## agent image のビルド

初回は手元でビルドする:

```bash
bash scripts/build-agent-codex-image.sh  # Codex CLI 用
bash scripts/build-agent-claude-image.sh # Claude Code 用
```

## テスト

```bash
uv run pytest -v
```

## 手動で動かす

以下は Codex CLI の例。

事前に image をビルド:

```bash
bash scripts/build-agent-codex-image.sh
```

Codex CLI の認証情報を用意する。 ChatGPT login cache や provider API key の持ち込み方法は [docs/profiles.md](docs/profiles.md) の Agent home skeleton を参照。

A と B を適当に作って `create` → `run` → `status` → `commit` → `delete` と一周させる例:

```bash
mkdir -p /tmp/fakeA/sub /tmp/fakeB/existing
echo hello > /tmp/fakeA/file1.txt
echo nested > /tmp/fakeA/sub/file2.txt
echo legacy > /tmp/fakeB/existing/old.txt

SID=$(uv run rehearse create /tmp/fakeA /tmp/fakeB)
uv run rehearse status
uv run rehearse run "$SID"            # Codex CLI 起動。成功すると outbox/.done が生える
uv run rehearse status "$SID"
ls ~/.local/share/rehearse/sessions/"$SID"/work/outbox/
(cd ~/.local/share/rehearse/sessions/"$SID" && git status)
uv run rehearse commit "$SID"         # outbox/ の配置に従って A→B にファイル移動
uv run rehearse delete "$SID"
```

セッション ID を自分で決めたい場合は `-s` を指定する。使える文字は profile 名と同じ英数字、 `_`、`-`、`.`:

```bash
uv run rehearse create -s music-2026-04 /tmp/fakeA /tmp/fakeB
```

セッションの作業ディレクトリを覗きたいとき:

```bash
uv run rehearse exec "$SID" pwd
uv run rehearse exec "$SID" tree
uv run rehearse exec "$SID" git status -u
```

Docker コンテナの中に入って作業ディレクトリを覗いたり、エージェントを手動実行したいとき:

```bash
uv run rehearse debug "$SID" bash
uv run rehearse debug "$SID" codex --help
uv run rehearse debug "$SID" /opt/rehearse/entrypoint.sh
```

## 後片付けの注意

セッションの作業ディレクトリにはホスト側ユーザーの権限では消せないファイルが作成される。これは [sticky bit によるパーミッションモデル](docs/mirroring.md) の副産物。セッションの作業ディレクトリを消す場合は:

```bash
uv run rehearse delete <session_id>
```

を実行すればよい。内部で Docker コンテナが root 権限で `rm -rf` する。
