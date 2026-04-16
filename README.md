# rehearse

AI エージェントに大容量ファイルの整理を任せるためのハーネス。 symlink をステージングに使い、実ファイルは人間のレビュー後まで一切動かさない。

設計の詳細は [CLAUDE.md](CLAUDE.md) と [docs/](docs/) を参照。

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

中身は `node:20-slim` ベースで Codex CLI、TLS ルート証明書、道具箱 (`findutils` / `tree` 等) を入れ、 `rm` / `cp` / `ln` / `chmod` / `chown` / `dd` / `truncate` を Dockerfile の最終層で削る。Codex 自体の sandbox は使わず、Docker の bind mount と agent UID を境界にする。詳細は [docker/codex/Dockerfile](docker/codex/Dockerfile) と [docs/architecture.md](docs/architecture.md) のツールボックス節を参照。

Claude Code agent を使う場合は別 image をビルドする:

```bash
bash scripts/build-agent-cc-image.sh
```

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

事前に image をビルドし、Codex CLI の認証情報を用意する。ChatGPT login cache や provider API key は [Home skeleton](#home-skeleton) で持ち込む:

```bash
bash scripts/build-agent-codex-image.sh
```

A と B を適当に作って `create` → `run` → `status` → `discard` → `purge` と一周させる例:

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
uv run rehearse discard "$SID"
uv run rehearse purge "$SID"
```

`create` 直後の workspace を覗きたいとき:

```bash
ls -la ~/.local/share/rehearse/sessions/$SID/data/
stat -c '%a %U:%G %n' ~/.local/share/rehearse/sessions/$SID/data/outbox
```

- `inbox/` は agent UID (既定 10000:10000) 所有
- `outbox/` とサブディレクトリは `1777` (sticky、 harness 所有)

## プロファイル

実行時設定は profile JSON に書く。 `rehearse create -p <profile> ...` で指定でき、 `-p` を省略すると `default` profile が使われる。 profile は session 作成時に `meta.json` へ転記されるので、後から profile JSON を編集しても既存 session には影響しない。

profile は `$REHEARSE_ROOT/profiles/<name>.json` に置く。 `default` profile は初回 `create` 時に `{}` として自動作成される。各項目は省略可能で、省略時は CLI 側の既定値を使う。相対パスは `$REHEARSE_ROOT` 起点で解決される。

```json
{
  "agent": "codex",
  "agent_image": "rehearse-agent-codex:latest",
  "helper_image": "busybox:latest",
  "agent_runner": "runners/my-agent.sh",
  "agent_uid": 10000,
  "agent_gid": 10000,
  "agent_timeout": 3600,
  "agent_extra_args": "--output-format stream-json --verbose",
  "skeleton": "codex"
}
```

| 項目 | 既定値 | 用途 |
|---|---|---|
| `agent` | `codex` | 標準 agent 種別 (`codex` / `claude-code`) |
| `agent_uid` | `10000` | agent コンテナを走らせる UID |
| `agent_gid` | `10000` | 同 GID |
| `agent_image` | `rehearse-agent-codex:latest` | agent コンテナの image。 `agent` の標準値を上書きする |
| `helper_image` | `busybox:latest` | `scripts/docker-helper.sh` が chown / cleanup に使う root コンテナ image |
| `agent_runner` | `<repo>/scripts/docker-runner.sh` | agent image を起動する runner。 Podman 等に差し替える場合に上書きする |
| `agent_timeout` | `3600` | container 内で `timeout` が agent CLI に与える秒数 |
| `agent_extra_args` | `null` | agent CLI に渡す追加引数 (スペース区切り) |
| `skeleton` | `default` | `sessions/<id>/home/agent/` にコピーする home skeleton 名 |

## Home skeleton

agent の home 初期状態は `$REHEARSE_ROOT/skeletons/<name>/` に置ける。 `rehearse create` は profile の `skeleton` で指定された skeleton を `sessions/<id>/home/agent/` にコピーし、その後 agent UID/GID に chown する。 symlink は symlink のままコピーされる。

`skeleton` 未指定時は `default`。 `skeletons/default/` は初回 `create` 時に空ディレクトリとして自動作成されるので、後から自由にカスタマイズできる。

Codex CLI 用に ChatGPT login cache を持ち込む例。 headless 環境へ `~/.codex/auth.json` をコピーする方法は [OpenAI の Codex authentication docs](https://developers.openai.com/codex/auth#login-on-headless-devices) でも案内されている。

```bash
mkdir -p "$HOME/.local/share/rehearse/skeletons/codex/.codex"
cp "$HOME/.codex/auth.json" \
  "$HOME/.local/share/rehearse/skeletons/codex/.codex/auth.json"

cat > "$HOME/.local/share/rehearse/profiles/codex.json" <<'JSON'
{
  "agent": "codex",
  "skeleton": "codex"
}
JSON
```

agent 起動前に環境変数や PATH を調整したい場合は、 skeleton に `.rehearse/agent/init.sh` を置く。 entrypoint は agent CLI を起動する前にこのファイルを source する。通常の shell script なので、agent process に渡したい環境変数は明示的に `export` する:

```bash
mkdir -p "$HOME/.local/share/rehearse/skeletons/codex/.rehearse/agent"
cat > "$HOME/.local/share/rehearse/skeletons/codex/.rehearse/agent/init.sh" <<'SH'
export OPENROUTER_API_KEY=sk-or-...
export PATH="$HOME/bin:$PATH"
SH
```

`.rehearse/agent/init.sh` は agent startup 用の escape hatch で、 provider API key などの secret を含み得る。 `auth.json` と同様に password と同じ扱いにすること。 session の git snapshot は `data/` だけを追跡するため `home/agent/.codex/auth.json` や `home/agent/.rehearse/agent/init.sh` は記録されない。 `discard` は workspace を残すので copied secret も残り、 `purge` で削除される。

## 環境変数

ユーザー向けの host 環境変数は `REHEARSE_ROOT` だけ。 agent / Docker / skeleton の設定は profile JSON と skeleton に書く。 provider API key は host から pass-through せず、 skeleton の `.rehearse/agent/init.sh` か agent ネイティブ設定に置く。

| 変数 | 既定値 | 用途 |
|---|---|---|
| `REHEARSE_ROOT` | `~/.local/share/rehearse` | workspace / lock / profile / skeleton の置き場 |

MCP など agent 固有の設定は profile ではなく、 skeleton に含める agent-native config に置く。Codex なら `.codex/config.toml`、Claude Code なら Claude Code が読む home 配下の設定ファイルを skeleton で持ち込む。

### runner の差し替え

既定の `scripts/docker-runner.sh` は Docker で agent image を起動する。Claude Code を使う場合は:

```bash
mkdir -p "$HOME/.local/share/rehearse/profiles"
cat > "$HOME/.local/share/rehearse/profiles/claude-code.json" <<'JSON'
{
  "agent": "claude-code"
}
JSON
```

別の agent を試したいときや、 API キー無しで挙動だけ確認したいときは:

```bash
mkdir -p "$HOME/.local/share/rehearse/profiles"
cat > "$HOME/.local/share/rehearse/profiles/opencode.json" <<'JSON'
{
  "agent_runner": "/path/to/your-runner.sh",
  "agent_image": "your-image:latest"
}
JSON

uv run rehearse create -p opencode /tmp/fakeA /tmp/fakeB
```

runner script は環境変数 `REHEARSE_SESSION_*` / `REHEARSE_AGENT_*` から必要な情報を受け取る。契約の詳細は [docs/architecture.md](docs/architecture.md) の「agent runner」節を参照。テスト時に同じ仕組みで使われる軽量 runner は [tests/fake-runner.sh](tests/fake-runner.sh) にある。

## 後片付けの注意

agent コンテナが UID 10000 で動くため、 `inbox/` の symlink や agent が `outbox/` に持ち込んだ symlink は**通常ユーザーからは `rm` できない**。 skeleton からコピーした `home/agent/` 内の secret も session と一緒に残る。 workspace を消すときは必ず:

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

## 現在の実装状況

- ✅ Step 1: agent プロンプト ([prompts/agent.md](prompts/agent.md))
- ✅ Step 2: 最小ハーネスのコード
- ✅ Step 3: Dockerfile + Codex CLI / Claude Code 起動 + skeleton 設定
- ✅ Step 4: commit アルゴリズム
