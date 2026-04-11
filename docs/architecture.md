# アーキテクチャ

## workspace のレイアウト

1 セッション = 1 ワークスペースディレクトリ。セッション終了後も audit 記録として残す (物理削除は `purge` コマンドで明示的に実行)。

```
/opt/rehearse/sessions/<session-id>/
├── .git/                    # レビュー用スナップショット (harness 所有、 agent 視界外)
├── .gitignore               # data/ 以外を除外
├── meta.json                # 起動時刻, A の実パス, B の実パス, scope, status
├── commit.log               # commit 時に追記
└── data/                    # コンテナにマウントされる唯一のサブツリー
    ├── a -> /host/path/A    # A への symlink (read-only 解決)
    ├── b -> /host/path/B    # B への symlink (read-only 解決)
    ├── c/                   # A のミラー (agent の未処理プール)
    ├── d/                   # B のミラー + agent の配置計画
    │   └── .done            # 正常終了時にエージェントが作る
    ├── transcript.jsonl     # Claude Code の会話ログ
    └── agent_stdout.log     # エージェントの stdout
```

`<session-id>` は UNIX 秒 (`1744296235` のような 10 桁文字列)。ソート可能で短いので、 symlink target に繰り返し現れても agent の入力トークンやレビュー負荷を圧迫しない。秒内衝突は `flock` で検知して再試行する。

## 4 つのディレクトリの役割

| ディレクトリ | 実体 | 意味 |
|---|---|---|
| `a/` | symlink → 実 A | 移動元 (read-only) |
| `b/` | symlink → 実 B | 移動先 (read-only だがコンテナ外では後の commit で rw として扱う) |
| `c/` | 実ディレクトリ | A の写し。 agent の「未処理」プール。各 entry は `a/` 配下への symlink |
| `d/` | 実ディレクトリ | B の写しから始まり、 agent が `c/` から symlink を `mv` して配置計画を組み立てる場所 |

## symlink のルール

**絶対パス**: C/D 内の symlink はすべて workspace 起点の絶対パスで作る。

例: `workspace/data/c/foo.flac` の target は `/opt/rehearse/sessions/<id>/data/a/foo.flac`

解決の連鎖:

1. `workspace/data/c/foo.flac` の target = `/opt/rehearse/sessions/<id>/data/a/foo.flac`
2. `/opt/rehearse/sessions/<id>/data/a` は symlink → `/host/path/A`
3. 最終的に `/host/path/A/foo.flac` にアクセスする

**相対パス禁止**: `../a/foo.flac` のような相対 symlink は `mv` で配置を動かしたときに target 解決が壊れる。絶対パスのみを許可し、harness 起動時に検証する。

## パーミッションモデル

agent の UID から見て:

```
workspace/               owner: harness, mode 755    → host 側メタの置き場、 container 非表示
workspace/data/          owner: harness, mode 755    → コンテナの mount 先、直下の add/remove 不可
workspace/data/a         symlink                      → 親が書込不可なので動かせない
workspace/data/b         symlink                      → 同上
workspace/data/c/        owner: agent,   mode 755    → 中身は全部 agent のもの、自由にいじれる
workspace/data/d/        owner: harness, mode 1777   → sticky + 書込可、中身の既存エントリは動かせない
workspace/data/d/**/     owner: harness, mode 1777   → B-mirror の各サブディレクトリ (sticky)
workspace/data/d/**/*    owner: harness              → B-mirror の symlink 本体 (harness 所有)
```

`data/` の write 権限を落とすことで、 `a`/`b` の symlink 自体を `mv` で剥がされるのを防ぐ。 workspace ルート (`meta.json`, `commit.log`, `.git/`) は container に一切マウントされないので、 agent からは観測不能。

**sticky bit による B-mirror の保護**: `d/` とその配下の全サブディレクトリには sticky bit を立てておく (`chmod 1777`)。 `d/` の初期内容 (B のミラー = サブディレクトリ + symlink) は harness 所有で作る。 sticky bit は「エントリの所有者でない限り、 directory 内の既存エントリを unlink / rename できない」という POSIX の挙動を使って、 **agent に B-mirror の構造と symlink を物理的に触らせない**ことを実現する:

- 既存 B-mirror symlink を `mv` しようとすると EPERM (所有者は harness)
- B-mirror サブディレクトリを `mv` / `rmdir` しようとすると EPERM (同上)
- 一方で write 権限は開けてあるので、 agent は B-mirror 内に**新しい**エントリを追加できる (sticky は既存エントリにしか効かない)
- agent が作った subdir や移動してきた symlink は agent 所有・非 sticky なので、自分の配下では自由に reorg できる

この結果、 agent が「動かしていいのは自分で持ち込んだ symlink だけ」という不変条件が機構的に保証され、 agent 側に target prefix を見て判断させる必要がなくなる。

実 A/実 B は Docker 側で read-only マウントされるため、 agent が symlink を follow して書き込みしようとしても EROFS で弾かれる。

## Docker マウント設計

**原則: ホストとコンテナで同じパスを使う**

symlink の target はただの文字列で、 解決時に絶対パスとして評価される。ホストとコンテナでパスが食い違うと、片側から symlink が壊れて見える。したがってコンテナ内のマウント先はホストのパスをそのまま使う。

マウントするのは **`data/` サブツリーのみ**。 workspace ルート直下の `.git/` や `meta.json` は container から見えないので、 agent が git の存在を観測することも、 harness のメタに触れることもできない。

```bash
docker run --rm \
  -v /opt/rehearse/sessions/<id>/data:/opt/rehearse/sessions/<id>/data:rw \
  -v /host/path/A:/host/path/A:ro \
  -v /host/path/B:/host/path/B:ro \
  --network=... \
  --user <agent-uid>:<agent-gid> \
  rehearse-agent:latest
```

コンテナ内の view:

```
/opt/rehearse/sessions/<id>/
└── data/                    (workspace/data のみがマウントされる)
    ├── a -> /host/path/A    (ro マウント経由で読める)
    ├── b -> /host/path/B    (ro マウント経由で読める)
    ├── c/
    └── d/
```

ホスト側の commit スクリプトも同じパスを使って symlink を辿れる。

## ツールボックス (コンテナ内)

Docker image には **許可コマンドだけ**をインストールする。不要なコマンドは PATH 上から消えるので呼びようがない。

**許可**:

- ディレクトリ操作: `mkdir`, `rmdir`
- 移動: `mv` (wrapper で `-n` 強制、上書き禁止)
- ファイル作成: `touch` (`.done` と `.FYI.md` の作成用)
- 探索: `ls`, `find`, `tree`
- メタデータ: `stat`, `readlink`, `realpath`
- パス操作: `basename`, `dirname`, `wc`
- テキスト I/O: `cat`, `grep`, `sed` (`.FYI.md` の読み書き・検索)
- シェル組込み: `cd`, `pwd`, `echo`, `test` / `[ ]`

**不許可** (image に入れない):

- `rm` — 削除不可 (削除は `rmdir` のみで、空ディレクトリ限定)
- `cp` — symlink 複製を防ぐ
- `ln` — 任意 symlink 生成を防ぐ
- `chmod`, `chown`, `dd`, `truncate` — 不要かつ危険

**ラッパー規約**:

- `mv` → 実際には `mv -n` (既存上書きを黙って行うのを防ぐ)

`ls` / `find` / `stat` は既定の挙動 (symlink 自身を見る) のままで構わない。 agent にとっては target の文字列そのものがプロビナンス情報になるので、 symlink を follow させるよりそのまま見せる方が有益。

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
4. workspace 用ディレクトリの作成権限
5. 他セッションが同じ B を使っていないか (`flock` で排他 — advisory ロックなので rehearse プロセス同士の衝突検知のみ、外部プログラムや agent 自身は影響を受けない)

## セッション開始時フック: git によるレビュー用スナップショット

`rehearse new` は workspace 構築の最後に、 `<id>/` を git リポジトリ化して `data/` の初期状態をコミットする。これはレビュー専用のスナップショットで、 rehearse 本体の動作には関与しない。

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

commit 前のレビュー時、 `data/d/` は B の full mirror に agent の配置計画が混ざった状態になる。 B が大きいほど「どこが変わったか」を目視で探すのは非現実的。差分情報自体は `data/d/` の symlink target に全部埋まっているので、初期状態を git に保存しておけば、それを commodity な git ツールチェーンで抽出できる:

- `git status` — セッション中に動いた symlink / 追加された `.FYI.md` / `.done` の一覧
- `git diff` — symlink target の変化 (= プロビナンスの変化) が直接読める
- rename 検出が自動で効く — symlink の blob 中身は target 文字列なので、 `mv` しただけなら blob が完全一致し rename として認識される
- tig / lazygit / gitui / VS Code など既存のレビュー UI がそのまま使える

### 責務分離

- **harness**: `rehearse new` の末尾で初回スナップショットを取って以降、 git を一切触らない
- **agent**: `.git/` は mount の外で不可視、道具箱に `git` もない。存在すら知らない
- **reviewer**: 必要に応じて `git status` / `git diff` を使う。任意で追加 commit やブランチ操作をしてもよい

セッション中〜後に git の状態を気にするアクターは reviewer だけ。 rehearse の用語空間からは git は脇にはみ出しており、「commit」という単語はあくまで `rehearse commit` の意味で使う。
