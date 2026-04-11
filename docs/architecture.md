# アーキテクチャ

## workspace のレイアウト

1 セッション = 1 ワークスペースディレクトリ。セッション終了後も audit 記録として残す (物理削除は `purge` コマンドで明示的に実行)。

```
/opt/rehearse/sessions/<session-id>/
├── meta.json             # 起動時刻, A の実パス, B の実パス, scope, status
├── a -> /host/path/A     # A への symlink (read-only 解決)
├── b -> /host/path/B     # B への symlink (read-only 解決)
├── c/                    # A のミラー (agent の未処理プール)
├── d/                    # B のミラー + agent の配置計画
│   └── .done             # 正常終了時にエージェントが作る
├── transcript.jsonl      # Claude Code の会話ログ
├── agent_stdout.log      # エージェントの stdout
└── commit.log            # commit 時に追記
```

`<session-id>` は `2026-04-10T14-23-55_abc` のような timestamp + ランダム suffix。

## 4 つのディレクトリの役割

| ディレクトリ | 実体 | 意味 |
|---|---|---|
| `a/` | symlink → 実 A | 移動元 (read-only) |
| `b/` | symlink → 実 B | 移動先 (read-only だがコンテナ外では後の commit で rw として扱う) |
| `c/` | 実ディレクトリ | A の写し。 agent の「未処理」プール。各 entry は `a/` 配下への symlink |
| `d/` | 実ディレクトリ | B の写しから始まり、 agent が `c/` から symlink を `mv` して配置計画を組み立てる場所 |

## symlink のルール

**絶対パス**: C/D 内の symlink はすべて workspace 起点の絶対パスで作る。

例: `workspace/c/foo.flac` の target は `/opt/rehearse/sessions/<id>/a/foo.flac`

解決の連鎖:

1. `workspace/c/foo.flac` の target = `/opt/rehearse/sessions/<id>/a/foo.flac`
2. `/opt/rehearse/sessions/<id>/a` は symlink → `/host/path/A`
3. 最終的に `/host/path/A/foo.flac` にアクセスする

**相対パス禁止**: `../a/foo.flac` のような相対 symlink は `mv` で配置を動かしたときに target 解決が壊れる。絶対パスのみを許可し、harness 起動時に検証する。

## パーミッションモデル

agent の UID から見て:

```
workspace/          owner: harness, mode 755   → ls/cd 可、直下の add/remove/rename 不可
workspace/a         symlink                     → 親が書込不可なので動かせない
workspace/b         symlink                     → 同上
workspace/c/        owner: agent,   mode 755   → 中身は自由にいじれる
workspace/d/        owner: agent,   mode 755   → 中身は自由にいじれる
```

親ディレクトリの write 権限を落とすことで、 `a`/`b` の symlink 自体を `mv` で剥がされるのを防ぐ。 `c/` `d/` の内部では agent が自由に動ける。

実 A/実 B は Docker 側で read-only マウントされるため、 agent が symlink を follow して書き込みしようとしても EROFS で弾かれる。

## Docker マウント設計

**原則: ホストとコンテナで同じパスを使う**

symlink の target はただの文字列で、 解決時に絶対パスとして評価される。ホストとコンテナでパスが食い違うと、片側から symlink が壊れて見える。したがってコンテナ内のマウント先はホストのパスをそのまま使う。

```bash
docker run --rm \
  -v /opt/rehearse/sessions/<id>:/opt/rehearse/sessions/<id>:rw \
  -v /host/path/A:/host/path/A:ro \
  -v /host/path/B:/host/path/B:ro \
  --network=... \
  --user <agent-uid>:<agent-gid> \
  rehearse-agent:latest
```

コンテナ内の view:

```
/opt/rehearse/sessions/<id>/
├── a -> /host/path/A        (ro マウント経由で読める)
├── b -> /host/path/B        (ro マウント経由で読める)
├── c/
└── d/
```

ホスト側の commit スクリプトも同じパスを使って symlink を辿れる。

## ツールボックス (コンテナ内)

Docker image には **許可コマンドだけ**をインストールする。不要なコマンドは PATH 上から消えるので呼びようがない。

**許可**:

- ディレクトリ操作: `mkdir`, `rmdir`
- 移動: `mv` (wrapper で `-n` 強制、上書き禁止)
- 探索: `ls`, `find` (`-L` 既定化), `tree`
- メタデータ: `stat` (`-L` 既定化), `readlink`, `realpath`
- パス操作: `basename`, `dirname`, `wc`
- シェル組込み: `cd`, `pwd`, `echo`, `test` / `[ ]`

**不許可** (image に入れない):

- `rm` — 削除不可 (削除は `rmdir` のみで、空ディレクトリ限定)
- `cp` — symlink 複製を防ぐ
- `ln` — 任意 symlink 生成を防ぐ
- `touch`, `chmod`, `chown`, `dd`, `truncate` — 不要かつ危険

**ラッパー規約**:

- `mv` → 実際には `mv -n` (既存上書きを黙って行うのを防ぐ)
- `stat` → 実際には `stat -L` (symlink 自身でなく target を見る)
- `find` は `-L` フラグを最初に付ける癖を system prompt でも明記

ファイル内容アクセス (`cat`, `head`, `grep`, `file` 等) は今回の用途では不要。必要が生じたら都度追加する。

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
5. 他セッションが同じ B を使っていないか (`flock` で排他)
