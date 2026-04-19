# Review

## レビュー手順

**配置計画そのもののレビューは git で行う**。 `rehearse create` の時点で `data/` の初期状態が git にスナップショットされているので、 agent が動かした分だけが差分として浮かび上がる。

通常の動線:

```bash
cd ~/.local/share/rehearse/sessions/<id>
git status                     # 変更された symlink / 追加された実ファイルの一覧
git diff                       # target (= プロビナンス) の変化を読む
cat data/outbox/**/FYI.md           # agent が残した補足を拾う (あれば)
less data/transcript.jsonl     # 判断根拠を遡りたいとき
```

- symlink の blob は target 文字列そのままなので、 `mv` だけの移動は rename 検出が自動で効く
- `.FYI.md` や `.done` も実ファイルとして自然に `git status` に出てくる
- tig / lazygit / gitui / VS Code など、好みのレビュー UI をそのまま使える

納得したら `rehearse commit`、不要なら `rehearse purge`。 git リポジトリは rehearse の動作に関与しないので、レビュアーが自由にブランチを切って試しても構わない。

## セッション開始時フック: git によるレビュー用スナップショット

`rehearse create` は session directory 構築の最後に、 `sessions/<id>/` を git リポジトリ化して `data/` の初期状態をコミットする。これはレビュー専用のスナップショットで、 rehearse 本体の動作には関与しない。

### 手順

```bash
cd ~/.local/share/rehearse/sessions/<id>
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
