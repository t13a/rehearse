# rehearse

AI エージェントに大容量ファイルの整理を任せるためのハーネス。 symlink をステージングに使い、実ファイルは人間のレビュー後まで一切動かさない。

設計の詳細は [CLAUDE.md](CLAUDE.md) と [docs/](docs/) を参照。

## 必要環境

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Docker (daemon が起動していること。現状の placeholder agent は `busybox:latest` を pull する)

## セットアップ

```bash
uv sync
```

`.venv/` に依存を入れて、 `rehearse` コマンドが `uv run` 経由で呼べる状態になる。

## テスト

```bash
uv run pytest -v
```

docker を必要とするテストには `@pytest.mark.docker` が付いている。 docker が使えない環境では conftest の fixture が自動で skip する。

個別に走らせたい場合:

```bash
uv run pytest tests/test_validate.py -v   # docker 不要
uv run pytest tests/test_create.py -v     # docker 必須
uv run pytest tests/test_lifecycle.py -v  # docker 必須
```

## 手動で動かす

A と B を適当に作って `create` → `run` → `status` → `discard` → `purge` と一周させる例:

```bash
mkdir -p /tmp/fakeA/sub /tmp/fakeB/existing
echo hello > /tmp/fakeA/file1.txt
echo nested > /tmp/fakeA/sub/file2.txt
echo legacy > /tmp/fakeB/existing/old.txt

SID=$(uv run rehearse create /tmp/fakeA /tmp/fakeB)
uv run rehearse status
uv run rehearse run "$SID"
uv run rehearse status "$SID"
uv run rehearse commit "$SID"    # スタブ。非零終了
uv run rehearse discard "$SID"
uv run rehearse purge "$SID"
```

`create` 直後の workspace を覗きたいとき:

```bash
ls -la ~/.local/share/rehearse/sessions/$SID/data/
stat -c '%a %U:%G %n' ~/.local/share/rehearse/sessions/$SID/data/d
```

- `c/` は agent UID (既定 10000:10000) 所有
- `d/` とサブディレクトリは `1777` (sticky、 harness 所有)

## 環境変数

全て `REHEARSE_` 接頭辞。既定値は [src/rehearse/config.py](src/rehearse/config.py) 参照。

| 変数 | 既定値 | 用途 |
|---|---|---|
| `REHEARSE_ROOT` | `~/.local/share/rehearse` | workspace / lock の置き場 |
| `REHEARSE_AGENT_UID` | `10000` | agent コンテナを走らせる UID |
| `REHEARSE_AGENT_GID` | `10000` | 同 GID |
| `REHEARSE_AGENT_IMAGE` | `busybox:latest` | agent コンテナの image (Step 3 で本物に差し替え) |
| `REHEARSE_HELPER_IMAGE` | `busybox:latest` | chown / cleanup 用の root コンテナ image |

## 後片付けの注意

agent コンテナが UID 10000 で動くため、 `c/` の symlink や agent が `d/` に持ち込んだ symlink は**通常ユーザーからは `rm` できない**。 workspace を消すときは必ず:

```bash
uv run rehearse purge <session_id>
```

を経由すること。内部で root コンテナを 1 発叩いて `rm -rf` する。

手動で `~/.local/share/rehearse/sessions/` を掃除したくなったら、同じ理屈で:

```bash
docker run --rm --user 0:0 \
  -v "$HOME/.local/share/rehearse:$HOME/.local/share/rehearse:rw" \
  busybox:latest \
  rm -rf "$HOME/.local/share/rehearse/sessions"
```

## 現在の実装状況

- ✅ Step 1: agent プロンプト ([prompts/agent.md](prompts/agent.md))
- ✅ Step 2: 最小ハーネスのコード (このコミット)
- ⏳ Step 3: Dockerfile (本物の agent image)
- ⏳ Step 4: commit アルゴリズム
