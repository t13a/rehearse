# セッションのライフサイクル

## 状態遷移

```
    [new]
      ↓ (harness 起動, workspace + c/d 構築)
   [running]
      ↓ (container 終了)
  ┌───┴────┬──────────┬────────┐
  ↓        ↓          ↓        ↓
[done]  [abort]  [timeout]  [crash]
  │        │          │        │
  └────────┴──────────┴────────┘
            ↓ (人間レビュー)
     ┌──────┼───────┐
     ↓      ↓       ↓
 [committed] [discarded] [resume → running]
     │          │
     └──────────┘
          ↓ (任意のタイミングで物理削除)
       [purged]
```

## 状態の定義

| 状態 | 説明 |
|---|---|
| `running` | コンテナが稼働中 |
| `done` | `d/.done` が存在する状態で container 正常終了 |
| `abort` | agent が自主的に終了 (`.done` なし) |
| `timeout` | 外部 watcher が `docker kill` した |
| `crash` | container が異常終了した (OOM 等) |
| `committed` | `commit` が完了し、実ファイルが A→B に移動済み |
| `discarded` | `discard` が実行された (実ファイルは無傷、workspace は audit として残る) |
| `purged` | workspace が物理削除された |

`done` と `abort` の区別は重要。`done` は「 agent が自分で完了と判断した」正常系。 `abort` `timeout` `crash` は何らかの異常で、レビュー時に扱いを変える可能性がある。

## コマンド

ハーネスが提供する CLI:

### `rehearse new <A> <B> [--scope <subpath>]`

- 新しい workspace を作成
- `data/` 配下に `a/`, `b/` symlink、`c/`, `d/` を構築
- `meta.json` を書き出し
- `.gitignore` を書き、 `data/` の初期状態を git にスナップショット (レビュー用、詳細は [architecture.md](architecture.md) の「セッション開始時フック」節)
- `--scope` 指定時は `d/` を B のサブディレクトリだけのミラーにする (スコープ制御)

### `rehearse run <session>`

- Docker コンテナを起動し、 agent を実行
- container 終了まで block (または `--detach`)
- 終了後、 `meta.json` の status を更新
- transcript を workspace にコピー

### `rehearse status <session>`

- session の現状と `d/` の tree を表示
- `.FYI.md` を隣接表示
- transcript の要約

### `rehearse commit <session>`

- `d/` の symlink を辿って実ファイルを A→B に rename
- 冪等な実装 (中断しても再実行で残りを処理)
- `meta.json` の status を `committed` に更新
- 詳細: [commit.md](commit.md)

### `rehearse discard <session>`

- 何もしない (実ファイルは無傷)
- `meta.json` の status を `discarded` に更新
- workspace は残る (audit 記録として)

### `rehearse resume <session>`

- 既存の workspace で agent を再起動
- `c/` に残っている symlink = 未処理、 `d/` に動いた symlink = 既に配置決定
- timeout や abort からの継続、または追加指示を与えた後の再実行に使う

### `rehearse purge <session>`

- workspace を物理削除
- どの状態からでも実行可能 (`committed` / `discarded` / エラー終了後 等)
- 実ファイルへの影響なし

## 規約: `.done`

agent は全ての配置を完了したと判断した時点で `d/.done` (空ファイルでも可) を作成して終了する。

- **正常終了のシグナルに限定**: 異常系は経路が多様で信頼できない。正常系だけで確実に起きることを signal にする
- `.done` がない状態で container が終了していたら `abort` / `timeout` / `crash` のいずれか
- レビュー時、 `.done` の有無で色分けすると事故防止になる

## 規約: `.FYI.md`

agent は配置の判断理由や Web 検索で得た情報を `.FYI.md` として `d/` 内に残せる。

**配置パターン** (どちらでもよい):

```
d/music/
  foo/
    bar.flac                        # symlink
    bar.flac.FYI.md                 # 個別ファイル単位の補足
  baz/
    FYI.md                          # ディレクトリ単位の補足
    qux.flac                        # symlink
```

**性質**:

- `.FYI.md` は **実ファイル**であり symlink ではない
- commit 時に B には**移動しない**: workspace 内にそのまま残る (audit 記録)
- レビュー時の判断材料として読める
- 必須ではない: agent が必要と判断した場所にだけ書く

## 規約: transcript

Claude Code は会話ログを `~/.claude/projects/...` に出力する。ハーネスはセッション終了時にこれを workspace の `transcript.jsonl` にコピーする。

- レビュー時に「なぜその配置にしたか」を遡れる
- `.FYI.md` とは別次元の情報 (transcript は全行動の記録、 `.FYI.md` は agent 自身が選んだダイジェスト)
- 両方あると相互補完になる

## レビュー手順

`rehearse status` はセッションの現状と transcript の要約を示すが、 **配置計画そのもののレビューは git で行う**。 `rehearse new` の時点で `data/` の初期状態が git にスナップショットされているので、 agent が動かした分だけが差分として浮かび上がる。

通常の動線:

```bash
cd /opt/rehearse/sessions/<id>
git status                     # 変更された symlink / 追加された実ファイルの一覧
git diff                       # target (= プロビナンス) の変化を読む
cat data/d/**/FYI.md           # agent が残した補足を拾う (あれば)
less data/transcript.jsonl     # 判断根拠を遡りたいとき
```

- symlink の blob は target 文字列そのままなので、 `mv` だけの移動は rename 検出が自動で効く
- `.FYI.md` や `.done` も実ファイルとして自然に `git status` に出てくる
- tig / lazygit / gitui / VS Code など、好みのレビュー UI をそのまま使える

納得したら `rehearse commit`、そうでなければ `rehearse discard`。 git リポジトリは rehearse の動作に関与しないので、レビュアーが自由にブランチを切って試しても構わない。

## コミット後の workspace の姿

`commit` 実行後、workspace はこのような状態になる:

- `c/` の symlink は dead (target の実ファイルが B に移動したので壊れている)
- `d/` の symlink も dead (同上)
- ただし symlink **自体** (文字列) と `.FYI.md` は残る
- `readlink c/foo.flac` → `/opt/rehearse/sessions/<id>/a/foo.flac` (文字列としては読める)
- 「元は A のどこにあって、 agent が B のどこに置こうとしたか」の記録が完全に残る
- 後日の振り返り、ルール改善、学習データとして使える

物理コストは symlink 1 個あたり数十バイト。 10k ファイルでも 1MB 未満なので、古いセッションを残しておくコストは無視できる。
