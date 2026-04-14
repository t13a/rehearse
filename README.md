# rehearse

AI エージェントに大容量ファイルの整理を任せるためのハーネス。 symlink をステージングに使い、実ファイルは人間のレビュー後まで一切動かさない。

設計の詳細は [CLAUDE.md](CLAUDE.md) と [docs/](docs/) を参照。

## 必要環境

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Docker (daemon が起動していること)
- `ANTHROPIC_API_KEY` (本物の agent を `rehearse run` で動かす場合のみ。テスト実行には不要)

## セットアップ

```bash
uv sync
```

`.venv/` に依存を入れて、 `rehearse` コマンドが `uv run` 経由で呼べる状態になる。

## agent image のビルド

`rehearse run` は既定で `rehearse-agent:latest` という image を呼ぶ。初回は手元でビルドする:

```bash
bash scripts/build-agent-image.sh
```

中身は `node:20-slim` ベースで Claude Code CLI と道具箱 (`findutils` / `tree` 等) を入れ、 `rm` / `cp` / `ln` / `chmod` / `chown` / `dd` / `truncate` を Dockerfile の最終層で削る。詳細は [docker/agent/Dockerfile](docker/agent/Dockerfile) と [docs/architecture.md](docs/architecture.md) のツールボックス節を参照。

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

事前に image をビルドして API キーをエクスポートする:

```bash
bash scripts/build-agent-image.sh
export ANTHROPIC_API_KEY=sk-ant-...
```

A と B を適当に作って `create` → `run` → `status` → `discard` → `purge` と一周させる例:

```bash
mkdir -p /tmp/fakeA/sub /tmp/fakeB/existing
echo hello > /tmp/fakeA/file1.txt
echo nested > /tmp/fakeA/sub/file2.txt
echo legacy > /tmp/fakeB/existing/old.txt

SID=$(uv run rehearse create /tmp/fakeA /tmp/fakeB)
uv run rehearse status
uv run rehearse run "$SID"            # Claude Code 起動。終わると outbox/.done が生える
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

## 環境変数

全て `REHEARSE_` 接頭辞。既定値は [src/rehearse/config.py](src/rehearse/config.py) 参照。

| 変数 | 既定値 | 用途 |
|---|---|---|
| `REHEARSE_ROOT` | `~/.local/share/rehearse` | workspace / lock の置き場 |
| `REHEARSE_AGENT_UID` | `10000` | agent コンテナを走らせる UID |
| `REHEARSE_AGENT_GID` | `10000` | 同 GID |
| `REHEARSE_AGENT_IMAGE` | `rehearse-agent:latest` | agent コンテナの image |
| `REHEARSE_HELPER_IMAGE` | `busybox:latest` | chown / cleanup 用の root コンテナ image |
| `REHEARSE_AGENT_RUNNER` | `<repo>/scripts/run-agent-cc.sh` | agent を起動する bash スクリプト。差し替えれば別の agent (OpenCode 等) やテスト用の fake runner に切り替えられる |
| `REHEARSE_AGENT_TIMEOUT` | `3600` | container 内で `timeout` が `claude` に与える秒数 |
| `REHEARSE_MCP_CONFIG` | (未設定) | Claude Code ネイティブ形式の MCP 設定 JSON のパス。指定すると container に RO mount され `claude --mcp-config` に渡される |
| `REHEARSE_AGENT_EXTRA_ARGS` | (未設定) | `claude` コマンドに渡す追加引数 (スペース区切り)。例: `--output-format stream-json --verbose --include-partial-messages` |
| `ANTHROPIC_API_KEY` | (未設定) | 既定 runner が必須として要求。 host の環境変数から container に pass-through される |

### MCP 設定の例

リモート MCP サーバーをひとつ繋ぐ最小例:

```json
{
  "mcpServers": {
    "fetch": {
      "type": "http",
      "url": "https://example.com/mcp"
    }
  }
}
```

これを `REHEARSE_MCP_CONFIG=/path/to/mcp.json` で渡すと、 agent から `mcp__fetch__*` ツールが見える。 image を再ビルドする必要はない。

### runner の差し替え

既定の `scripts/run-agent-cc.sh` は Claude Code 用。別の agent を試したいときや、 API キー無しで挙動だけ確認したいときは:

```bash
REHEARSE_AGENT_RUNNER=/path/to/your-runner.sh \
REHEARSE_AGENT_IMAGE=your-image:latest \
  uv run rehearse run "$SID"
```

runner script は環境変数 `REHEARSE_SESSION_*` / `REHEARSE_AGENT_*` から必要な情報を受け取る。契約の詳細は [docs/architecture.md](docs/architecture.md) の「agent runner」節を参照。テスト時に同じ仕組みで使われる軽量 runner は [tests/fake-runner.sh](tests/fake-runner.sh) にある。

## 後片付けの注意

agent コンテナが UID 10000 で動くため、 `inbox/` の symlink や agent が `outbox/` に持ち込んだ symlink は**通常ユーザーからは `rm` できない**。 workspace を消すときは必ず:

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
- ✅ Step 2: 最小ハーネスのコード
- ✅ Step 3: Dockerfile + Claude Code 起動 + MCP 取り込み
- ✅ Step 4: commit アルゴリズム
