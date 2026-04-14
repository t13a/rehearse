# commit アルゴリズム

## 基本方針

`commit` は `outbox/` の symlink ツリーを辿り、 symlink の target が `refs/a/` 配下 (= A 由来) のものだけ実ファイルを rename する。 `refs/b/` 配下 (= 既存 B への symlink) と `.FYI.md` は何もしない。

3 つの性質を満たす:

1. **冪等** — 中断されても同じコマンドを再実行するだけで残り分を処理できる
2. **同一 fs の atomicity に乗る** — 個別の `rename(2)` は atomic なので、中断状態は常に「一部移動済み・残り未移動」の形だけ
3. **衝突検出** — 予期しない状態 (A 側実ファイルが消え B 側にもない等) は即 abort

## 擬似コード

```python
def commit(workspace: Path, A: Path, B: Path, log: LogFile):
    data = workspace / "data"
    outbox = data / "outbox"
    a_prefix = str(data / "refs" / "a") + "/"
    b_prefix = str(data / "refs" / "b") + "/"

    for entry in walk(outbox):
        if entry.is_symlink():
            handle_symlink(entry, outbox, A, B, a_prefix, b_prefix, log)
        elif entry.is_file():
            # .FYI.md のような実ファイル → B には移動しない
            continue

def handle_symlink(link: Path, outbox: Path, A: Path, B: Path,
                   a_prefix: str, b_prefix: str, log: LogFile):
    target = os.readlink(link)            # 文字列としての target
    rel = link.relative_to(outbox)        # outbox/ からの相対パス
    dst = B / rel                          # 実 B 内の配置先

    if target.startswith(a_prefix):
        # A 由来 → 実ファイルを移動する必要がある
        src = resolve_target_to_real_A(target, a_prefix, A)

        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.rename(src, dst)            # 同一 fs なので atomic
            log.append("moved", src=src, dst=dst)

        elif not src.exists() and dst.exists():
            # 既に移動済み (resume 対応)
            log.append("already-moved", src=src, dst=dst)

        elif src.exists() and dst.exists():
            # 衝突: agent の計画と B の現状が不整合
            log.append("conflict", src=src, dst=dst)
            raise CommitAbort(f"both src and dst exist: {src} / {dst}")

        else:
            # src も dst もない = 予期しない状態
            log.append("missing", src=src, dst=dst)
            raise CommitAbort(f"neither src nor dst exists: {src} / {dst}")

    elif target.startswith(b_prefix):
        # 既存 B への symlink: 何もしない (agent が動かさなかった entry)
        pass

    else:
        # workspace 起点でないパス = 想定外
        log.append("unexpected-target", target=target)
        raise CommitAbort(f"unexpected symlink target: {target}")

def resolve_target_to_real_A(target: str, a_prefix: str, A: Path) -> Path:
    # target が "/opt/rehearse/sessions/<id>/data/refs/a/foo.flac" のとき
    # a_prefix を剥いで A/foo.flac にマップする
    suffix = target[len(a_prefix):]
    return A / suffix
```

## なぜ workspace 起点の absolute path で比較するか

symlink の target は `workspace/data/refs/a/...` または `workspace/data/refs/b/...` の 2 系統しかないという不変条件を立てている (inbox/outbox 構築時にそう作る)。

target 文字列の prefix で分岐するので:

- 文字列マッチだけで判断でき fs を叩かない
- `/host/path/A/...` のような実パスに解決してから比較するより速い
- 将来 A の実パスが変わっても、 workspace 内の prefix は変わらないので commit ロジックに影響しない

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
- workspace 内 (`outbox/` の中) にそのまま残る
- B のライブラリには混入しない (B のクリーンネスを維持)
- レビュー時・後日の振り返り時に workspace/outbox/ 内で参照

## rollback (commit 中) は必要ないか

個別 `rename(2)` が atomic なので、中断された場合の状態は常に「N 個移動済み・残り未移動」という完全に一貫した状態になる。 rollback は不要で、 resume すれば続きから進められる。

もしどうしても A 側に全て戻したい場合は:

- workspace/commit.log を逆順に辿って rename で戻す
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
