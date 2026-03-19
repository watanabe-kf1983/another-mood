# Stage Runner

Watcher から起動される処理関数の実行を包む共通ランナー。
出力の原子性と順序性を保証する。

## 設計原則

- **結果整合**: 入力の一貫性は保証しない。最後の正しい run で収束する
- **Multi-Instance 許容**: 同一ステージの複数インスタンスが同時に走りうる
- **クロスプラットフォーム**: POSIX 固有の仕組み（flock 等）に依存しない

## フロー

```
StageRunner(inputDirs, outputDir, processFn)

1. startTime = now()
2. tmpDir = createTmpDir()
3. processFn(inputDirs, tmpDir)
4. lock({outputDir}.lock/)               ← mkdir ベースの atomic lock
5. existingTime = {outputDir}.version.json のタイムスタンプ
6. if startTime > existingTime:
     rename outputDir → outputDir.old
     rename tmpDir → outputDir
     rm outputDir.old
     {outputDir}.version.json に startTime を記録
   else:
     rm tmpDir                          ← 自分の結果は古い。捨てる
7. unlock({outputDir}.lock/)
```

## 各要素の役割

| 要素 | 解決する問題 |
|---|---|
| tmpDir に書いてから rename | 出力の混在防止（原子性） |
| startTime の比較 | 古い結果による上書き防止（順序性） |
| outputDir 丸ごと差し替え | 残骸ファイルの防止 |
| mkdir ベースの lock | read-compare-write の競合防止 |

## メタファイル

各出力ディレクトリの隣に配置する。
outputDir の中には置かない（ロック中に outputDir の中身を丸ごと差し替えるため）。

```
.reqs-builder/
  tmp/
    normalized/
      schema/                ← normalizedSchemaDir（丸ごと差し替え対象）
      schema.version.json
      schema.lock/
      contents/              ← normalizedContentsDir
      contents.version.json
      contents.lock/
      queries/               ← normalizedQueriesDir
      queries.version.json
      queries.lock/
    views/                   ← viewsDir
    views.version.json
    views.lock/
  output/                    ← outDir
  output.version.json
  output.lock/
```

```json
{
  "startTime": "2026-03-19T10:32:15.123Z",
  "stage": "normalizer"
}
```

## ロック方式

mkdir ベースの cross-platform atomic lock を使用する:

- mkdir は POSIX / Windows 両方で原子的に動作する
- stale lock 対策（PID 記録 + 生存確認、またはタイムアウト）はライブラリに委ねる
- 実装例: Python `filelock`

## InputStrategy（将来の拡張点）

現時点では processFn に物理パス（inputDirs）を直接渡す（direct 方式）。
パフォーマンス問題が判明した場合に以下へ差し替え可能な境界として残す:

- tmpDir コピー方式
- インメモリ FS 方式

## 背景: 入力一貫性を保証しない理由

debounce 後に処理が起動されるため、読み込み中に入力が変わる確率は極めて低い。
万一不整合が生じても、次の Watcher トリガーで正しい結果に収束する。
content hash による前後比較、generation チェック等の検証は、
実測でボトルネックが確認されてから導入する。

## 背景: タイムスタンプを採用した理由

バージョン番号（単調増加カウンタ）のほうが理論的には優れるが、
マルチプロセス間でカウンタを共有する仕組みが追加で必要になる。
同一マシン上のシステムクロックは実用上十分信頼でき、
タイムスタンプであれば共有状態なしにプロセス間で比較できる。
