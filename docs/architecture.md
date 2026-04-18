# アーキテクチャ

## ディレクトリレイアウト

1 セッション = 1 ディレクトリ。セッション終了後も audit 記録として残す (物理削除は `purge` コマンドで明示的に実行)。

```
~/.local/share/rehearse/sessions/<session-id>/
├── .git/                    # レビュー用スナップショット (harness 所有、 agent 視界外)
├── .gitignore               # data/ 以外を除外
├── meta.json                # 起動時刻, A の実パス, B の実パス, scope, status
├── commit.log               # commit 時に追記
└── data/                    # agent work dir。コンテナにマウントされる唯一のサブツリー
    ├── refs/
    │   ├── a -> /host/path/A    # A への symlink (read-only 参照)
    │   └── b -> /host/path/B    # B への symlink (read-only 参照)
    ├── inbox/               # A のミラー (agent の未処理プール)
    └── outbox/              # B のミラー + agent の配置計画
        └── .done            # 正常終了時にエージェントが作る
```

`<session-id>` は既定では UNIX 秒 (`1744296235` のような 10 桁文字列)。ソート可能で短いので、 symlink target に繰り返し現れても agent の入力トークンやレビュー負荷を圧迫しない。秒内衝突は `mkdir(2)` の atomicity で検知して +1 retry する。`rehearse create -s SID` を使うと任意の名前付き session id を指定できる。使える文字は profile 名と同じ英数字、 `_`、`-`、`.` で、既存 session との衝突時は上書きせず失敗する。

以降、`sessions/<id>/data/` を **agent work dir**、`sessions/<id>/home/agent/` を **agent home** と呼ぶ。実ディレクトリ名は短く保ち、役割名で意味を補う。

## ディレクトリの役割

| ディレクトリ | 実体 | 意味 |
|---|---|---|
| `data/` | 実ディレクトリ | agent work dir。agent が見る作業ディレクトリ |
| `refs/a/` | symlink → 実 A | 移動元 (read-only) |
| `refs/b/` | symlink → 実 B | 移動先 (read-only だがコンテナ外では後の commit で rw として扱う) |
| `inbox/` | 実ディレクトリ | A の写し。 agent の「未処理」プール。各 entry は `refs/a/` 配下への symlink |
| `outbox/` | 実ディレクトリ | B の写しから始まり、 agent が `inbox/` から symlink を `mv` して配置計画を組み立てる場所 |

## symlink のルール

**絶対パス**: inbox/outbox 内の symlink はすべて session directory 起点の絶対パスで作る。

例: `/path/to/inbox/foo.flac` の target は `/path/to/refs/a/foo.flac`

解決の連鎖:

1. `/path/to/inbox/foo.flac` の target = `/path/to/refs/a/foo.flac`
2. `/path/to/refs/a` は symlink → `/host/path/A`
3. 最終的に `/host/path/A/foo.flac` にアクセスする

**相対パス禁止**: `../a/foo.flac` のような相対 symlink は `mv` で配置を動かしたときに target 解決が壊れる。絶対パスのみを許可し、harness 起動時に検証する。

## パーミッションモデル

agent の UID から見て:

```
data/              owner: guard, mode 755      → コンテナの mount 先、直下の add/remove 不可
data/refs/         owner: guard, mode 755      → 参照用、書込不可
data/refs/a        symlink                      → 親が書込不可なので動かせない
data/refs/b        symlink                      → 同上
data/inbox/        owner: agent, mode 777      → 書込可、 agent が自分の symlink を `mv` する出発点
data/inbox/*       owner: agent                 → setup 時に chown コンテナでハンドオフ済み
data/outbox/       owner: guard, mode 1777     → sticky + 書込可、中身の既存エントリは動かせない
data/outbox/**/    owner: guard, mode 1777     → B-mirror の各サブディレクトリ (sticky)
data/outbox/**/*   owner: guard                → B-mirror の symlink 本体 (guard 所有)
```

agent work dir (`data/`) と `refs/` の write 権限を落とすことで、 `refs/a`/`refs/b` の symlink 自体を `mv` で剥がされるのを防ぐ。 session directory ルート (`meta.json`, `commit.log`, `.git/`) は container に一切マウントされないので、 agent からは観測不能。

**sticky bit + 所有権ハンドオフによる B-mirror の保護**: `outbox/` とその配下の全サブディレクトリには sticky bit を立てておく (`chmod 1777`)。 `outbox/` の初期内容 (B のミラー = サブディレクトリ + symlink) は guard 所有にする。 sticky bit は「エントリの所有者でない限り、 directory 内の既存エントリを unlink / rename できない」という POSIX の挙動を使って、 **agent に B-mirror の構造と symlink を物理的に触らせない**ことを実現する:

- 既存 B-mirror symlink を `mv` しようとすると EPERM (所有者は guard)
- B-mirror サブディレクトリを `mv` / `rmdir` しようとすると EPERM (同上)
- 一方で write 権限は開けてあるので、 agent は B-mirror 内に**新しい**エントリを追加できる (sticky は既存エントリにしか効かない)
- agent が作った subdir や移動してきた symlink は agent 所有・非 sticky なので、自分の配下では自由に reorg できる

**所有権ハンドオフ**: sticky bit enforcement は「所有者である限り動かせる」という対称側も持つ。 agent が `inbox/` から `outbox/` に運んできた symlink を後から**別の場所に動かし直す** (do-over) ためには、 agent 自身がその symlink の owner である必要がある。そこで `create` の末尾で `scripts/docker-helper.sh` 経由の短命な root コンテナを叩き、まず `data/` 全体を `guard_uid:guard_gid` に寄せてから、 `inbox/` と `home/agent/` を `agent_uid:agent_gid` にハンドオフする。 `rename(2)` は owner を保存するので、 `mv inbox/foo.flac outbox/music/...` としても owner は agent のままで、あとから `mv` で別の場所に動かし直せる。

この結果、 agent が「動かしていいのは自分で持ち込んだ symlink だけ」という不変条件が機構的に保証され、 agent 側に target prefix を見て判断させる必要がなくなる。また、配置の do-over も何度でもできる。

guard UID と agent UID は**別にする**必要がある。 sticky bit は「 root か owner なら動かせる」という仕様なので、 agent コンテナを guard と同じ UID で動かしてしまうと B-mirror の保護が効かない。既定では agent = 現在の host user、 guard = 65534 として分離する。これにより agent が作った配置物は host 側で手動編集しやすく、B mirror の初期構造だけを guard で守れる。

実 A/実 B は Docker 側で read-only マウントされるため、 agent が symlink を follow して書き込みしようとしても EROFS で弾かれる。

## Docker マウント設計

**原則: ホストとコンテナで同じパスを使う**

symlink の target はただの文字列で、 解決時に絶対パスとして評価される。ホストとコンテナでパスが食い違うと、片側から symlink が壊れて見える。したがってコンテナ内のマウント先はホストのパスをそのまま使う。

マウントするのは **agent work dir (`data/`) のみ**。 session directory ルート直下の `.git/` や `meta.json` は container から見えないので、 agent が git の存在を観測することも、 harness のメタに触れることもできない。

```bash
docker run --rm \
  -v /opt/rehearse/sessions/<id>/data:/opt/rehearse/sessions/<id>/data:rw \
  -v /host/path/A:/host/path/A:ro \
  -v /host/path/B:/host/path/B:ro \
  --network=... \
  --user <agent-uid>:<agent-gid> \
  rehearse-agent-codex:latest
```

コンテナ内の view:

```
/opt/rehearse/sessions/<id>/
└── data/                    (sessions/<id>/data のみがマウントされる)
    ├── refs/
    │   ├── a -> /host/path/A    (ro マウント経由で読める)
    │   └── b -> /host/path/B    (ro マウント経由で読める)
    ├── inbox/
    └── outbox/
```

ホスト側の commit スクリプトも同じパスを使って symlink を辿れる。

### agent home: `sessions/<id>/home/agent` ↔ `/home/agent`

Codex CLI や Claude Code は agent home 配下に認証情報、設定、会話履歴を置く。これがコンテナ揮発領域にあると `--rm` で消えてしまうので、 agent の HOME を **session directory 内に永続化**する:

- `rehearse create` がセッションごとに `sessions/<id>/home/agent/` を掘り、 `inbox/` と一緒に agent UID へ chown ハンドオフする
- profile の `skeleton` で指定された `$REHEARSE_ROOT/skeletons/<name>/` を `sessions/<id>/home/agent/` にコピーする。未指定時は `default`。 `skeletons/default/` は空ディレクトリとして自動作成される
- runner script はこれを `/home/agent` に rw で bind mount し、 `HOME=/home/agent` を `-e` で渡す
- FHS に沿った `/home/agent` を選んだのは、一般的な CLI agent が前提とする「ホームディレクトリらしい場所」と整合させるため
- ホスト側のパスが `sessions/<id>/home/agent` なのは session directory レイアウトの対称性を取るため

コピーは symlink を symlink のまま保つ。 skeleton は雛形で、 agent home は独立したコピーなので、 agent が `.codex/auth.json` などを更新しても skeleton 側には書き戻さない。 session directory は `purge` まで残るため copied secret も残る。 `purge` で session directory を消すと agent home も一緒に消える。短期セッションでは履歴を後から振り返れるし、長期では `purge` 一発で掃除できる。

セッション開始時の git snapshot は `data/` だけを追跡するので、 `home/agent/.codex/auth.json` のような agent home 配下のファイルは session git repo に入らない。

## agent runner: harness と agent の境界

`docker run` の組み立ては **bash スクリプト (`scripts/docker-runner.sh`) に外出し**してある。 Python (`run.run_agent`) はもはや agent コンテナの docker コマンドを知らず、 runner を `subprocess.run` で起動して exit code を受け取るだけの薄い wrapper になっている。

同じ方針で、 root 権限が必要な `chown` / `cleanup` は `scripts/docker-helper.sh` に外出ししている。 Python は helper image、広めに mount する親ディレクトリ、実行したいコマンドだけを渡す。Docker 以外へ寄せる場合は runner と helper の 2 箇所が runtime 境界になる。

理由は二つ:

1. **テスタビリティ**: 本物の agent image と API key / auth cache を要求すると lifecycle テストが回せない。 profile の `agent_runner` を `tests/fake-runner.sh` に差し替えると、 busybox だけで Step 2 相当のテストが動く
2. **agent の交換可能性**: 将来 Codex CLI / Claude Code を OpenCode やローカル LLM ベースの agent に差し替えるとき、 Python 側を一切いじらず、 runner script を新しい agent 用に書き直すだけで済む

### Python ↔ Bash の契約

harness は以下の環境変数を runner にエクスポートする:

| 変数 | 意味 |
|---|---|
| `REHEARSE_SESSION_DIR` | session directory (host path) |
| `REHEARSE_AGENT_WORK_DIR` | agent work dir (`data/`) の host path |
| `REHEARSE_AGENT_HOME` | agent home (`home/agent/`) の host path (= container 内 `/home/agent` の bind 元) |
| `REHEARSE_SESSION_RUN_LOCK` | run 中だけ runner が `flock` で保持する session lock |
| `REHEARSE_SESSION_A` | A の host path (RO mount に使う) |
| `REHEARSE_SESSION_B` | B の host path (RO mount に使う) |
| `REHEARSE_AGENT_IMAGE` | 使う image |
| `REHEARSE_AGENT_UID` / `REHEARSE_AGENT_GID` | container user |
| `REHEARSE_AGENT_TIMEOUT` | container 内で `timeout` が agent CLI に与える秒数 |
| `REHEARSE_RUNNER_MODE` | `run` または `debug` |
| `REHEARSE_DEBUG_ENTRYPOINT` | debug mode で Docker entrypoint にする command |

runner は上記だけを使って `docker run` を組み立て、 container の exit code を自分の exit code としてそのまま返す。 harness はその数字だけを観察する。`debug` は同じ runner 契約で agent image を起動し、Docker の entrypoint だけを差し替える。これにより `/bin/bash` で agent home を確認したり、`/opt/rehearse/entrypoint.sh` を手動起動して通常 run と同じ経路を再現できる。

`running` は Docker など特定の runtime ではなく、 `REHEARSE_SESSION_RUN_LOCK` の `flock` から導出する。 runner が lock を握っている間だけ `status` / `commit` / `purge` は session を実行中として扱う。プロセス終了時には OS が lock を解放するため、 `Ctrl+C` や runner crash の後に stale な `running` が残らない。

これらの `REHEARSE_AGENT_*` は harness と runner の内部契約であり、ユーザー向け設定ではない。ユーザーは `$REHEARSE_ROOT/profiles/<name>.json` に `agent` / `agent_image` / `agent_uid` / `guard_uid` / `agent_timeout` などを書き、 `rehearse create -p <name> ...` で session に転記する。 guard UID/GID は create 時の ownership setup にだけ使い、 runner には渡さない。

provider API key のような agent process 用の環境変数は runner から pass-through しない。 skeleton に `.rehearse/agent/init.sh` を置くと、 entrypoint が agent CLI 起動前に source する。これにより `.codex/config.toml` や Claude Code の agent home 配下設定と、 `OPENROUTER_API_KEY` のような provider 固有設定を同じ skeleton に閉じ込められる。`init.sh` は通常の shell script なので、agent process に渡したい値は `export` する。

恒久的な agent instructions は container image には焼き込まない。 `rehearse create` が profile の `agent_instructions` を `data/AGENTS.md` にコピーし、Claude Code 互換の `data/CLAUDE.md -> AGENTS.md` も作る。 entrypoint が agent CLI に渡す prompt は、 `run -m` のカスタム指示か、初回/継続を示す短い既定指示だけにする。

### timeout の扱い

runner が組み立てる image の entrypoint は `timeout --kill-after=10 ${REHEARSE_AGENT_TIMEOUT} <agent-cli> ...` で agent CLI を包む。

- 上限秒数経過で SIGTERM、 10 秒待っても落ちなければ SIGKILL
- `timeout` の終了コードは SIGTERM 経路で 124、 SIGKILL 経路で 137
- harness の `cmd_run` は exit code 124/137 をまとめて `exit_reason="timeout"` として記録する

## ツールボックス (コンテナ内)

Codex image (`docker/codex/Dockerfile`) と Claude Code image (`docker/claude/Dockerfile`) は `node:20-slim` をベースにしている。どちらも npm パッケージとして CLI を入れ、 base image に標準で入っている coreutils と、 apt で足した `findutils` / `tree` で agent の道具箱になる。Codex image には HTTPS/WSS 接続用の `ca-certificates` も入れる。Codex 自体の sandbox は `danger-full-access` にして、Docker の bind mount と agent UID を containment boundary とする。

**許可** (image に存在する):

- ディレクトリ操作: `mkdir`, `rmdir`
- 移動: `mv`
- ファイル作成: `touch` (`.done` と `.FYI.md` の作成用)
- 探索: `ls`, `find`, `tree`
- メタデータ: `stat`, `readlink`, `realpath`
- パス操作: `basename`, `dirname`, `wc`
- テキスト I/O: `cat`, `grep`, `sed` (`.FYI.md` の読み書き・検索)
- 時間制御: `timeout` (entrypoint が `claude` を包むのに使う)
- シェル組込み: `cd`, `pwd`, `echo`, `test` / `[ ]`

**不許可** (Dockerfile の最終層で `rm` する):

- `rm` — 削除不可 (削除は `rmdir` のみで、空ディレクトリ限定)
- `cp` — symlink 複製を防ぐ
- `ln` — 任意 symlink 生成を防ぐ
- `chmod`, `chown`, `dd`, `truncate` — 不要かつ危険

最後の `rm` で `rm` 自身を消すのは意図的で、削除を **単一の `RUN` 命令**にまとめることで「 `rm` が消えた後にもう一度 `rm` を呼ぶ」という順序の罠を避けている。

`ls` / `find` / `stat` は既定の挙動 (symlink 自身を見る) のままで構わない。 agent にとっては target の文字列そのものがプロビナンス情報になるので、 symlink を follow させるよりそのまま見せる方が有益。

agent ごとの小さなヘルパーや provider 固有の環境変数は image に焼き込まず、 skeleton の agent home 配下に置く。必要なら `.rehearse/agent/init.sh` で `PATH` を調整し、 `~/bin` などを agent CLI 起動前に使える状態にする。

## Isolation まわり

- **Docker container** を採用 (systemd-nspawn / bubblewrap も候補だが情報量と既存 tooling で Docker が有利)
- **network**: 必要に応じて有効 (Web 検索を MCP 経由でさせる場合)
- **timeout**: 外部 watcher が N 分後に `docker kill` する
- **リソース制限**: cgroup 経由で cheap に付けられる (必要に応じて)
- **user namespace**: エージェントの UID は host の unprivileged user にマップする

## 入力の事前検証

セッション開始時にハーネスが実行するチェック:

1. A と B が同一ファイルシステムか (commit 時の `rename(2)` atomicity のため)
2. A と B が symlink を含まないか (含む場合は中断)
3. A と B のファイルシステムが symlink をサポートするか
4. ディレクトリの作成権限

## B に対する排他制御

`commit` は実ファイルを B に対して `rename(2)` するので、同じ B に対する並行 commit は衝突する可能性がある。そこで `commit` 開始時に `${REHEARSE_ROOT}/locks/b-<hash>.lock` を `flock` で排他取得する (advisory なので rehearse プロセス同士のみ対象、外部プログラムや agent は無関係)。

`create` / `run` は B を read-only でしか触らないのでロックは取らない。自動 session id の採番は `mkdir(2)` の atomicity に任せて、 EEXIST なら +1 で retry する。名前付き session id は同じく `mkdir(2)` で衝突検出し、既存なら retry せず失敗する (flock 不要)。

## セッション開始時フック: git によるレビュー用スナップショット

`rehearse create` は session directory 構築の最後に、 `sessions/<id>/` を git リポジトリ化して `data/` の初期状態をコミットする。これはレビュー専用のスナップショットで、 rehearse 本体の動作には関与しない。

### 手順

```bash
cd /opt/rehearse/sessions/<id>
git init -q
cat > .gitignore <<'EOF'
/*
!/.gitignore
!/data
EOF
git add -A
git commit -q -m "session start"
```

`.gitignore` は root 直下を全部除外して `data/` だけを track する。 `meta.json` や `commit.log` は git に入らない。

### なぜ git か

commit 前のレビュー時、 `data/outbox/` は B の full mirror に agent の配置計画が混ざった状態になる。 B が大きいほど「どこが変わったか」を目視で探すのは非現実的。差分情報自体は `data/outbox/` の symlink target に全部埋まっているので、初期状態を git に保存しておけば、それを commodity な git ツールチェーンで抽出できる:

- `git status` — セッション中に動いた symlink / 追加された `.FYI.md` / `.done` の一覧
- `git diff` — symlink target の変化 (= プロビナンスの変化) が直接読める
- rename 検出が自動で効く — symlink の blob 中身は target 文字列なので、 `mv` しただけなら blob が完全一致し rename として認識される
- tig / lazygit / gitui / VS Code など既存のレビュー UI がそのまま使える

### 責務分離

- **harness**: `rehearse create` の末尾で初回スナップショットを取って以降、 git を一切触らない
- **agent**: `.git/` は mount の外で不可視、道具箱に `git` もない。存在すら知らない
- **reviewer**: 必要に応じて `git status` / `git diff` を使う。任意で追加 commit やブランチ操作をしてもよい

セッション中〜後に git の状態を気にするアクターは reviewer だけ。 rehearse の用語空間からは git は脇にはみ出しており、「commit」という単語はあくまで `rehearse commit` の意味で使う。
