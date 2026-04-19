# rehearse

AI エージェントに大容量ファイルの整理を任せるためのハーネス。 symlink をステージングに使い、実ファイルは人間のレビュー後まで一切動かさない。

## ドキュメント

背景・詳細は [docs/](docs/) を参照。

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
- Docker (daemon が起動していること)
- agent の認証情報 (skeleton で持ち込む `.codex/auth.json` や `.rehearse/agent/init.sh`)

## セットアップ

```bash
uv sync
```

`.venv/` に依存を入れて、 `rehearse` コマンドが `uv run` 経由で呼べる状態になる。

## agent image のビルド

`rehearse run` は既定で Codex CLI agent (`rehearse-agent-codex:latest`) を呼ぶ。初回は手元でビルドする:

```bash
bash scripts/build-agent-codex-image.sh
```

中身は `node:20-slim` ベースで Codex CLI、TLS ルート証明書、道具箱 (`findutils` / `tree` 等) を入れ、 `rm` / `cp` / `ln` / `chmod` / `chown` / `dd` / `truncate` を Dockerfile の最終層で削る。Codex 自体の sandbox は使わず、Docker の bind mount と agent UID を境界にする。詳細は [docker/codex/Dockerfile](docker/codex/Dockerfile) と [docs/profiles.md](docs/profiles.md) の Toolbox 節を参照。

Claude Code agent を使う場合は別 image をビルドする:

```bash
bash scripts/build-agent-claude-image.sh
```

## テスト

```bash
uv run pytest -v
```

docker を必要とするテストには `@pytest.mark.docker` が付いている。 docker が使えない環境では conftest の fixture が自動で skip する。

個別に走らせたい場合:

```bash
uv run pytest tests/test_validate.py -v   # docker 不要
uv run pytest tests/test_session.py -v    # 一部 docker 必須
uv run pytest tests/test_cli.py -v        # docker 必須
```

## 手動で動かす

事前に image をビルドし、Codex CLI の認証情報を用意する。ChatGPT login cache や provider API key は [Home skeleton](#home-skeleton) で持ち込む:

```bash
bash scripts/build-agent-codex-image.sh
```

A と B を適当に作って `create` → `run` → `status` → `commit` → `purge` と一周させる例:

```bash
mkdir -p /tmp/fakeA/sub /tmp/fakeB/existing
echo hello > /tmp/fakeA/file1.txt
echo nested > /tmp/fakeA/sub/file2.txt
echo legacy > /tmp/fakeB/existing/old.txt

SID=$(uv run rehearse create /tmp/fakeA /tmp/fakeB)
uv run rehearse status
uv run rehearse run "$SID"            # Codex CLI 起動。終わると outbox/.done が生える
uv run rehearse status "$SID"
ls ~/.local/share/rehearse/sessions/"$SID"/data/outbox/
(cd ~/.local/share/rehearse/sessions/"$SID" && git status)
uv run rehearse commit "$SID"         # outbox/ の配置に従って A→B にファイル移動
uv run rehearse purge "$SID"
```

セッション ID を自分で決めたい場合は `-s` を指定する。使える文字は profile 名と同じ英数字、 `_`、`-`、`.`:

```bash
uv run rehearse create -s music-2026-04 /tmp/fakeA /tmp/fakeB
```

セッションの作業ディレクトリを覗きたいとき:

```bash
uv run rehearse exec "$SID" ls -la
uv run rehearse exec "$SID" stat -c '%a %U:%G %n' outbox
```

- `inbox/` は agent UID/GID 所有
- `outbox/` とサブディレクトリは `1777` (sticky、 guard UID/GID 所有)

agent image の中で手動確認したいときは `debug` を使う。mount、UID/GID、lock、状態更新は `run` と同じで、entrypoint だけを差し替える。端末から実行した場合は interactive TTY も渡す:

```bash
uv run rehearse debug "$SID" bash
uv run rehearse debug "$SID" codex --help
uv run rehearse debug "$SID" /opt/rehearse/entrypoint.sh
```

## 後片付けの注意

agent UID/GID の既定値は host UID/GID なので、agent が agent work dir の `outbox/` に持ち込んだ配置物や agent home (`home/agent/`) は host 側から手動編集しやすい。一方、B mirror の初期構造は guard UID/GID 所有の sticky directory で守られる。 skeleton からコピーした `home/agent/` 内の secret も session と一緒に残る。 session directory を丸ごと消すときは必ず:

```bash
uv run rehearse purge <session_id>
```

を経由すること。内部で `scripts/docker-helper.sh` 経由の root コンテナを 1 発叩いて `rm -rf` する。

手動で `~/.local/share/rehearse/sessions/` を掃除したくなったら、同じ理屈で:

```bash
docker run --rm --user 0:0 \
  -v "$HOME/.local/share/rehearse:$HOME/.local/share/rehearse:rw" \
  busybox:latest \
  rm -rf "$HOME/.local/share/rehearse/sessions"
```
