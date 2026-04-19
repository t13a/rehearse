# Commit

## 基本方針

`commit` は `outbox/` の symlink ツリーを辿り、 symlink の target が `refs/a/` 配下 (= A 由来) のものだけ実ファイルを rename する。 `refs/b/` 配下 (= 既存 B への symlink) と `.FYI.md` は何もしない。

3 つの性質を満たす:

1. **冪等** — 中断されても同じコマンドを再実行するだけで残り分を処理できる
2. **同一 fs の atomicity に乗る** — 個別の `rename(2)` は atomic なので、中断状態は常に「一部移動済み・残り未移動」の形だけ
3. **衝突検出** — 予期しない状態 (A 側実ファイルが消え B 側にもない等) は即 abort

## なぜ session directory 起点の absolute path で比較するか

symlink の target は `session directory/data/refs/a/...` または `session directory/data/refs/b/...` の 2 系統しかないという不変条件を立てている (inbox/outbox 構築時にそう作る)。

target 文字列の prefix で分岐するので:

- 文字列マッチだけで判断でき fs を叩かない
- `/host/path/A/...` のような実パスに解決してから比較するより速い
- 将来 A の実パスが変わっても、 session directory 内の prefix は変わらないので commit ロジックに影響しない

## 冪等性の担保

中断後に再実行した場合:

| src の状態 | dst の状態 | 解釈 | アクション |
|---|---|---|---|
| exists | not exists | 未移動 | rename する |
| not exists | exists | 移動済み | スキップ (log: already-moved) |
| exists | exists | 衝突 | abort |
| not exists | not exists | 想定外 | abort |

このテーブルは commit の任意の中断点から再開可能であることを保証する。

## `.FYI.md` の扱い

- commit 中は **完全にスキップ** する
- session directory 内 (`outbox/` の中) にそのまま残る
- B のライブラリには混入しない (B のクリーンネスを維持)
- レビュー時・後日の振り返り時に session directory/outbox/ 内で参照

## rollback (commit 中) は必要ないか

個別 `rename(2)` が atomic なので、中断された場合の状態は常に「N 個移動済み・残り未移動」という完全に一貫した状態になる。 rollback は不要で、 resume すれば続きから進められる。

もしどうしても A 側に全て戻したい場合は:

- session directory/commit.log を逆順に辿って rename で戻す
- ただしこれは例外対応であり、通常フローには含めない

## 並列性

同一 B に対する commit は serialize する (`flock` で排他)。複数の session が同じ B を触る場合、意図しない順序で commit されると衝突検出が真の衝突なのか順序問題なのか区別できなくなるため。

現状は並列セッション非サポートの前提だが、 flock を最初から入れておけば将来の拡張にも耐える。

## 失敗時の診断

commit.log は構造化 (JSONL 推奨) で書く:

```jsonl
{"ts": "...", "op": "moved", "src": "/A/foo.flac", "dst": "/B/music/foo.flac"}
{"ts": "...", "op": "already-moved", "src": "/A/bar.flac", "dst": "/B/music/bar.flac"}
{"ts": "...", "op": "conflict", "src": "/A/baz.flac", "dst": "/B/music/baz.flac"}
```

abort 時は最後のエントリが原因。 resume や手動リカバリの際に参照する。


## B に対する排他制御

`commit` は実ファイルを B に対して `rename(2)` するので、同じ B に対する並行 commit は衝突する可能性がある。そこで `commit` 開始時に `${REHEARSE_ROOT}/locks/b-<hash>.lock` を `flock` で排他取得する (advisory なので rehearse プロセス同士のみ対象、外部プログラムや agent は無関係)。

`create` / `run` は B を read-only でしか触らないのでロックは取らない。自動 session id の採番は `mkdir(2)` の atomicity に任せて、 EEXIST なら +1 で retry する。名前付き session id は同じく `mkdir(2)` で衝突検出し、既存なら retry せず失敗する (flock 不要)。

## コミット後の作業ディレクトリの姿

`commit` 実行後、作業ディレクトリはこのような状態になる:

- `inbox/` の symlink は dead (target の実ファイルが B に移動したので壊れている)
- `outbox/` の symlink は B 由来のものは live、 A 由来のものは dead
- ただし symlink **自体** (文字列) と `.FYI.md` は残る
- `readlink inbox/foo.flac` → `$HOME/.local/share/rehearse/sessions/<id>/data/refs/a/foo.flac` (文字列としては読める)
- 「元は A のどこにあって、 agent が B のどこに置こうとしたか」の記録が完全に残る
- 後日の振り返り、ルール改善、学習データとして使える

物理コストは symlink 1 個あたり数十バイト。 10k ファイルでも 1MB 未満なので、古いセッションを残しておくコストは無視できる。
