# AtomicDirWriter

出力ディレクトリの原子性と順序性を保証する共通ライター。
各パイプラインステージおよび Renderer が使用する。

## 設計原則

- **結果整合**: 入力の一貫性は保証しない。最後の正しい run で収束する
- **Multi-Instance 許容**: 同一ステージの複数インスタンスが同時に走りうる
- **クロスプラットフォーム**: Python `filelock` ライブラリで OS 差異を吸収

## フロー

```
AtomicDirWriter(outputDir, processFn)

1. startTime = now()
2. tmpDir = createTmpDir()
3. processFn(out_dir=tmpDir)
4. lock({outputDir}.lock)               ← filelock
5. existingTime = {outputDir}.version.json のタイムスタンプ
6. if startTime > existingTime:
     rm outputDir
     rename tmpDir → outputDir
     {outputDir}.version.json に startTime を記録
   else:
     rm tmpDir                          ← 自分の結果は古い。捨てる
7. unlock({outputDir}.lock)
```

processFn は `out_dir` をキーワード引数で受け取る（`DirWriterFn` プロトコル）。
入力データの参照は processFn 側の責務であり、AtomicDirWriter は関与しない。

## 各要素の役割

| 要素 | 解決する問題 |
|---|---|
| tmpDir に書いてから rename | 出力の混在防止（原子性） |
| startTime の比較 | 古い結果による上書き防止（順序性） |
| outputDir 丸ごと差し替え | 残骸ファイルの防止 |
| filelock による lock | read-compare-write の競合防止 |

## メタファイル

各出力ディレクトリの隣に配置する。
outputDir の中には置かない（ロック中に outputDir の中身を丸ごと差し替えるため）。

```
.reqs-builder/
  <projectDir>/                     ← CLI の第一位置パラメータに対応
    tmp/
      normalized/
        schema/              ← normalizedSchemaDir（丸ごと差し替え対象）
        schema.version.json
        schema.lock
        contents/            ← normalizedContentsDir
        contents.version.json
        contents.lock
        queries/             ← normalizedQueriesDir
        queries.version.json
        queries.lock
      views/                 ← viewsDir
      views.version.json
      views.lock
    output/                  ← outDir
    output.version.json
    output.lock
```

```json
{
  "startTime": "2026-03-19T10:32:15.123Z"
}
```

## ロック方式

Python `filelock` ライブラリを使用する:

- OS ごとに適切なロック方式を自動選択（POSIX: fcntl、Windows: msvcrt）
- stale lock 対策（プロセス終了時の自動解放）がライブラリに組み込み済み
- ロック取得は競合時にブロッキング（待ち続ける）

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

## 背景: rm + rename を採用した理由

旧設計では lock 内で `rename outputDir → old, rename tmpDir → outputDir, rm old` としていたが、
lock 内では他の writer は来ず、version.json は swap 完了後に書くため downstream の watcher も発火しない。
`rmtree(outputDir) → rename(tmpDir, outputDir)` で十分であり、old_dir の管理が不要になる。
