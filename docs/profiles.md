# Profiles

実行時設定は profile JSON に書く。 `rehearse create -p <profile> ...` で指定でき、 `-p` を省略すると `default` profile が使われる。 profile は session 作成時に `meta.json` へ転記されるので、後から profile JSON を編集しても既存 session には影響しない。

profile は `$REHEARSE_ROOT/profiles/<name>.json` に置く。 `default` profile は初回 `create` 時に `{}` として自動作成される。各項目は省略可能で、省略時は CLI 側の既定値を使う。相対パスは `$REHEARSE_ROOT` 起点で解決される。

```json
{
  "agent": "codex",
  "agent_image": "rehearse-agent-codex:latest",
  "helper_image": "busybox:latest",
  "agent_runner": "runners/my-agent.sh",
  "agent_uid": 1000,
  "agent_gid": 1000,
  "guard_uid": 65534,
  "guard_gid": 65534,
  "agent_instructions": "instructions/music.md",
  "agent_timeout": 3600,
  "agent_extra_args": "--output-format stream-json --verbose",
  "skeleton": "codex"
}
```

| 項目 | 既定値 | 用途 |
|---|---|---|
| `agent` | `codex` | 標準 agent 種別 (`codex` / `claude`) |
| `agent_uid` | host UID | agent コンテナを走らせる UID。既定では現在の host ユーザー UID |
| `agent_gid` | host GID | agent コンテナを走らせる GID。既定では現在の host ユーザー GID |
| `guard_uid` | `65534` | B mirror の初期構造を守る UID。 `agent_uid` と同じ値は不可 |
| `guard_gid` | `65534` | B mirror の初期構造を守る GID |
| `agent_image` | `rehearse-agent-codex:latest` | agent コンテナの image。 `agent` の標準値を上書きする |
| `helper_image` | `busybox:latest` | `scripts/docker-helper.sh` が chown / cleanup に使う root コンテナ image |
| `agent_runner` | bundled `scripts/docker-runner.sh` | agent image を起動する runner。 Podman 等に差し替える場合に上書きする |
| `agent_instructions` | bundled `instructions/default.md` | session 作成時に agent work dir (`work/AGENTS.md`) へコピーする agent instructions。相対パスは `$REHEARSE_ROOT` 起点 |
| `agent_timeout` | `3600` | container 内で `timeout` が agent CLI に与える秒数 |
| `agent_extra_args` | `null` | agent CLI に渡す追加引数 (スペース区切り) |
| `skeleton` | `default` | agent home (`sessions/<id>/home/agent/`) にコピーする home skeleton 名 |

## Agent images

対応中のエージェントは下記の通り。

- Codex (`docker/codex/Dockerfile`)
- Claude Code (`docker/claude/Dockerfile`)

> Note: Claude Code agent image はローカル利用向けです。`docker/claude/Dockerfile` は Anthropic のプロプライエタリ・ソフトウェアである Claude Code をインストールします。ビルド済みの Claude Code agent image は、この repository の MIT license では再配布できません。Anthropic のライセンス条件に従ってください。

エージェント自体の sandbox を無効化し、Docker の bind mount と agent UID を containment boundary とする。

### Toolbox

base image (`node:20-slim`) に標準で入っている npm と coreutils に加え、 apt で足した `ca-certificates` / `findutils` / `tree` が agent の道具箱になる。

**許可** (image に存在する):

- ディレクトリ操作: `mkdir`, `rmdir`
- 移動: `mv`
- ファイル作成: `touch` (`.done` と `.FYI.md` の作成用)
- 探索: `ls`, `find`, `tree`
- メタデータ: `stat`, `readlink`, `realpath`
- パス操作: `basename`, `dirname`, `wc`
- テキスト I/O: `cat`, `grep`, `sed` (`.FYI.md` の読み書き・検索)
- 時間制御: `timeout` (entrypoint がエージェントを包むのにも使う)
- シェル組込み: `cd`, `pwd`, `echo`, `test` / `[ ]`

**不許可** (Dockerfile の最終層で `rm` する):

- `rm` — 削除不可 (削除は `rmdir` のみで、空ディレクトリ限定)
- `cp` — symlink 複製を防ぐ
- `ln` — 任意 symlink 生成を防ぐ
- `chmod`, `chown`, `dd`, `truncate` — 不要かつ危険

最後の `rm` で `rm` 自身を消すのは意図的で、削除を **単一の `RUN` 命令**にまとめることで「 `rm` が消えた後にもう一度 `rm` を呼ぶ」という順序の罠を避けている。

`ls` / `find` / `stat` は既定の挙動 (symlink 自身を見る) のままで構わない。 agent にとっては target の文字列そのものがプロビナンス情報になるので、 symlink を follow させるよりそのまま見せる方が有益。

agent ごとの小さなヘルパーや provider 固有の環境変数は image に焼き込まず、 skeleton の agent home 配下に置く。必要なら `.rehearse/agent/init.sh` で `PATH` を調整し、 `~/bin` などを agent CLI 起動前に使える状態にする。

## Agent instructions

agent への恒久的な作業指示は、session 作成時に agent work dir の `work/AGENTS.md` としてコピーされる。Claude Code 互換のため、同じ場所に `CLAUDE.md -> AGENTS.md` の相対 symlink も作る。Codex / Claude Code には instructions の内容を prompt として渡さず、各 agent の native な discovery に任せる。

既定では bundled `instructions/default.md` を使う。用途ごとに差し替える場合は `$REHEARSE_ROOT` 配下に instructions file を置き、profile の `agent_instructions` で指定する:

```json
{
  "agent_instructions": "instructions/music.md"
}
```

`rehearse run -m ...` で渡すのは、その実行に限ったカスタム指示だけ。 `-m` を省略した場合、entrypoint は初回なら `Start working.`、継続なら `Resume working.` という短い既定指示だけを agent CLI に渡す。

## Agent home skeleton

agent home の初期状態は `$REHEARSE_ROOT/skeletons/<name>/` に置ける。 `rehearse create` は profile の `skeleton` で指定された skeleton を `sessions/<id>/home/agent/` にコピーし、その後 agent UID/GID に chown する。 symlink は symlink のままコピーされる。

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

`.rehearse/agent/init.sh` は agent startup 用の escape hatch で、 provider API key などの secret を含み得る。 `auth.json` と同様に password と同じ扱いにすること。 session の git snapshot は `work/` だけを追跡するため `home/agent/.codex/auth.json` や `home/agent/.rehearse/agent/init.sh` は記録されない。 session directory は `delete` まで残るので copied secret も残り、 `delete` で削除される。
