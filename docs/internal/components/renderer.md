# Document Renderer

## 処理フロー

1. Hugo が `outDir` → `render.outDir` に変換

## Technical Stack

- Hugo (hugo-bin 経由): Go 製シングルバイナリ、高速ビルド、ライブリロード対応
- 将来: AsciiDoc レンダリング環境への差し替えも検討

## Hugo 統合

ユーザパイプラインとツール内部パイプライン（[pipeline.md](../pipeline/pipeline.md) 参照）の出力を
Hugo Module Mounts で 1つの Hugo server に統合できる。
別ポートで分離することも可能。どちらを採用するかは未定。

### 現行 TypeScript 実装（参照実装）

```
src/
  commands/
    dev.ts              # reqs-builder dev (統合起動、Hugo サーバ含む)
resources/
  hugo/
    hugo.toml           # Hugo 設定
    layouts/            # Hugo レイアウト
```
