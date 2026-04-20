# Mirroring

## 作業ディレクトリの役割

| ディレクトリ | 実体 | 意味 |
|---|---|---|
| `work/` | 実ディレクトリ | agent work dir。agent が見る作業ディレクトリ |
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
work/              owner: guard, mode 755      → コンテナの mount 先、直下の add/remove 不可
work/refs/         owner: guard, mode 755      → 参照用、書込不可
work/refs/a        symlink                      → 親が書込不可なので動かせない
work/refs/b        symlink                      → 同上
work/inbox/        owner: agent, mode 777      → 書込可、 agent が自分の symlink を `mv` する出発点
work/inbox/*       owner: agent                 → setup 時に chown コンテナでハンドオフ済み
work/outbox/       owner: guard, mode 1777     → sticky + 書込可、中身の既存エントリは動かせない
work/outbox/**/    owner: guard, mode 1777     → B-mirror の各サブディレクトリ (sticky)
work/outbox/**/*   owner: guard                → B-mirror の symlink 本体 (guard 所有)
```

agent work dir (`work/`) と `refs/` の write 権限を落とすことで、 `refs/a`/`refs/b` の symlink 自体を `mv` で剥がされるのを防ぐ。 session directory ルート (`meta.json`, `commit.log`, `.git/`) は container に一切マウントされないので、 agent からは観測不能。

**sticky bit + 所有権ハンドオフによる B-mirror の保護**: `outbox/` とその配下の全サブディレクトリには sticky bit を立てておく (`chmod 1777`)。 `outbox/` の初期内容 (B のミラー = サブディレクトリ + symlink) は guard 所有にする。 sticky bit は「エントリの所有者でない限り、 directory 内の既存エントリを unlink / rename できない」という POSIX の挙動を使って、 **agent に B-mirror の構造と symlink を物理的に触らせない**ことを実現する:

- 既存 B-mirror symlink を `mv` しようとすると EPERM (所有者は guard)
- B-mirror サブディレクトリを `mv` / `rmdir` しようとすると EPERM (同上)
- 一方で write 権限は開けてあるので、 agent は B-mirror 内に**新しい**エントリを追加できる (sticky は既存エントリにしか効かない)
- agent が作った subdir や移動してきた symlink は agent 所有・非 sticky なので、自分の配下では自由に reorg できる

**所有権ハンドオフ**: sticky bit enforcement は「所有者である限り動かせる」という対称側も持つ。 agent が `inbox/` から `outbox/` に運んできた symlink を後から**別の場所に動かし直す** (do-over) ためには、 agent 自身がその symlink の owner である必要がある。そこで `create` の末尾で `scripts/docker-helper.sh` 経由の短命な root コンテナを叩き、まず `work/` 全体を `guard_uid:guard_gid` に寄せてから、 `inbox/` と `home/agent/` を `agent_uid:agent_gid` にハンドオフする。 `rename(2)` は owner を保存するので、 `mv inbox/foo.flac outbox/music/...` としても owner は agent のままで、あとから `mv` で別の場所に動かし直せる。

この結果、 agent が「動かしていいのは自分で持ち込んだ symlink だけ」という不変条件が機構的に保証され、 agent 側に target prefix を見て判断させる必要がなくなる。また、配置の do-over も何度でもできる。

guard UID と agent UID は**別にする**必要がある。 sticky bit は「 root か owner なら動かせる」という仕様なので、 agent コンテナを guard と同じ UID で動かしてしまうと B-mirror の保護が効かない。既定では agent = 現在の host user、 guard = 65534 として分離する。これにより agent が作った配置物は host 側で手動編集しやすく、B mirror の初期構造だけを guard で守れる。

実 A/実 B は Docker 側で read-only マウントされるため、 agent が symlink を follow して書き込みしようとしても EROFS で弾かれる。
